"""Work history (F5): past projects, extracted from dropped files or typed in.

The operator confirms and edits every extraction before it is saved. The
columns hold the operator's version; `ai_extraction` keeps Claude's original
reading for provenance.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from app.models.job import AiFailure


class Complexity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


# --- files ------------------------------------------------------------------


class DroppedFile(BaseModel):
    """One file the operator dropped. Text only; the browser reads it."""

    name: str = Field(min_length=1, max_length=255)
    content: str = Field(max_length=400_000)


class RefusedFile(BaseModel):
    name: str
    reason: str


class AcceptedFile(BaseModel):
    name: str
    size: int
    sha256: str


class SourceFile(AcceptedFile):
    """What is stored: the accepted file plus its text, for re-extraction."""

    content: str


# --- Claude output ----------------------------------------------------------


class ExtractionConfidence(BaseModel):
    name: float = Field(ge=0, le=1)
    summary: float = Field(ge=0, le=1)
    tech_stack: float = Field(ge=0, le=1)
    vertical: float = Field(ge=0, le=1)
    project_type: float = Field(ge=0, le=1)
    complexity: float = Field(ge=0, le=1)
    role: float = Field(ge=0, le=1)
    outcomes: float = Field(ge=0, le=1)
    client_name_detected: float = Field(ge=0, le=1)
    duration_hint: float = Field(ge=0, le=1)


class Extraction(BaseModel):
    """Claude's reading of the dropped files. Prefills the form; never saved
    as-is."""

    name: str
    summary: str
    tech_stack: list[str]
    vertical: str | None
    project_type: str | None
    complexity: Complexity
    complexity_reason: str
    role: str | None
    outcomes: list[str]
    client_name_detected: str | None
    duration_hint: str | None
    confidence: ExtractionConfidence


# --- API --------------------------------------------------------------------


class ExtractRequest(BaseModel):
    files: list[DroppedFile] = Field(min_length=1, max_length=10)


class ExtractResponse(BaseModel):
    accepted: list[AcceptedFile]
    refused: list[RefusedFile]
    extraction: Extraction | None
    failure: AiFailure | None


class WorkHistoryIn(BaseModel):
    """The operator's record. Everything optional except a name."""

    name: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=4000)
    tech_stack: list[str] = Field(default_factory=list, max_length=40)
    vertical: str | None = Field(default=None, max_length=120)
    project_type: str | None = Field(default=None, max_length=120)
    complexity: Complexity | None = None
    role: str | None = Field(default=None, max_length=120)
    outcomes: list[str] = Field(default_factory=list, max_length=20)
    client_name: str | None = Field(default=None, max_length=200)
    may_name_client: bool = False
    budget_band: str | None = Field(default=None, max_length=60)
    started: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    ended: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    source_files: list[DroppedFile] = Field(default_factory=list, max_length=10)
    ai_extraction: Extraction | None = None


class WorkHistoryPatch(BaseModel):
    """Partial update; `None` means "leave unchanged" (use the explicit
    clearing fields to null a value)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    tech_stack: list[str] | None = Field(default=None, max_length=40)
    vertical: str | None = Field(default=None, max_length=120)
    project_type: str | None = Field(default=None, max_length=120)
    complexity: Complexity | None = None
    role: str | None = Field(default=None, max_length=120)
    outcomes: list[str] | None = Field(default=None, max_length=20)
    client_name: str | None = Field(default=None, max_length=200)
    may_name_client: bool | None = None
    budget_band: str | None = Field(default=None, max_length=60)
    started: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    ended: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}$")
    clear: list[str] = Field(
        default_factory=list,
        description="Names of nullable fields to set to null.",
    )


class WorkHistoryOut(BaseModel):
    id: str
    name: str
    summary: str
    tech_stack: list[str]
    vertical: str | None
    project_type: str | None
    complexity: Complexity | None
    role: str | None
    outcomes: list[str]
    client_name: str | None
    may_name_client: bool
    budget_band: str | None
    started: str | None
    ended: str | None
    source_files: list[SourceFile]
    ai_extraction: Extraction | None
    created_at: str
    updated_at: str


class WorkHistorySummary(BaseModel):
    id: str
    name: str
    vertical: str | None
    tech_stack: list[str]
    complexity: Complexity | None
    may_name_client: bool
    ended: str | None
    updated_at: str
