"""F6 models: connection status, Lead fields, preview, attempts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.job import AiFailure


class ConnectionStatus(BaseModel):
    configured: bool
    connected: bool
    connected_at: str | None = None
    scopes: list[str] = Field(default_factory=list)
    last_used_at: str | None = None


class ConnectStart(BaseModel):
    authorize_url: str
    state: str


class CompleteRequest(BaseModel):
    code: str = Field(min_length=1, max_length=512)
    state: str = Field(min_length=1, max_length=128)


class LeadFieldsIn(BaseModel):
    """The operator's confirmed values. Saving them clears the AI flags."""

    industry: str | None = Field(default=None, max_length=120)
    job_type: str | None = Field(default=None, max_length=120)
    tools: str | None = Field(default=None, max_length=255)
    proposal_link: str | None = Field(default=None, max_length=500)
    by_invitation: bool = False


class LeadFields(LeadFieldsIn):
    confirmed_at: str | None = None


class ClassificationConfidence(BaseModel):
    industry: float = Field(ge=0, le=1)
    job_type: float = Field(ge=0, le=1)
    tools: float = Field(ge=0, le=1)


class Classification(BaseModel):
    """Claude's picklist mapping. Built with Literal types from picklists.json
    at runtime (see lead_classifier.classification_schema)."""

    industry: str
    job_type: str
    tools: str = Field(max_length=255)
    confidence: ClassificationConfidence


class FieldFlag(BaseModel):
    field: Literal["Industry", "Job_Type", "Tools"]
    reason: str
    confidence: float | None


class ChecklistItem(BaseModel):
    key: str
    label: str
    ok: bool


class LeadPreview(BaseModel):
    payload: dict[str, Any]
    truncations: list[str]
    flags: list[FieldFlag]
    checklist: list[ChecklistItem]
    ready: bool
    classification: Classification | None
    classification_failure: AiFailure | None
    lead_fields: LeadFields | None
    picklists: dict[str, list[str]]
    thresholds: dict[str, float]


class LeadAttempt(BaseModel):
    id: str
    proposal_id: str
    payload_hash: str
    response_status: int | None
    zoho_lead_id: str | None
    action: str | None
    error: str | None
    attempted_by: str
    attempted_at: str


class CreateLeadResult(BaseModel):
    ok: bool
    zoho_lead_id: str | None
    action: str | None
    error: str | None
    reconnect: bool = False
    attempt: LeadAttempt
