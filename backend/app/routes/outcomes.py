"""F8 routes: the inbound outcome from Zoho, the integration secret, a
proposal's outcome history and index, the review queue, and the Attention
counts for the home screen.

The inbound route is the one public write in the API. It carries no user JWT,
so it validates the contract here (400), rate-limits, hashes the bearer secret
and hands both to `record_outcome()` through PostgREST as the anon role. That
function is the only thing anon may call; it resolves the tenant itself.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import ValidationError

from app.core.config import Settings, get_settings
from app.core.deps import Db
from app.models.outcomes import (
    ArchiveIn,
    Attention,
    AttentionItem,
    MatchIn,
    OutcomeIn,
    OutcomeRecord,
    OutcomeResult,
    ProposalOutcomes,
    QueuedOutcome,
    RagIndexRow,
    SecretCreated,
    SecretStatus,
)
from app.routes.proposals import _load_proposal
from app.services.db import AnonDb, DbError
from app.services.rate_limit import RateLimiter

router = APIRouter(prefix="/api", tags=["outcomes"])

MAX_BODY_BYTES = 32 * 1024
limiter = RateLimiter(limit=30, window_seconds=60)

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_anon_db(settings: SettingsDep) -> AnonDb:
    return AnonDb(settings)


Anon = Annotated[AnonDb, Depends(get_anon_db)]


def _http(e: DbError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


def endpoint_url(settings: Settings) -> str:
    """The public URL Zoho posts to: same origin as the OAuth callback."""
    u = urlparse(settings.zoho_redirect_uri)
    return f"{u.scheme}://{u.netloc}/api/integrations/zoho/outcome"


def crm_lead_url(settings: Settings, lead_id: str | None) -> str | None:
    """Org-less record URL; Zoho redirects a single-org account to its org path.
    accounts.zoho.<tld> → crm.zoho.<tld>, so EU/IN data centres resolve too."""
    if not lead_id:
        return None
    host = urlparse(settings.zoho_accounts_url).netloc.replace("accounts.", "crm.", 1)
    return f"https://{host}/crm/tab/Leads/{lead_id}"


def _hash(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


# --- inbound ---------------------------------------------------------------------


def _validation_message(e: ValidationError) -> str:
    parts = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg')}" if loc else str(err.get("msg")))
    return "; ".join(parts)[:500]


@router.post(
    "/integrations/zoho/outcome",
    response_model=OutcomeResult,
    responses={202: {"model": OutcomeResult}},
)
async def receive_outcome(
    request: Request, response: Response, anon: Anon
) -> OutcomeResult:
    client_ip = request.client.host if request.client else "unknown"
    if not limiter.allow(client_ip):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests; try again shortly"
        )

    auth = request.headers.get("authorization", "")
    scheme, _, token = auth.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or len(token) < 16:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "Missing or malformed integration secret"
        )

    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        raise HTTPException(
            status.HTTP_413_CONTENT_TOO_LARGE, "Payload larger than 32 KB"
        )
    try:
        payload = OutcomeIn.model_validate(json.loads(body or b"{}"))
    except ValidationError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, _validation_message(e)) from e
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Not JSON: {e}") from e

    try:
        result = anon.record_outcome(
            _hash(token), payload.model_dump(mode="json", exclude_none=True)
        )
    except DbError as e:
        # Zoho shows this on the Lead and emails the operator (R8).
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Proposal Forge could not record the outcome: {e.detail[:200]}",
        ) from e

    code = int(result.get("code", 500))
    if code == 401:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, result.get("message"))
    if code not in (200, 202):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            result.get("message") or "Unexpected result from record_outcome",
        )
    response.status_code = code
    return OutcomeResult.model_validate(result)


# --- the secret -------------------------------------------------------------------


@router.get("/integrations/outcome-secret", response_model=SecretStatus)
def secret_status(db: Db, settings: SettingsDep) -> SecretStatus:
    try:
        row = db.get_integration_secret()
    except DbError as e:
        raise _http(e) from e
    return SecretStatus(
        exists=row is not None,
        created_at=row.get("created_at") if row else None,
        last_used_at=row.get("last_used_at") if row else None,
        endpoint_url=endpoint_url(settings),
    )


@router.post("/integrations/outcome-secret", response_model=SecretCreated)
def generate_secret(db: Db, settings: SettingsDep) -> SecretCreated:
    """Generate or rotate. The plaintext is returned once and never stored."""
    plaintext = secrets.token_urlsafe(32)
    try:
        row = db.upsert_integration_secret(
            {
                "secret_hash": _hash(plaintext),
                "created_at": datetime.now(UTC).isoformat(),
                "last_used_at": None,
            }
        )
    except DbError as e:
        raise _http(e) from e
    return SecretCreated(
        exists=True,
        created_at=row.get("created_at"),
        last_used_at=None,
        endpoint_url=endpoint_url(settings),
        secret=plaintext,
    )


@router.delete("/integrations/outcome-secret", status_code=status.HTTP_204_NO_CONTENT)
def revoke_secret(db: Db) -> None:
    try:
        db.delete_integration_secret()
    except DbError as e:
        raise _http(e) from e
    return None


# --- a proposal's outcomes ----------------------------------------------------------


def _stale_after(db: Db) -> int:
    try:
        profile = db.get_profile()
    except DbError as e:
        raise _http(e) from e
    return int((profile or {}).get("stale_submitted_days") or 14)


def _is_stale(status_: str, submitted_at: str | None, days: int) -> bool:
    if status_ != "submitted" or not submitted_at:
        return False
    since = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
    return datetime.now(UTC) - since > timedelta(days=days)


@router.get("/proposals/{proposal_id}/outcomes", response_model=ProposalOutcomes)
def proposal_outcomes(
    proposal_id: str, db: Db, settings: SettingsDep
) -> ProposalOutcomes:
    proposal = _load_proposal(db, proposal_id)
    try:
        history = db.list_outcomes(proposal_id)
        index = db.get_rag_index(proposal_id)
    except DbError as e:
        raise _http(e) from e
    days = _stale_after(db)
    return ProposalOutcomes(
        status=proposal["status"],
        history=[OutcomeRecord.model_validate(r) for r in history],
        index=RagIndexRow.model_validate(index) if index else None,
        zoho_lead_id=proposal.get("zoho_lead_id"),
        lead_url=crm_lead_url(settings, proposal.get("zoho_lead_id")),
        submitted_at=proposal.get("submitted_at"),
        stale_after_days=days,
        stale=_is_stale(proposal["status"], proposal.get("submitted_at"), days),
    )


@router.put("/proposals/{proposal_id}/rag-archived", response_model=RagIndexRow)
def set_archived(proposal_id: str, body: ArchiveIn, db: Db) -> RagIndexRow:
    _load_proposal(db, proposal_id)
    try:
        row = db.set_rag_archived(proposal_id, body.archived)
    except DbError as e:
        raise _http(e) from e
    if row is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "This proposal has no outcome indexed yet"
        )
    return RagIndexRow.model_validate(row)


# --- review queue -------------------------------------------------------------------


@router.get("/outcomes/queue", response_model=list[QueuedOutcome])
def list_queue(db: Db) -> list[QueuedOutcome]:
    try:
        rows = db.list_outcome_queue()
    except DbError as e:
        raise _http(e) from e
    return [QueuedOutcome.model_validate(r) for r in rows]


@router.post("/outcomes/queue/{queue_id}/match", response_model=OutcomeResult)
def match_queued(queue_id: str, body: MatchIn, db: Db) -> OutcomeResult:
    """The operator says which proposal a held outcome belongs to."""
    _load_proposal(db, body.proposal_id)
    try:
        result = db.resolve_queued_outcome(queue_id, body.proposal_id)
    except DbError as e:
        if "not found" in e.detail:
            raise HTTPException(status.HTTP_404_NOT_FOUND, e.detail) from e
        raise _http(e) from e
    return OutcomeResult.model_validate(result)


@router.post(
    "/outcomes/queue/{queue_id}/dismiss", status_code=status.HTTP_204_NO_CONTENT
)
def dismiss_queued(queue_id: str, db: Db) -> None:
    try:
        ok = db.dismiss_queued_outcome(queue_id)
    except DbError as e:
        raise _http(e) from e
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Queued outcome not found")
    return None


@router.post("/outcomes/rebuild-index")
def rebuild_index(db: Db) -> dict[str, int]:
    """Regenerate the caller's rag_index from outcome history."""
    try:
        n = db.rebuild_rag_index()
    except DbError as e:
        raise _http(e) from e
    return {"rebuilt": int(n or 0)}


# --- attention ----------------------------------------------------------------------


def _title(row: dict[str, Any]) -> str | None:
    job = row.get("job_posts") or {}
    if isinstance(job, list):
        job = job[0] if job else {}
    return job.get("title")


@router.get("/attention", response_model=Attention)
def attention(db: Db) -> Attention:
    try:
        proposals = db.list_proposals_for_attention()
        queued = db.list_outcome_queue()
    except DbError as e:
        raise _http(e) from e
    days = _stale_after(db)
    failed = [
        AttentionItem(
            proposal_id=p["id"], job_title=_title(p), since=p.get("updated_at")
        )
        for p in proposals
        if p.get("lead_sync_state") == "failed"
    ]
    stale = [
        AttentionItem(
            proposal_id=p["id"], job_title=_title(p), since=p.get("submitted_at")
        )
        for p in proposals
        if _is_stale(p.get("status", ""), p.get("submitted_at"), days)
    ]
    return Attention(
        lead_failed=failed,
        queued_outcomes=len(queued),
        stale_submitted=stale,
        stale_after_days=days,
    )
