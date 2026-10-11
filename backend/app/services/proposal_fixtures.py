"""Small builders for draft versions and approvals, used by tests and by the
developer smoke scripts. Not used by the application itself."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.models.proposal import Quote, Sections


def approved_version(
    cover_letter: str,
    *,
    quote_amount: str | None = None,
    quote_model: str = "hourly",
    version_id: str = "v1",
) -> Sections:
    quote = (
        Quote(
            model=quote_model,  # type: ignore[arg-type]
            amount=Decimal(quote_amount),
            rationale="test",
            evidence=[],
        )
        if quote_amount is not None
        else None
    )
    return Sections(cover_letter=cover_letter, answers=[], quote=quote)


def approvals_for(
    cover_letter: str, version_id: str = "v1"
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sections = approved_version(cover_letter, quote_amount="65", version_id=version_id)
    versions = [
        {"id": version_id, "version": 1, "sections": sections.model_dump(mode="json")}
    ]
    approvals = [
        {
            "draft_version_id": version_id,
            "section": "all",
            "approved_at": "2026-10-11T10:00:00+00:00",
        }
    ]
    return versions, approvals
