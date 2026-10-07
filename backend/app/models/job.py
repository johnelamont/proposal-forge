"""Parse result for an Upwork job post (F1). Shape per docs/F1_JOB_PARSING.md.

Every field that comes from the paste is nullable: absence is `None`, never a
default that looks like data.
"""

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class HoursPerWeek(StrEnum):
    LT30 = "lt30"
    GT30 = "gt30"


class PaymentType(StrEnum):
    HOURLY = "hourly"
    FIXED = "fixed"


class Duration(StrEnum):
    LT1M = "lt1m"
    M1_3 = "1to3m"
    M3_6 = "3to6m"
    GT6M = "gt6m"


class ExperienceLevel(StrEnum):
    ENTRY = "entry"
    INTERMEDIATE = "intermediate"
    EXPERT = "expert"


class Engagement(BaseModel):
    hours_per_week: HoursPerWeek | None = None
    hours_per_week_raw: str | None = None
    payment_type: PaymentType | None = None
    duration: Duration | None = None
    duration_raw: str | None = None
    experience_level: ExperienceLevel | None = None
    hourly_rate_min: Decimal | None = None
    hourly_rate_max: Decimal | None = None
    fixed_budget: Decimal | None = None
    project_type: Literal["ongoing", "one_time"] | None = None
    contract_to_hire: bool = False


class Activity(BaseModel):
    proposals_min: int | None = None
    proposals_max: int | None = None
    last_viewed_raw: str | None = None
    interviewing: int | None = None
    invites_sent: int | None = None
    unanswered_invites: int | None = None
    bid_high: Decimal | None = None
    bid_avg: Decimal | None = None
    bid_low: Decimal | None = None


class Connects(BaseModel):
    required: int | None = None
    available: int | None = None


class Client(BaseModel):
    """Statistics about the client. Parsed by regex; never sent to Claude."""

    payment_verified: bool | None = None
    phone_verified: bool | None = None
    rating: Decimal | None = None
    review_count: int | None = None
    country: str | None = None
    city: str | None = None
    jobs_posted: int | None = None
    hire_rate_pct: int | None = None
    open_jobs: int | None = None
    total_spent: Decimal | None = None
    hires: int | None = None
    active_hires: int | None = None
    avg_hourly_paid: Decimal | None = None
    hours_billed: int | None = None
    industry: str | None = None
    company_size: str | None = None
    member_since: str | None = None
    recent_history_count: int | None = None


class Question(BaseModel):
    text: str
    source: Literal["upwork", "description"]


class ParsedJob(BaseModel):
    """Output of the deterministic layer. No AI involved."""

    source_format: Literal["desktop", "mobile", "unknown"] = "unknown"
    title: str | None = None
    posted_ago_raw: str | None = None
    location_restriction: str | None = None
    upwork_job_id: str | None = None
    description: str = ""
    engagement: Engagement = Field(default_factory=Engagement)
    skills: list[str] = Field(default_factory=list)
    preferred_qualifications: dict[str, str] = Field(default_factory=dict)
    activity: Activity = Field(default_factory=Activity)
    connects: Connects = Field(default_factory=Connects)
    client: Client = Field(default_factory=Client)
    questions: list[Question] = Field(default_factory=list)
    unparsed_lines: list[str] = Field(default_factory=list)

    @property
    def recognised(self) -> bool:
        """Whether the text looked like an Upwork job post at all."""
        return bool(self.description) or bool(self.skills) or bool(self.title)


# ---------------------------------------------------------------------------
# Claude layer
# ---------------------------------------------------------------------------


class BudgetStatement(BaseModel):
    model: Literal["hourly", "fixed", "unstated"]
    amount_raw: str | None = None
    milestones: list[str] = Field(default_factory=list)


class SensitiveDataDomain(BaseModel):
    flag: bool
    reason: str | None = None


class Confidence(BaseModel):
    """0.0-1.0 per extracted field. Display-only; drives no automation."""

    one_line: float = Field(ge=0, le=1)
    deliverables: float = Field(ge=0, le=1)
    requirements: float = Field(ge=0, le=1)
    questions_in_description: float = Field(ge=0, le=1)
    budget_statement: float = Field(ge=0, le=1)
    timeline_statement: float = Field(ge=0, le=1)
    red_flags: float = Field(ge=0, le=1)
    sensitive_data_domain: float = Field(ge=0, le=1)


class AiReading(BaseModel):
    """What Claude extracts from the description. Schema-validated on return."""

    one_line: str
    deliverables: list[str]
    requirements: list[str]
    questions_in_description: list[str]
    budget_statement: BudgetStatement | None
    timeline_statement: str | None
    red_flags: list[str]
    sensitive_data_domain: SensitiveDataDomain
    confidence: Confidence


class AiFailure(BaseModel):
    """Why the Claude layer produced nothing. Always shown to the operator."""

    kind: Literal["error", "empty", "malformed", "refusal", "skipped"]
    message: str


class Conflict(BaseModel):
    field: str
    upwork_value: str | None
    description_value: str | None
    evidence: str | None = None


ParseStatus = Literal["ok", "ai_failed", "unrecognised"]


class JobAnalysis(BaseModel):
    """Both layers merged: what the API returns and what gets stored."""

    parsed: ParsedJob
    ai: AiReading | None
    ai_failure: AiFailure | None
    conflicts: list[Conflict]
    parse_status: ParseStatus
