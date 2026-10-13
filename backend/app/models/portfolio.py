"""F7 models: the selection, the manifest (exactly what the PDF says), the
preview, the export request and the export record."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

MAX_ENTRIES = 40
MONTH = r"^\d{4}-\d{2}$"


class Selection(BaseModel):
    """What the operator ticked. `from`/`to` filter on an entry's end month
    (or start month when it has no end)."""

    model_config = ConfigDict(populate_by_name=True)

    entry_ids: list[str] = Field(min_length=1, max_length=MAX_ENTRIES)
    title: str | None = Field(default=None, max_length=120)
    from_: str | None = Field(default=None, alias="from", pattern=MONTH)
    to: str | None = Field(default=None, pattern=MONTH)
    include_results: bool = True
    include_tech: bool = True


class PortfolioEntryOption(BaseModel):
    """A work-history entry as offered for selection."""

    id: str
    name: str
    vertical: str | None
    started: str | None
    ended: str | None
    may_name_client: bool
    has_client_name: bool


class ManifestEntry(BaseModel):
    id: str
    name: str
    period: str | None
    role: str | None
    vertical: str | None
    # "for Northwind Mortgage" only when may_name_client; else
    # "for a mortgage brokerage client"; None when neither is known.
    client_line: str | None
    summary: str
    tech_stack: list[str]
    outcomes: list[str]


class TechCount(BaseModel):
    name: str
    count: int


class Results(BaseModel):
    """Counts only; industry names only. Never job titles or Lead data."""

    won: int
    lost: int
    withdrawn: int
    industries_won: list[str]


class Manifest(BaseModel):
    """Everything the PDF renders, in order. Its canonical JSON is hashed and
    that hash is what the operator approves."""

    title: str
    operator: str
    positioning: str
    generated_on: str
    entries: list[ManifestEntry]
    tech: list[TechCount]
    results: Results | None
    footer: str


class PreviewOut(BaseModel):
    manifest: Manifest
    content_hash: str
    pdf_base64: str
    page_count: int
    warnings: list[str]


class ExportRequest(BaseModel):
    selection: Selection
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ExportRecord(BaseModel):
    id: str
    content_hash: str
    pdf_hash: str
    selection: dict[str, Any]
    entry_count: int
    page_count: int
    exported_by: str
    exported_at: str
