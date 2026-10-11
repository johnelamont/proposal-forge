"""F6 routes: Zoho connection, Lead preview, confirmed fields, Create Lead.

The connect flow completes from the frontend under the user's JWT, so the
refresh token is written under RLS. Create Lead is the affirmative action;
every press is logged to the append-only lead_attempts table (R1, R2).
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from app.config.picklists import INDUSTRY, JOB_TYPE
from app.core.auth import CurrentUser, current_user
from app.core.config import Settings, get_settings
from app.core.deps import Db
from app.models.job import AiFailure, JobAnalysis
from app.models.zoho import (
    Classification,
    CompleteRequest,
    ConnectionStatus,
    ConnectStart,
    CreateLeadResult,
    LeadAttempt,
    LeadFields,
    LeadFieldsIn,
    LeadPreview,
)
from app.routes.proposals import _load_job, _load_proposal
from app.services import crypto
from app.services.db import DbError, UserDb
from app.services.lead_builder import build_preview, payload_hash
from app.services.lead_classifier import LeadClassifier, build_classifier
from app.services.zoho_client import SCOPES, ZohoClient, ZohoError, ZohoGateway

router = APIRouter(prefix="/api", tags=["zoho"])


def get_zoho(settings: Annotated[Settings, Depends(get_settings)]) -> ZohoGateway:
    return ZohoClient(
        client_id=settings.zoho_client_id,
        client_secret=settings.zoho_client_secret,
        accounts_url=settings.zoho_accounts_url,
        api_url=settings.zoho_api_url,
        redirect_uri=settings.zoho_redirect_uri,
        layout_id=settings.zoho_leads_layout_id,
    )


def get_classifier(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LeadClassifier:
    return build_classifier(settings.anthropic_api_key, settings.anthropic_model)


Zoho = Annotated[ZohoGateway, Depends(get_zoho)]
Classifier = Annotated[LeadClassifier, Depends(get_classifier)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
User = Annotated[CurrentUser, Depends(current_user)]


def _http(e: DbError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


def _require_configured(settings: Settings) -> None:
    if not settings.zoho_configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Zoho is not configured on the server (ZOHO_CLIENT_ID, "
            "ZOHO_CLIENT_SECRET, TOKEN_ENCRYPTION_KEY).",
        )


# --- connection -------------------------------------------------------------


@router.get("/integrations/zoho/status", response_model=ConnectionStatus)
def zoho_status(db: Db, settings: SettingsDep) -> ConnectionStatus:
    try:
        row = db.get_zoho_connection()
    except DbError as e:
        raise _http(e) from e
    return ConnectionStatus(
        configured=settings.zoho_configured,
        connected=row is not None,
        connected_at=row.get("connected_at") if row else None,
        scopes=row.get("scopes", []) if row else [],
        last_used_at=row.get("last_used_at") if row else None,
    )


@router.get("/integrations/zoho/connect", response_model=ConnectStart)
def zoho_connect(db: Db, settings: SettingsDep, zoho: Zoho) -> ConnectStart:
    _require_configured(settings)
    nonce = secrets.token_urlsafe(24)
    try:
        db.insert_oauth_state(nonce)
    except DbError as e:
        raise _http(e) from e
    return ConnectStart(authorize_url=zoho.authorize_url(nonce), state=nonce)


@router.get("/integrations/zoho/callback", include_in_schema=False)
def zoho_callback(
    settings: SettingsDep,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    """Zoho sends the browser here; we only hand it on to the frontend, which
    completes the exchange under the user's own session."""
    params = {
        k: v for k, v in {"code": code, "state": state, "error": error}.items() if v
    }
    url = settings.frontend_url.rstrip("/") + "/settings/zoho?" + urlencode(params)
    return RedirectResponse(url, status_code=status.HTTP_302_FOUND)


@router.post("/integrations/zoho/complete", response_model=ConnectionStatus)
def zoho_complete(
    body: CompleteRequest, db: Db, user: User, settings: SettingsDep, zoho: Zoho
) -> ConnectionStatus:
    _require_configured(settings)
    try:
        state = db.get_oauth_state(body.state)
    except DbError as e:
        raise _http(e) from e
    if state is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Unknown or used connect state; start again."
        )
    expires = datetime.fromisoformat(state["expires_at"].replace("Z", "+00:00"))
    try:
        db.delete_oauth_state(body.state)  # single use, whatever happens next
    except DbError as e:
        raise _http(e) from e
    if expires < datetime.now(UTC):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Connect request expired; start again."
        )
    try:
        grant = zoho.exchange_code(body.code)
    except ZohoError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, e.message) from e
    try:
        enc = crypto.encrypt(
            grant.refresh_token, settings.token_encryption_key, aad=user.id
        )
    except crypto.CryptoError as e:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(e)) from e
    try:
        row = db.upsert_zoho_connection(
            {
                "refresh_token_enc": enc,
                "api_domain": grant.api_domain,
                "accounts_url": settings.zoho_accounts_url,
                "scopes": SCOPES.split(","),
                "connected_at": datetime.now(UTC).isoformat(),
            }
        )
    except DbError as e:
        raise _http(e) from e
    return ConnectionStatus(
        configured=True,
        connected=True,
        connected_at=row.get("connected_at"),
        scopes=row.get("scopes", []),
    )


@router.delete("/integrations/zoho/connection", status_code=status.HTTP_204_NO_CONTENT)
def zoho_disconnect(db: Db, user: User, settings: SettingsDep, zoho: Zoho) -> None:
    try:
        row = db.get_zoho_connection()
    except DbError as e:
        raise _http(e) from e
    if row is None:
        return None
    try:
        token = crypto.decrypt(
            row["refresh_token_enc"], settings.token_encryption_key, aad=user.id
        )
        zoho.revoke(token)
    except crypto.CryptoError:
        pass  # cannot revoke what we cannot read; delete the row anyway
    try:
        db.delete_zoho_connection()
    except DbError as e:
        raise _http(e) from e
    return None


# --- lead -------------------------------------------------------------------


def _fields(proposal: dict[str, Any]) -> LeadFields | None:
    raw = proposal.get("lead_fields")
    return LeadFields.model_validate(raw) if raw else None


def _classification(
    proposal: dict[str, Any],
) -> tuple[Classification | None, AiFailure | None]:
    raw = proposal.get("lead_classification") or {}
    result = raw.get("result")
    failure = raw.get("failure")
    return (
        Classification.model_validate(result) if result else None,
        AiFailure.model_validate(failure) if failure else None,
    )


def _ensure_classified(
    db: UserDb,
    proposal: dict[str, Any],
    analysis: JobAnalysis,
    classifier: LeadClassifier,
    force: bool,
) -> dict[str, Any]:
    classification, failure = _classification(proposal)
    if classification is not None and not force:
        return proposal
    outcome = classifier.classify(analysis)
    stored = {
        "at": datetime.now(UTC).isoformat(),
        "result": outcome.model_dump(mode="json")
        if isinstance(outcome, Classification)
        else None,
        "failure": outcome.model_dump(mode="json")
        if isinstance(outcome, AiFailure)
        else None,
    }
    try:
        return db.update_proposal(proposal["id"], {"lead_classification": stored})
    except DbError as e:
        raise _http(e) from e


def _preview(
    db: UserDb,
    proposal: dict[str, Any],
    classifier: LeadClassifier,
    *,
    reclassify: bool = False,
) -> tuple[LeadPreview, JobAnalysis, dict[str, Any]]:
    job = _load_job(db, proposal["job_post_id"])
    analysis = JobAnalysis.model_validate(job["analysis"])
    if not _fields(proposal) or _fields(proposal).confirmed_at is None:  # type: ignore[union-attr]
        proposal = _ensure_classified(db, proposal, analysis, classifier, reclassify)
    try:
        versions = db.list_versions(proposal["id"])
        approvals = db.list_approvals(proposal["id"])
        connected = db.get_zoho_connection() is not None
    except DbError as e:
        raise _http(e) from e
    classification, failure = _classification(proposal)
    preview = build_preview(
        analysis,
        versions,
        approvals,
        _fields(proposal),
        classification,
        failure,
        connected,
    )
    return preview, analysis, proposal


@router.get("/proposals/{proposal_id}/lead-preview", response_model=LeadPreview)
def lead_preview(
    proposal_id: str,
    db: Db,
    classifier: Classifier,
    reclassify: Annotated[bool, Query()] = False,
) -> LeadPreview:
    proposal = _load_proposal(db, proposal_id)
    preview, _, _ = _preview(db, proposal, classifier, reclassify=reclassify)
    return preview


@router.put("/proposals/{proposal_id}/lead-fields", response_model=LeadPreview)
def set_lead_fields(
    proposal_id: str, body: LeadFieldsIn, db: Db, classifier: Classifier
) -> LeadPreview:
    """The operator's confirmed values. Picklist fields must be on the list."""
    if body.industry is not None and body.industry not in INDUSTRY:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Industry is not on the picklist"
        )
    if body.job_type is not None and body.job_type not in JOB_TYPE:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Job_Type is not on the picklist"
        )
    proposal = _load_proposal(db, proposal_id)
    fields = LeadFields(**body.model_dump(), confirmed_at=datetime.now(UTC).isoformat())
    try:
        proposal = db.update_proposal(
            proposal_id, {"lead_fields": fields.model_dump(mode="json")}
        )
    except DbError as e:
        raise _http(e) from e
    preview, _, _ = _preview(db, proposal, classifier)
    return preview


@router.get("/proposals/{proposal_id}/lead-attempts", response_model=list[LeadAttempt])
def lead_attempts(proposal_id: str, db: Db) -> list[LeadAttempt]:
    _load_proposal(db, proposal_id)
    try:
        rows = db.list_lead_attempts(proposal_id)
    except DbError as e:
        raise _http(e) from e
    return [LeadAttempt.model_validate(r) for r in rows]


@router.post("/proposals/{proposal_id}/create-lead", response_model=CreateLeadResult)
def create_lead(
    proposal_id: str,
    db: Db,
    user: User,
    settings: SettingsDep,
    zoho: Zoho,
    classifier: Classifier,
) -> CreateLeadResult:
    """The affirmative action. Upserts on Upwork_Job_ID; logs every attempt."""
    _require_configured(settings)
    proposal = _load_proposal(db, proposal_id)
    preview, _, proposal = _preview(db, proposal, classifier)
    if not preview.ready:
        missing = ", ".join(c.label for c in preview.checklist if not c.ok)
        raise HTTPException(status.HTTP_409_CONFLICT, f"Not ready: {missing}")

    try:
        conn = db.get_zoho_connection()
    except DbError as e:
        raise _http(e) from e
    if conn is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zoho is not connected")

    payload = preview.payload
    digest = payload_hash(payload)
    attempt: dict[str, Any] = {"proposal_id": proposal_id, "payload_hash": digest}
    error: str | None = None
    reconnect = False
    result = None
    try:
        refresh = crypto.decrypt(
            conn["refresh_token_enc"], settings.token_encryption_key, aad=user.id
        )
        access, domain = zoho.access_token(refresh)
        result = zoho.upsert_lead(access, domain or conn["api_domain"], payload)
        attempt.update(
            response_status=result.status,
            zoho_lead_id=result.lead_id,
            action=result.action,
        )
    except crypto.CryptoError as e:
        error, reconnect = f"Stored Zoho token unreadable: {e}", True
    except ZohoError as e:
        error, reconnect = e.message, e.reconnect
        attempt.update(response_status=e.status)
    if error:
        attempt["error"] = error[:1000]

    try:
        row = db.insert_lead_attempt(attempt)
        if result is not None:
            db.update_proposal(
                proposal_id,
                {
                    "zoho_lead_id": result.lead_id,
                    "lead_sync_state": "created",
                    "status": "submitted",
                    "submitted_at": proposal.get("submitted_at")
                    or datetime.now(UTC).isoformat(),
                },
            )
            db.touch_zoho_connection()
        else:
            db.update_proposal(proposal_id, {"lead_sync_state": "failed"})
    except DbError as e:
        raise _http(e) from e

    return CreateLeadResult(
        ok=result is not None,
        zoho_lead_id=result.lead_id if result else None,
        action=result.action if result else None,
        error=error,
        reconnect=reconnect,
        attempt=LeadAttempt.model_validate(row),
    )
