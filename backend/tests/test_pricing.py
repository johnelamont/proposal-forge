"""F4: every number traces to evidence; no evidence → no number."""

from decimal import Decimal

from app.models.job import PaymentType
from app.models.proposal import Profile
from app.services.job_parser import parse_job_post
from app.services.pricing import propose_quote


def profile(**overrides) -> Profile:
    base = {
        "user_id": "u",
        "created_at": "t",
        "updated_at": "t",
        "signature_name": "A. Person",
        "positioning": "Independent consultant.",
    }
    return Profile.model_validate({**base, **overrides})


def test_hourly_within_client_range_uses_default_rate(desktop_hourly):
    job = parse_job_post(desktop_hourly)  # $25–$65/hr
    q = propose_quote(job, profile(default_hourly_rate=Decimal("60")), [])
    assert q.model == "hourly" and q.amount == Decimal("60")
    assert "within the client's range" in q.rationale
    assert any("$25.00–$65.00" in e.detail for e in q.evidence)
    assert any(e.source == "profile" for e in q.evidence)


def test_hourly_above_client_range_is_flagged_not_clamped(desktop_conflict):
    job = parse_job_post(desktop_conflict)  # $9–$21/hr
    q = propose_quote(job, profile(default_hourly_rate=Decimal("85")), [])
    assert q.amount == Decimal("85")
    assert "above the client's range" in q.rationale


def test_hourly_without_default_rate_leaves_amount_blank(desktop_hourly):
    job = parse_job_post(desktop_hourly)
    q = propose_quote(job, profile(), [])
    assert q.model == "hourly" and q.amount is None
    assert "enter the rate yourself" in q.rationale
    assert any(e.source == "job" for e in q.evidence)  # the range is still shown


def test_fixed_from_cited_history_bands(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    job.engagement.payment_type = PaymentType.FIXED
    job.engagement.fixed_budget = Decimal("3000")
    cited = [
        {"name": "A", "budget_band": "$1–5K"},
        {"name": "B", "budget_band": "$5K-$10K"},
        {"name": "C", "budget_band": None},
    ]
    q = propose_quote(job, profile(), cited)
    assert q.model == "fixed" and q.amount == Decimal("7500")  # mean of 5000, 10000
    assert sum(1 for e in q.evidence if e.source == "history") == 2
    assert any("$3000" in e.detail for e in e_list(q))


def e_list(q):
    return q.evidence


def test_no_evidence_at_all_is_blank(mobile_relayed):
    job = parse_job_post(mobile_relayed)  # hourly, no range on mobile
    q = propose_quote(job, profile(), [])
    assert q.amount is None
    assert "enter the quote yourself" in q.rationale


def test_payment_model_conflict_is_carried_into_the_quote(desktop_conflict):
    from app.models.job import Conflict

    job = parse_job_post(desktop_conflict)
    clash = Conflict(
        field="payment_type",
        upwork_value="hourly $9.00-$21.00/hr",
        description_value="fixed",
    )
    q = propose_quote(job, profile(default_hourly_rate=Decimal("65")), [], [clash])
    assert q.evidence[0].detail.startswith("Upwork says hourly")
    assert "different payment model" in q.rationale
    assert "$65.00/hr" in q.rationale  # two-decimal money formatting
