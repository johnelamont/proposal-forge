"""F7 routes: selectable entries, preview, approve-and-download, export log.

Approve re-renders from current data and compares the manifest hash with
the one the operator previewed; a mismatch is a 409 and nothing is exported.
The export row is written before the file is returned (R1, R2).
"""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status

from app.core.deps import Db
from app.models.portfolio import (
    ExportRecord,
    ExportRequest,
    Manifest,
    PortfolioEntryOption,
    PreviewOut,
    Selection,
)
from app.routes.proposals import _require_profile
from app.services.db import DbError, UserDb
from app.services.portfolio import (
    PortfolioError,
    build_manifest,
    manifest_hash,
    pdf_hash,
    render_pdf,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])
log = logging.getLogger(__name__)


def _http(e: DbError) -> HTTPException:
    return HTTPException(e.status_code, e.detail)


def _build(db: UserDb, selection: Selection) -> tuple[Manifest, list[str], bytes, int]:
    profile = _require_profile(db)
    try:
        entries = db.list_work_history_for_portfolio()
        index_rows = db.list_rag_index_for_matching()
    except DbError as e:
        raise _http(e) from e
    try:
        manifest, warnings = build_manifest(
            profile, entries, index_rows, selection, datetime.now(UTC).date()
        )
    except PortfolioError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from e
    try:
        pdf, pages = render_pdf(manifest)
    except Exception as e:  # noqa: BLE001 — any renderer fault is R8: halt, report
        log.exception("portfolio render failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            f"Could not generate the PDF; nothing was exported ({type(e).__name__}).",
        ) from e
    return manifest, warnings, pdf, pages


@router.get("/entries", response_model=list[PortfolioEntryOption])
def entries(db: Db) -> list[PortfolioEntryOption]:
    try:
        rows = db.list_work_history_for_portfolio()
    except DbError as e:
        raise _http(e) from e
    return [
        PortfolioEntryOption(
            id=r["id"],
            name=r["name"],
            vertical=r.get("vertical"),
            started=r.get("started"),
            ended=r.get("ended"),
            may_name_client=bool(r.get("may_name_client")),
            has_client_name=bool((r.get("client_name") or "").strip()),
        )
        for r in rows
    ]


@router.post("/preview", response_model=PreviewOut)
def preview(selection: Selection, db: Db) -> PreviewOut:
    manifest, warnings, pdf, pages = _build(db, selection)
    return PreviewOut(
        manifest=manifest,
        content_hash=manifest_hash(manifest),
        pdf_base64=base64.b64encode(pdf).decode("ascii"),
        page_count=pages,
        warnings=warnings,
    )


@router.post("/exports")
def approve_and_download(body: ExportRequest, db: Db) -> Response:
    """The affirmative action. Logged before the file leaves."""
    manifest, _, pdf, pages = _build(db, body.selection)
    current = manifest_hash(manifest)
    if current != body.content_hash:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The document changed since you previewed it (an entry, a naming flag "
            "or an outcome). Preview again, then approve.",
        )
    digest = pdf_hash(pdf)
    try:
        db.insert_portfolio_export(
            {
                "content_hash": current,
                "pdf_hash": digest,
                "selection": body.selection.model_dump(mode="json", by_alias=True),
                "entry_count": len(manifest.entries),
                "page_count": pages,
            }
        )
    except DbError as e:
        # No record → no file (R2).
        raise HTTPException(
            e.status_code, f"Export not recorded, so not downloaded: {e.detail}"
        ) from e
    filename = f"portfolio-{manifest.generated_on}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Content-Hash": current,
            "X-Pdf-Hash": digest,
            "X-Page-Count": str(pages),
        },
    )


@router.get("/exports", response_model=list[ExportRecord])
def export_log(db: Db) -> list[ExportRecord]:
    try:
        rows: list[dict[str, Any]] = db.list_portfolio_exports()
    except DbError as e:
        raise _http(e) from e
    return [ExportRecord.model_validate(r) for r in rows]
