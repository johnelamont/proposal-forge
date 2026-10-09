"""Proposal drafting (F3) and price quote (F4).

Drafts are versions: every AI draft, refine or operator edit appends a
`DraftVersion`; nothing is overwritten. Copying is approval (R1) and is
recorded as a `ProposalApproval` with the hash of the copied text (R2).
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.models.job import AiFailure

# --- profile ------------------------------------------------------------------


class ProfileIn(BaseModel):
    signature_name: str = Field(default="", max_length=120)
    positioning: str = Field(default="", max_length=4000)
    greeting: str = Field(default="Hi,", max_length=80)
    sign_off: str = Field(default="Kind Regards,", max_length=80)
    tone_notes: str = Field(default="", max_length=2000)
    never_claim: list[str] = Field(default_factory=list, max_length=20)
    default_hourly_rate: Decimal | None = Field(default=None, ge=0)
    fixed_price_range: str | None = Field(default=None, max_length=80)


class Profile(ProfileIn):
    user_id: str
    created_at: str
    updated_at: str

    @property
    def ready(self) -> bool:
        """Drafting needs a name to sign with and something to say."""
        return bool(self.signature_name.strip()) and bool(self.positioning.strip())


# --- sections -----------------------------------------------------------------


class Answer(BaseModel):
    question: str
    answer: str


class QuoteEvidence(BaseModel):
    source: str
    detail: str


class Quote(BaseModel):
    """F4. `amount` is null when there is no comparable pricing (never invented)."""

    model: Literal["hourly", "fixed"] | None
    amount: Decimal | None
    rationale: str
    evidence: list[QuoteEvidence] = Field(default_factory=list)


class Sections(BaseModel):
    cover_letter: str | None
    answers: list[Answer] = Field(default_factory=list)
    quote: Quote | None = None


# --- Claude output ------------------------------------------------------------


class DraftConfidence(BaseModel):
    cover_letter: float = Field(ge=0, le=1)
    answers: float = Field(ge=0, le=1)


class DraftOutput(BaseModel):
    """What Claude returns for a full draft. Framed (greeting, sign-off) and
    checked (never-claim phrases) by the backend afterwards."""

    cover_letter: str
    answers: list[Answer]
    confidence: DraftConfidence


class RefineOutput(BaseModel):
    content: str
    confidence: float = Field(ge=0, le=1)


# --- versions and approvals -----------------------------------------------------

Source = Literal["ai", "refine", "edit", "manual"]
SectionName = Literal["cover_letter", "answer", "quote", "all"]


class AiMeta(BaseModel):
    model: str | None = None
    confidence: dict[str, float] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    failure: AiFailure | None = None


class DraftVersion(BaseModel):
    id: str
    proposal_id: str
    version: int
    source: Source
    sections: Sections
    ai_meta: AiMeta | None
    created_at: str


class ProposalApproval(BaseModel):
    id: str
    proposal_id: str
    draft_version_id: str
    section: SectionName
    section_index: int | None
    content_hash: str
    approved_by: str
    approved_at: str


class Proposal(BaseModel):
    id: str
    job_post_id: str
    status: Literal["draft", "submitted", "won", "lost", "withdrawn"]
    extra_questions: list[str]
    current_version_id: str | None
    created_at: str
    updated_at: str


class ProposalOut(BaseModel):
    proposal: Proposal
    versions: list[DraftVersion]
    approvals: list[ProposalApproval]
    job_title: str | None


# --- requests -------------------------------------------------------------------


class CreateProposalRequest(BaseModel):
    job_post_id: str
    form_paste: str | None = Field(default=None, max_length=20_000)


class QuestionsRequest(BaseModel):
    form_paste: str = Field(min_length=1, max_length=20_000)


class RefineRequest(BaseModel):
    section: Literal["cover_letter", "answer"]
    index: int | None = None
    instruction: str = Field(min_length=1, max_length=1000)


class EditRequest(BaseModel):
    section: Literal["cover_letter", "answer", "quote"]
    index: int | None = None
    content: str = Field(max_length=20_000)
    quote_amount: Decimal | None = Field(default=None, ge=0)


class ApprovalRequest(BaseModel):
    draft_version_id: str
    section: SectionName
    section_index: int | None = None
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
