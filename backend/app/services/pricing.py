"""F4: propose a price quote from evidence, or leave it blank.

Deterministic. Every number in the quote traces to a listed piece of
evidence: the job's own rate or budget, the operator's default rate, and the
budget bands of the past projects F2 said were worth citing. With no
evidence at all, `amount` is None and the rationale says so (R8).
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from app.models.job import Conflict, ParsedJob, PaymentType
from app.models.proposal import Profile, Quote, QuoteEvidence

BAND = re.compile(r"\$?\s*([\d,]+(?:\.\d+)?)\s*([kK])?")


def _money(text: str) -> list[Decimal]:
    out = []
    for num, k in BAND.findall(text):
        value = Decimal(num.replace(",", ""))
        if k:
            value *= 1000
        out.append(value)
    return out


def _round(value: Decimal) -> Decimal:
    return value.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def propose_quote(
    job: ParsedJob,
    profile: Profile,
    cited_history: list[dict[str, Any]],
    conflicts: list[Conflict] | None = None,
) -> Quote:
    """The quote plus, when F1 found Upwork and the client disagreeing on
    the payment model, that disagreement as evidence and in the rationale."""
    quote = _propose(job, profile, cited_history)
    clash = next((c for c in conflicts or [] if c.field == "payment_type"), None)
    if clash:
        quote.evidence.insert(
            0,
            QuoteEvidence(
                source="job",
                detail=(
                    f"Upwork says {clash.upwork_value}; the description says "
                    f"{clash.description_value}"
                ),
            ),
        )
        quote.rationale += (
            " Note: the client's own text describes a different payment model "
            "from Upwork's field — consider quoting that way instead."
        )
    return quote


def _propose(
    job: ParsedJob, profile: Profile, cited_history: list[dict[str, Any]]
) -> Quote:
    e = job.engagement
    evidence: list[QuoteEvidence] = []
    model = e.payment_type.value if e.payment_type else None

    if e.payment_type == PaymentType.HOURLY:
        if e.hourly_rate_min is not None and e.hourly_rate_max is not None:
            evidence.append(
                QuoteEvidence(
                    source="job",
                    detail=(
                        f"Client's hourly range "
                        f"${e.hourly_rate_min}–${e.hourly_rate_max}"
                    ),
                )
            )
        if job.activity.bid_avg is not None:
            evidence.append(
                QuoteEvidence(
                    source="job",
                    detail=f"Bids so far: avg ${job.activity.bid_avg}/hr "
                    f"(high ${job.activity.bid_high}, low ${job.activity.bid_low})",
                )
            )
        if profile.default_hourly_rate is not None:
            evidence.append(
                QuoteEvidence(
                    source="profile",
                    detail=f"Your default rate ${profile.default_hourly_rate:.2f}/hr",
                )
            )
            rate = profile.default_hourly_rate
            if e.hourly_rate_max is not None and rate > e.hourly_rate_max:
                return Quote(
                    model="hourly",
                    amount=_round(rate),
                    rationale=(
                        f"Your default rate (${rate:.2f}/hr) is above the client's "
                        f"range (up to ${e.hourly_rate_max}/hr). Quoted at your "
                        "rate; decide whether to meet the range or justify the gap."
                    ),
                    evidence=evidence,
                )
            return Quote(
                model="hourly",
                amount=_round(rate),
                rationale="Your default hourly rate, within the client's range.",
                evidence=evidence,
            )
        if e.hourly_rate_max is not None:
            return Quote(
                model="hourly",
                amount=None,
                rationale=(
                    "No default hourly rate in your profile. The client's range "
                    "is shown; enter the rate yourself."
                ),
                evidence=evidence,
            )

    if e.payment_type == PaymentType.FIXED and e.fixed_budget is not None:
        evidence.append(
            QuoteEvidence(source="job", detail=f"Client's budget ${e.fixed_budget}")
        )

    bands: list[Decimal] = []
    for entry in cited_history:
        band = entry.get("budget_band")
        if band:
            values = _money(band)
            if values:
                bands.append(max(values))
                evidence.append(
                    QuoteEvidence(
                        source="history",
                        detail=f"{entry.get('name')}: budget band {band}",
                    )
                )
    if profile.fixed_price_range:
        evidence.append(
            QuoteEvidence(
                source="profile",
                detail=f"Your typical fixed-price range {profile.fixed_price_range}",
            )
        )

    if model == "fixed" or (model is None and bands):
        if bands:
            typical = _round(sum(bands) / len(bands))
            return Quote(
                model="fixed",
                amount=typical,
                rationale=(
                    f"Midpoint of the upper bands of {len(bands)} comparable past "
                    "project(s). Adjust for this job's scope."
                ),
                evidence=evidence,
            )
        if e.fixed_budget is not None:
            return Quote(
                model="fixed",
                amount=None,
                rationale=(
                    "No comparable past pricing. The client's budget is shown; "
                    "enter the amount yourself."
                ),
                evidence=evidence,
            )

    return Quote(
        model=model,  # type: ignore[arg-type]
        amount=None,
        rationale="No comparable pricing — enter the quote yourself.",
        evidence=evidence,
    )
