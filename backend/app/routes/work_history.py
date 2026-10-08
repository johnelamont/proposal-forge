"""F5 routes: extract a draft from dropped files, then CRUD on work history.

`extract` never writes. Saving is a separate, explicit request carrying the
operator's edited record (R8). Files are screened on extract and again on
save (R5).
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.config import Settings, get_settings
from app.core.deps import Db
from app.models.job import AiFailure
from app.models.work_history import (
    Extraction,
    ExtractRequest,
    ExtractResponse,
    SourceFile,
    WorkHistoryIn,
    WorkHistoryOut,
    WorkHistoryPatch,
    WorkHistorySummary,
)
from app.services.db import DbError
from app.services.file_rules import screen
from app.services.work_history_extractor import (
    WorkHistoryExtractor,
    build_extractor,
)

router = APIRouter(prefix="/api/work-history", tags=["work-history"])


def get_extractor(
    settings: Annotated[Settings, Depends(get_settings)],
) -> WorkHistoryExtractor:
    return build_extractor(settings.anthropic_api_key, settings.anthropic_model)


Extractor = Annotated[WorkHistoryExtractor, Depends(get_extractor)]

NULLABLE_FIELDS = {
    "vertical",
    "project_type",
    "complexity",
    "role",
    "client_name",
    "budget_band",
    "started",
    "ended",
}


def _http(e: DbError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


def _out(row: dict[str, Any]) -> WorkHistoryOut:
    return WorkHistoryOut.model_validate(row)


def _screened_source_files(files) -> list[dict[str, Any]]:
    """Re-screen on save; refuse the whole request if any file fails."""
    result = screen(files)
    if result.refused:
        detail = "; ".join(f"{r.name}: {r.reason}" for r in result.refused)
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, f"Refused files — {detail}"
        )
    return [
        SourceFile(**a.model_dump(), content=t.content).model_dump()
        for a, t in zip(result.accepted, result.texts, strict=True)
    ]


# --- extract (no write) ------------------------------------------------------


@router.post("/extract", response_model=ExtractResponse)
def extract(body: ExtractRequest, extractor: Extractor) -> ExtractResponse:
    result = screen(body.files)
    if not result.texts:
        return ExtractResponse(
            accepted=result.accepted,
            refused=result.refused,
            extraction=None,
            failure=AiFailure(
                kind="skipped", message="None of the dropped files can be sent."
            ),
        )
    outcome = extractor.extract(result.texts)
    return ExtractResponse(
        accepted=result.accepted,
        refused=result.refused,
        extraction=outcome if isinstance(outcome, Extraction) else None,
        failure=outcome if isinstance(outcome, AiFailure) else None,
    )


# --- CRUD -------------------------------------------------------------------


@router.get("", response_model=list[WorkHistorySummary])
def list_entries(db: Db) -> list[WorkHistorySummary]:
    try:
        rows = db.list_work_history()
    except DbError as e:
        raise _http(e) from e
    return [WorkHistorySummary.model_validate(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=WorkHistoryOut)
def create_entry(body: WorkHistoryIn, db: Db) -> WorkHistoryOut:
    row = body.model_dump(mode="json", exclude={"source_files"})
    row["source_files"] = _screened_source_files(body.source_files)
    try:
        return _out(db.insert_work_history(row))
    except DbError as e:
        raise _http(e) from e


@router.get("/{entry_id}", response_model=WorkHistoryOut)
def get_entry(entry_id: str, db: Db) -> WorkHistoryOut:
    try:
        row = db.get_work_history(entry_id)
    except DbError as e:
        raise _http(e) from e
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work history entry not found")
    return _out(row)


@router.patch("/{entry_id}", response_model=WorkHistoryOut)
def update_entry(entry_id: str, body: WorkHistoryPatch, db: Db) -> WorkHistoryOut:
    patch = body.model_dump(mode="json", exclude_none=True, exclude={"clear"})
    for name in body.clear:
        if name not in NULLABLE_FIELDS:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, f"{name} cannot be cleared"
            )
        patch[name] = None
    if not patch:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Nothing to update")
    try:
        return _out(db.update_work_history(entry_id, patch))
    except DbError as e:
        raise _http(e) from e


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(entry_id: str, db: Db) -> Response:
    try:
        deleted = db.delete_work_history(entry_id)
    except DbError as e:
        raise _http(e) from e
    if not deleted:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Work history entry not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
