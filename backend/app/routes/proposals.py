"""F3/F4 routes: profile, proposals, draft versions, approvals.

Every change to a draft is a new version (append-only). Copying is the
approval: the frontend asks `copy-text` for the exact text and its hash,
copies it, then records the approval with that hash; the server refuses a
hash that does not match the stored version (R1, R2).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import Settings, get_settings
from app.core.deps import Db
from app.models.advisory import Advisory
from app.models.job import JobAnalysis
from app.models.proposal import (
    AiMeta,
    ApprovalRequest,
    CreateProposalRequest,
    DraftVersion,
    EditRequest,
    Profile,
    ProfileIn,
    Proposal,
    ProposalApproval,
    ProposalOut,
    QuestionsRequest,
    Quote,
    RefineRequest,
    SectionName,
    Sections,
)
from app.services.db import DbError, UserDb
from app.services.drafter import Drafter, build_drafter, content_hash, questions_for
from app.services.form_paste import extract_questions
from app.services.pricing import propose_quote

router = APIRouter(prefix="/api", tags=["proposals"])


def get_drafter(settings: Annotated[Settings, Depends(get_settings)]) -> Drafter:
    return build_drafter(settings.anthropic_api_key, settings.anthropic_model)


DrafterDep = Annotated[Drafter, Depends(get_drafter)]


def _http(e: DbError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


# --- profile ----------------------------------------------------------------


@router.get("/profile", response_model=Profile | None)
def get_profile(db: Db) -> Profile | None:
    try:
        row = db.get_profile()
    except DbError as e:
        raise _http(e) from e
    return Profile.model_validate(row) if row else None


@router.put("/profile", response_model=Profile)
def put_profile(body: ProfileIn, db: Db) -> Profile:
    try:
        row = db.upsert_profile(body.model_dump(mode="json"))
    except DbError as e:
        raise _http(e) from e
    return Profile.model_validate(row)


# --- helpers ------------------------------------------------------------------


def _require_profile(db: UserDb) -> Profile:
    try:
        row = db.get_profile()
    except DbError as e:
        raise _http(e) from e
    profile = Profile.model_validate(row) if row else None
    if profile is None or not profile.ready:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Set up your profile first: a signature name and a positioning "
            "paragraph are needed before drafting.",
        )
    return profile


def _load_proposal(db: UserDb, proposal_id: str) -> dict[str, Any]:
    try:
        row = db.get_proposal(proposal_id)
    except DbError as e:
        raise _http(e) from e
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Proposal not found")
    return row


def _load_job(db: UserDb, job_post_id: str) -> dict[str, Any]:
    try:
        row = db.get_job_post(job_post_id)
    except DbError as e:
        raise _http(e) from e
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job post not found")
    return row


def _out(db: UserDb, proposal: dict[str, Any]) -> ProposalOut:
    try:
        versions = db.list_versions(proposal["id"])
        approvals = db.list_approvals(proposal["id"])
        job = db.get_job_post(proposal["job_post_id"])
    except DbError as e:
        raise _http(e) from e
    title = None
    if job:
        title = (job.get("analysis") or {}).get("parsed", {}).get("title")
    return ProposalOut(
        proposal=Proposal.model_validate(proposal),
        versions=[DraftVersion.model_validate(v) for v in versions],
        approvals=[ProposalApproval.model_validate(a) for a in approvals],
        job_title=title,
    )


def _current_sections(db: UserDb, proposal: dict[str, Any]) -> tuple[dict, Sections]:
    vid = proposal.get("current_version_id")
    if not vid:
        raise HTTPException(status.HTTP_409_CONFLICT, "No draft yet")
    try:
        version = db.get_version(vid)
    except DbError as e:
        raise _http(e) from e
    if version is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Current version missing")
    return version, Sections.model_validate(version["sections"])


def _append_version(
    db: UserDb,
    proposal: dict[str, Any],
    sections: Sections,
    source: str,
    meta: AiMeta | None,
) -> dict[str, Any]:
    try:
        existing = db.list_versions(proposal["id"])
        number = (max((v["version"] for v in existing), default=0)) + 1
        version = db.insert_version(
            {
                "proposal_id": proposal["id"],
                "version": number,
                "source": source,
                "sections": sections.model_dump(mode="json"),
                "ai_meta": meta.model_dump(mode="json") if meta else None,
            }
        )
        return db.update_proposal(proposal["id"], {"current_version_id": version["id"]})
    except DbError as e:
        raise _http(e) from e


def _generate(
    db: UserDb, drafter: Drafter, proposal: dict[str, Any], profile: Profile
) -> dict[str, Any]:
    job = _load_job(db, proposal["job_post_id"])
    analysis = JobAnalysis.model_validate(job["analysis"])
    advisory = Advisory.model_validate(job["advisory"]) if job.get("advisory") else None
    cite_ids = (
        [c.entry_id for c in advisory.reading.cite]
        if advisory and advisory.reading
        else []
    )
    try:
        cited = db.get_work_history_many(cite_ids)
    except DbError as e:
        raise _http(e) from e
    questions = questions_for(analysis, proposal.get("extra_questions") or [])
    sections, meta = drafter.draft(analysis, advisory, cited, profile, questions)
    sections.quote = propose_quote(analysis.parsed, profile, cited, analysis.conflicts)
    return _append_version(db, proposal, sections, "ai", meta)


# --- proposals ------------------------------------------------------------------


@router.post(
    "/proposals", status_code=status.HTTP_201_CREATED, response_model=ProposalOut
)
def create_proposal(
    body: CreateProposalRequest, db: Db, drafter: DrafterDep
) -> ProposalOut:
    """Create the proposal for a job (one per job) and write draft version 1."""
    profile = _require_profile(db)
    job = _load_job(db, body.job_post_id)
    if job.get("decision") == "abandon":
        raise HTTPException(status.HTTP_409_CONFLICT, "This job was abandoned.")
    try:
        existing = db.get_proposal_by_job(body.job_post_id)
    except DbError as e:
        raise _http(e) from e
    if existing:
        return _out(db, existing)

    analysis = JobAnalysis.model_validate(job["analysis"])
    extra = (
        extract_questions(body.form_paste, [q.text for q in analysis.parsed.questions])
        if body.form_paste
        else []
    )
    try:
        proposal = db.insert_proposal(
            {"job_post_id": body.job_post_id, "extra_questions": extra}
        )
    except DbError as e:
        raise _http(e) from e
    proposal = _generate(db, drafter, proposal, profile)
    return _out(db, proposal)


@router.get("/proposals/by-job/{job_post_id}", response_model=ProposalOut | None)
def proposal_for_job(job_post_id: str, db: Db) -> ProposalOut | None:
    try:
        row = db.get_proposal_by_job(job_post_id)
    except DbError as e:
        raise _http(e) from e
    return _out(db, row) if row else None


@router.get("/proposals/{proposal_id}", response_model=ProposalOut)
def get_proposal(proposal_id: str, db: Db) -> ProposalOut:
    return _out(db, _load_proposal(db, proposal_id))


@router.post("/proposals/{proposal_id}/draft", response_model=ProposalOut)
def redraft(proposal_id: str, db: Db, drafter: DrafterDep) -> ProposalOut:
    """A fresh full draft as a new version. Earlier versions are untouched."""
    profile = _require_profile(db)
    proposal = _load_proposal(db, proposal_id)
    return _out(db, _generate(db, drafter, proposal, profile))


@router.post("/proposals/{proposal_id}/questions", response_model=ProposalOut)
def add_questions(proposal_id: str, body: QuestionsRequest, db: Db) -> ProposalOut:
    """Merge questions from a pasted apply form. The next draft answers them."""
    proposal = _load_proposal(db, proposal_id)
    job = _load_job(db, proposal["job_post_id"])
    analysis = JobAnalysis.model_validate(job["analysis"])
    known = [q.text for q in analysis.parsed.questions] + list(
        proposal.get("extra_questions") or []
    )
    found = extract_questions(body.form_paste, known)
    if not found:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "No new questions found in that paste.",
        )
    try:
        proposal = db.update_proposal(
            proposal_id,
            {"extra_questions": list(proposal.get("extra_questions") or []) + found},
        )
    except DbError as e:
        raise _http(e) from e
    return _out(db, proposal)


@router.post("/proposals/{proposal_id}/refine", response_model=ProposalOut)
def refine(
    proposal_id: str, body: RefineRequest, db: Db, drafter: DrafterDep
) -> ProposalOut:
    """Claude rewrites one section per the instruction → new version.
    On failure nothing is written and the error is returned (R8)."""
    profile = _require_profile(db)
    proposal = _load_proposal(db, proposal_id)
    _, sections = _current_sections(db, proposal)
    if body.section == "cover_letter":
        current = sections.cover_letter or ""
    else:
        if body.index is None or not 0 <= body.index < len(sections.answers):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Bad answer index"
            )
        current = sections.answers[body.index].answer
    if not current.strip():
        raise HTTPException(
            status.HTTP_409_CONFLICT, "Nothing to refine yet; edit first."
        )
    text, meta = drafter.refine(
        current, body.instruction, profile, body.section == "cover_letter"
    )
    if text is None:
        failure = meta.failure.message if meta.failure else "unknown"
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"Refine failed: {failure} Previous version kept.",
        )
    if body.section == "cover_letter":
        sections.cover_letter = text
    else:
        sections.answers[body.index].answer = text  # type: ignore[index]
    return _out(db, _append_version(db, proposal, sections, "refine", meta))


@router.post("/proposals/{proposal_id}/edit", response_model=ProposalOut)
def edit(proposal_id: str, body: EditRequest, db: Db) -> ProposalOut:
    """The operator's own change to one section → new version."""
    proposal = _load_proposal(db, proposal_id)
    _, sections = _current_sections(db, proposal)
    if body.section == "cover_letter":
        sections.cover_letter = body.content
    elif body.section == "answer":
        if body.index is None or not 0 <= body.index < len(sections.answers):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Bad answer index"
            )
        sections.answers[body.index].answer = body.content
    else:
        previous = sections.quote
        sections.quote = Quote(
            model=previous.model if previous else None,
            amount=body.quote_amount,
            rationale=body.content or "Entered by you.",
            evidence=previous.evidence if previous else [],
        )
    return _out(db, _append_version(db, proposal, sections, "edit", None))


# --- copy and approval ------------------------------------------------------------


class CopyText(BaseModel):
    text: str
    content_hash: str


def section_text(sections: Sections, section: SectionName, index: int | None) -> str:
    """Exactly what goes to the clipboard. The approval hash is of this text."""
    if section == "cover_letter":
        return sections.cover_letter or ""
    if section == "answer":
        if index is None or not 0 <= index < len(sections.answers):
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "Bad answer index"
            )
        return sections.answers[index].answer
    if section == "quote":
        q = sections.quote
        return "" if q is None or q.amount is None else str(q.amount)
    parts = [sections.cover_letter or ""]
    for a in sections.answers:
        parts.append(f"{a.question}\n{a.answer}")
    if sections.quote and sections.quote.amount is not None:
        unit = "/hr" if sections.quote.model == "hourly" else ""
        parts.append(f"Quote: ${sections.quote.amount}{unit}")
    return "\n\n".join(p for p in parts if p.strip())


@router.get("/proposals/{proposal_id}/copy-text", response_model=CopyText)
def copy_text(
    proposal_id: str,
    db: Db,
    section: SectionName,
    version_id: str,
    index: int | None = None,
) -> CopyText:
    _load_proposal(db, proposal_id)
    try:
        version = db.get_version(version_id)
    except DbError as e:
        raise _http(e) from e
    if version is None or version["proposal_id"] != proposal_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    text = section_text(Sections.model_validate(version["sections"]), section, index)
    return CopyText(text=text, content_hash=content_hash(text))


@router.post(
    "/proposals/{proposal_id}/approvals",
    status_code=status.HTTP_201_CREATED,
    response_model=ProposalApproval,
)
def record_approval(
    proposal_id: str, body: ApprovalRequest, db: Db
) -> ProposalApproval:
    """Called by the frontend in the same click that wrote the clipboard."""
    _load_proposal(db, proposal_id)
    try:
        version = db.get_version(body.draft_version_id)
    except DbError as e:
        raise _http(e) from e
    if version is None or version["proposal_id"] != proposal_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Version not found")
    expected = content_hash(
        section_text(
            Sections.model_validate(version["sections"]),
            body.section,
            body.section_index,
        )
    )
    if expected != body.content_hash:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The copied text does not match this version. Copy again from the page.",
        )
    try:
        row = db.insert_approval(
            {
                "proposal_id": proposal_id,
                "draft_version_id": body.draft_version_id,
                "section": body.section,
                "section_index": body.section_index,
                "content_hash": body.content_hash,
            }
        )
    except DbError as e:
        raise _http(e) from e
    return ProposalApproval.model_validate(row)
