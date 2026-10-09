"""F2 route: compute (or refresh) the wheelhouse advisory for a job post.

Stored on the job so reopening it costs nothing; the operator refreshes it
after adding work history. Advisory to the operator only: the Continue /
Abandon decision stays a manual click.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.deps import Db
from app.models.advisory import Advisory
from app.models.job import JobAnalysis
from app.routes.jobs import JobPostOut, _load, _row_to_out
from app.services.advisor import Advisor, build_advisor
from app.services.db import DbError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_advisor(settings: Annotated[Settings, Depends(get_settings)]) -> Advisor:
    return build_advisor(settings.anthropic_api_key, settings.anthropic_model)


AdvisorDep = Annotated[Advisor, Depends(get_advisor)]


@router.post("/{job_id}/advisory", response_model=JobPostOut)
def compute_advisory(job_id: str, db: Db, advisor: AdvisorDep) -> JobPostOut:
    row = _load(db, job_id)
    analysis = JobAnalysis.model_validate(row["analysis"])
    try:
        history = db.list_work_history_for_matching()
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e

    advisory: Advisory = advisor.advise(analysis, history)
    try:
        row = db.update_job_post(
            job_id,
            {"advisory": advisory.model_dump(mode="json"), "advisory_at": "now()"},
        )
    except DbError as e:
        raise HTTPException(e.status_code, e.detail) from e
    if row.get("advisory") is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "Advisory was not stored"
        )
    return _row_to_out(row)
