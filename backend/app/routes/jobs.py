"""F1 routes: parse a pasted job post, review it, decide.

Nothing is treated as a parsed job until the operator clicks Continue or
Abandon; until then the row exists with `decision = null`.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.config import Settings, get_settings
from app.core.deps import Db, get_db
from app.models.job import JobAnalysis, ParsedJob
from app.services import job_analysis
from app.services.claude import ClaudeReader, build_reader
from app.services.db import DbError, UserDb
from app.services.job_parser import RE_JOB_URL

router = APIRouter(prefix="/api/jobs", tags=["jobs"])

__all__ = ["get_db", "get_reader", "router"]


# --- dependencies -----------------------------------------------------------


def get_reader(settings: Annotated[Settings, Depends(get_settings)]) -> ClaudeReader:
    return build_reader(settings.anthropic_api_key, settings.anthropic_model)


Reader = Annotated[ClaudeReader, Depends(get_reader)]


# --- schemas ----------------------------------------------------------------


class ParseRequest(BaseModel):
    raw_paste: str = Field(min_length=1, max_length=50_000)


class LinkRequest(BaseModel):
    job_link: str = Field(min_length=1, max_length=500)


class DecisionRequest(BaseModel):
    decision: Literal["continue", "abandon"]


class JobPostOut(BaseModel):
    id: str
    analysis: JobAnalysis
    upwork_job_id: str | None
    decision: Literal["continue", "abandon"] | None
    decided_at: str | None
    created_at: str


# --- helpers ----------------------------------------------------------------


def _row_to_out(row: dict[str, Any]) -> JobPostOut:
    return JobPostOut(
        id=row["id"],
        analysis=JobAnalysis.model_validate(row["analysis"]),
        upwork_job_id=row.get("upwork_job_id"),
        decision=row.get("decision"),
        decided_at=row.get("decided_at"),
        created_at=row["created_at"],
    )


def _analysis_columns(analysis: JobAnalysis) -> dict[str, Any]:
    return {
        "analysis": analysis.model_dump(mode="json"),
        "parse_status": analysis.parse_status,
        "upwork_job_id": analysis.parsed.upwork_job_id,
    }


def _load(db: UserDb, job_id: str) -> dict[str, Any]:
    try:
        row = db.get_job_post(job_id)
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job post not found")
    return row


# --- routes -----------------------------------------------------------------


@router.post("/parse", status_code=status.HTTP_201_CREATED, response_model=JobPostOut)
def parse_job(body: ParseRequest, db: Db, reader: Reader) -> JobPostOut:
    analysis = job_analysis.analyse_job_post(body.raw_paste, reader)
    try:
        row = db.insert_job_post(
            {"raw_paste": body.raw_paste, **_analysis_columns(analysis)}
        )
    except DbError as e:
        if e.status_code == 409:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You already have a job post with this Upwork job ID.",
            ) from e
        raise HTTPException(e.status_code, e.detail) from e
    return _row_to_out(row)


@router.get("", response_model=list[dict[str, Any]])
def list_jobs(db: Db) -> list[dict[str, Any]]:
    try:
        return db.list_job_posts()
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e


@router.get("/{job_id}", response_model=JobPostOut)
def get_job(job_id: str, db: Db) -> JobPostOut:
    return _row_to_out(_load(db, job_id))


@router.post("/{job_id}/reread", response_model=JobPostOut)
def reread_job(job_id: str, db: Db, reader: Reader) -> JobPostOut:
    """Retry the Claude layer only. The deterministic fields are untouched."""
    row = _load(db, job_id)
    parsed = ParsedJob.model_validate(row["analysis"]["parsed"])
    analysis = job_analysis.reread(parsed, reader)
    try:
        row = db.update_job_post(job_id, _analysis_columns(analysis))
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e
    return _row_to_out(row)


@router.patch("/{job_id}/link", response_model=JobPostOut)
def set_job_link(job_id: str, body: LinkRequest, db: Db) -> JobPostOut:
    """Supply the job link a mobile paste lacks. Accepts a URL or a bare ID."""
    m = RE_JOB_URL.search(body.job_link) or re.fullmatch(
        r"~[0-9A-Za-z]+", body.job_link.strip()
    )
    if not m:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Expected an Upwork job URL or an ID like ~0123456789abcdef.",
        )
    job_ref = m.group(1) if m.lastindex else m.group(0)
    row = _load(db, job_id)
    analysis = JobAnalysis.model_validate(row["analysis"])
    analysis.parsed.upwork_job_id = job_ref
    try:
        row = db.update_job_post(job_id, _analysis_columns(analysis))
    except DbError as e:
        if e.status_code == 409:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "You already have a job post with this Upwork job ID.",
            ) from e
        raise HTTPException(e.status_code, e.detail) from e
    return _row_to_out(row)


@router.post("/{job_id}/decision", response_model=JobPostOut)
def decide(job_id: str, body: DecisionRequest, db: Db) -> JobPostOut:
    """Continue or Abandon. Both are recorded; the row is never deleted."""
    row = _load(db, job_id)
    if row.get("decision") is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Already decided: {row['decision']}"
        )
    try:
        row = db.update_job_post(
            job_id, {"decision": body.decision, "decided_at": "now()"}
        )
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e
    return _row_to_out(row)
