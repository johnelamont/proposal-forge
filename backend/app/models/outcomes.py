"""F8 models: the inbound outcome contract, history, index, queue, secret.

Contract: docs/ZOHO_INTEGRATION.md → Outcome in. The `lead` allow-list is
enforced here with `extra="forbid"` (Rule 5): a payload carrying any other
Lead field is rejected before it reaches the database.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Outcome = Literal["won", "lost", "withdrawn"]
LostReason = Literal["hired_other", "job_closed", "junk_lead", "not_qualified"]

# The only Lead fields Zoho may send back (docs/ZOHO_INTEGRATION.md). Kept as a
# tuple so the test suite can assert the list verbatim against the Deluge helper.
LEAD_ALLOW_LIST = (
    "Industry",
    "Job_Type",
    "Tools",
    "Rate_Type",
    "Hourly_Rate",
    "Upwork_Fixed_Price",
    "Budget",
    "Skills_Required",
    "Deliverables",
    "Client_s_Desired_Experience_Level",
)


class LeadSnapshot(BaseModel):
    """Allow-listed Lead values as they stand when the outcome is recorded."""

    model_config = ConfigDict(extra="forbid")

    Industry: str | None = Field(default=None, max_length=120)
    Job_Type: str | None = Field(default=None, max_length=120)
    Tools: str | None = Field(default=None, max_length=255)
    Rate_Type: str | None = Field(default=None, max_length=40)
    Hourly_Rate: Decimal | None = Field(default=None, ge=0)
    Upwork_Fixed_Price: Decimal | None = Field(default=None, ge=0)
    Budget: Decimal | None = Field(default=None, ge=0)
    Skills_Required: str | None = Field(default=None, max_length=1000)
    Deliverables: str | None = Field(default=None, max_length=8000)
    Client_s_Desired_Experience_Level: str | None = Field(default=None, max_length=40)


class OutcomeIn(BaseModel):
    """What Zoho posts. Validation failures are a 400 with the message."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["1.0"]
    upwork_job_id: str = Field(min_length=1, max_length=64)
    zoho_lead_id: str | None = Field(default=None, max_length=40)
    outcome: Outcome
    lost_reason: LostReason | None = None
    decided_at: datetime | None = None
    lead: LeadSnapshot = Field(default_factory=LeadSnapshot)

    @model_validator(mode="after")
    def _reason_only_with_lost(self) -> OutcomeIn:
        if self.outcome == "lost" and self.lost_reason is None:
            raise ValueError("lost_reason is required when outcome is lost")
        if self.outcome != "lost" and self.lost_reason is not None:
            raise ValueError("lost_reason is only valid when outcome is lost")
        return self


class OutcomeResult(BaseModel):
    """The answer Zoho's helper writes to Forge_Sync."""

    code: Literal[200, 202]
    message: str
    proposal_id: str | None = None
    outcome: Outcome | None = None
    indexed: bool = False
    queued: bool = False
    duplicate: bool = False


class OutcomeRecord(BaseModel):
    id: str
    proposal_id: str
    outcome: Outcome
    lost_reason: LostReason | None
    decided_at: str | None
    zoho_lead_id: str | None
    lead: dict[str, Any]
    source: Literal["zoho", "manual_match"]
    received_at: str


class RagIndexRow(BaseModel):
    proposal_id: str
    outcome: Outcome
    lost_reason: LostReason | None
    industry: str | None
    job_type: str | None
    tools: str | None
    rate_type: str | None
    hourly_rate: Decimal | None
    fixed_price: Decimal | None
    budget: Decimal | None
    budget_band: str | None
    quote_model: str | None
    quote_amount: Decimal | None
    job_title: str | None
    skills: list[str]
    proposal_excerpt: str | None
    decided_at: str | None
    archived: bool
    indexed_at: str


class ProposalOutcomes(BaseModel):
    status: str
    history: list[OutcomeRecord]
    index: RagIndexRow | None
    zoho_lead_id: str | None
    lead_url: str | None
    submitted_at: str | None
    stale_after_days: int
    stale: bool


class ArchiveIn(BaseModel):
    archived: bool


class QueuedOutcome(BaseModel):
    id: str
    upwork_job_id: str
    zoho_lead_id: str | None
    payload: dict[str, Any]
    received_at: str
    resolved_at: str | None
    resolved_proposal_id: str | None
    dismissed_at: str | None


class MatchIn(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=64)


class SecretStatus(BaseModel):
    exists: bool
    created_at: str | None = None
    last_used_at: str | None = None
    endpoint_url: str


class SecretCreated(SecretStatus):
    """Returned once, on generate or rotate. The plaintext is never stored."""

    secret: str


class AttentionItem(BaseModel):
    proposal_id: str
    job_title: str | None
    since: str | None


class Attention(BaseModel):
    """The home screen's strip: what needs the operator."""

    lead_failed: list[AttentionItem]
    queued_outcomes: int
    stale_submitted: list[AttentionItem]
    stale_after_days: int
