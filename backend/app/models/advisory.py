"""Wheelhouse advisory (F2): how a parsed job compares with past work.

Two layers, like F1: `Comparable` rows come from deterministic matching
against `work_history`; `AdvisoryReading` is Claude's verdict on those
comparables. Until F8 records outcomes, the evidence is work history only.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.job import AiFailure
from app.models.work_history import Complexity

EvidenceLevel = Literal["none_history", "none_comparable", "thin", "some", "strong"]
Fit = Literal["strong", "partial", "weak", "none"]


class Comparable(BaseModel):
    """A work-history entry that resembles the job, and why."""

    entry_id: str
    name: str
    score: float
    shared_tech: list[str]
    shared_terms: list[str]
    vertical: str | None
    project_type: str | None
    complexity: Complexity | None


class MatchStrength(BaseModel):
    level: EvidenceLevel
    comparable_count: int
    history_count: int
    label: str


class Citation(BaseModel):
    entry_id: str
    name: str
    why: str


class AdvisoryConfidence(BaseModel):
    fit: float = Field(ge=0, le=1)
    reasons: float = Field(ge=0, le=1)
    gaps: float = Field(ge=0, le=1)
    cite: float = Field(ge=0, le=1)
    angle: float = Field(ge=0, le=1)


class AdvisoryReading(BaseModel):
    """Claude's verdict. Only produced when at least one comparable exists."""

    fit: Fit
    reasons: list[str]
    gaps: list[str]
    cite: list[Citation]
    angle: str
    confidence: AdvisoryConfidence


class Advisory(BaseModel):
    comparables: list[Comparable]
    match_strength: MatchStrength
    reading: AdvisoryReading | None
    failure: AiFailure | None
    outcomes_note: str = (
        "Win/loss evidence appears once proposal outcomes are recorded (F8)."
    )
