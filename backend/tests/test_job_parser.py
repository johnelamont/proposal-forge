"""Deterministic parser against the three real (redacted) pastes.

Each test pins the values a reviewer can check against the fixture by eye.
The R5 tests assert that client statistics and history never end up in the
text destined for Claude.
"""

from decimal import Decimal

import pytest

from app.services.job_analysis import reading_input
from app.services.job_parser import parse_job_post

CLIENT_SECTION_MARKERS = [
    "Payment method",
    "hire rate",
    "total spent",
    "Member since",
    "Bid range",
    "Last viewed by client",
    "recent history",
    "Freelancer A.",
    "Alex",
]


# --- desktop, hourly, established client ------------------------------------


def test_desktop_hourly_header_and_link(desktop_hourly):
    job = parse_job_post(desktop_hourly)
    assert job.source_format == "desktop"
    assert job.title == "Zoho Consulting"
    assert job.posted_ago_raw == "Posted 8 hours ago"
    assert job.location_restriction == "Only freelancers located in the U.S. may apply."
    assert job.upwork_job_id == "~021000000000000000001"


def test_desktop_hourly_engagement(desktop_hourly):
    eng = parse_job_post(desktop_hourly).engagement
    assert eng.hours_per_week == "gt30"
    assert eng.hours_per_week_raw == "More than 30 hrs/week"
    assert eng.payment_type == "hourly"
    assert eng.duration == "gt6m"
    assert eng.experience_level == "intermediate"
    assert eng.hourly_rate_min == Decimal("25.00")
    assert eng.hourly_rate_max == Decimal("65.00")
    assert eng.fixed_budget is None
    assert eng.project_type == "ongoing"
    assert eng.contract_to_hire is False


def test_desktop_hourly_skills_activity_connects(desktop_hourly):
    job = parse_job_post(desktop_hourly)
    assert job.skills == ["Zoho CRM", "Zoho Creator"]
    assert job.preferred_qualifications == {}
    act = job.activity
    assert (act.proposals_min, act.proposals_max) == (20, 50)
    assert act.last_viewed_raw == "4 hours ago"
    assert (act.interviewing, act.invites_sent, act.unanswered_invites) == (4, 0, 0)
    assert (act.bid_high, act.bid_avg, act.bid_low) == (
        Decimal("75.00"),
        Decimal("54.62"),
        Decimal("30.00"),
    )
    assert (job.connects.required, job.connects.available) == (22, 36)


def test_desktop_hourly_client_stats(desktop_hourly):
    c = parse_job_post(desktop_hourly).client
    assert c.payment_verified is True
    assert c.phone_verified is True
    assert c.rating == Decimal("5.0")
    assert c.review_count == 3
    assert (c.country, c.city) == ("USA", "Boulder")
    assert c.jobs_posted == 9
    assert (c.hire_rate_pct, c.open_jobs) == (45, 2)
    assert c.total_spent == Decimal("11000")
    assert (c.hires, c.active_hires) == (5, 1)
    assert c.avg_hourly_paid == Decimal("37.39")
    assert c.hours_billed == 309
    assert c.industry == "Finance & Accounting"
    assert c.company_size == "Mid-sized company (10-99 people)"
    assert c.member_since == "Feb 21, 2024"
    assert c.recent_history_count == 3


def test_desktop_hourly_no_questions_and_nothing_unparsed(desktop_hourly):
    job = parse_job_post(desktop_hourly)
    assert job.questions == []
    assert job.unparsed_lines == []


# --- desktop, Upwork says hourly, client says fixed -------------------------


def test_conflict_fixture_structured_fields(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    assert job.source_format == "desktop"
    assert job.title == "Looking for Zoho Implementer for CRM"
    assert job.location_restriction == "Worldwide"
    assert job.upwork_job_id == "~021000000000000000002"
    eng = job.engagement
    assert eng.hours_per_week == "lt30"
    assert eng.payment_type == "hourly"
    assert eng.duration == "1to3m"
    assert (eng.hourly_rate_min, eng.hourly_rate_max) == (
        Decimal("9.00"),
        Decimal("21.00"),
    )
    assert eng.contract_to_hire is True
    assert job.skills == [
        "Zoho CRM",
        "Zoho Creator",
        "Automation",
        "Lead Generation",
        "Email Automation",
    ]


def test_conflict_fixture_new_client_has_nulls_not_zeros(desktop_conflict):
    c = parse_job_post(desktop_conflict).client
    assert c.payment_verified is False
    assert c.phone_verified is True
    assert c.rating is None
    assert c.review_count is None
    assert c.country == "Canada"
    assert c.city is None  # the time line had no city before it
    assert (c.hire_rate_pct, c.open_jobs) == (0, 1)
    assert c.total_spent is None
    assert c.hires is None
    assert c.industry is None
    assert c.recent_history_count is None
    assert c.member_since == "Oct 6, 2026"


def test_conflict_fixture_description_keeps_client_prose(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    assert job.description.startswith("TITLE")
    assert "Budget: fixed price, paid in 3 milestones" in job.description
    assert "When you apply, please tell us:" in job.description
    assert job.description.rstrip().endswith("duplicate deal?")
    # Prose-embedded questions are Claude's job; the parser finds none.
    assert job.questions == []
    assert job.unparsed_lines == []


# --- mobile (relayed) ---------------------------------------------------------


def test_mobile_fixture_layout_differences(mobile_relayed):
    job = parse_job_post(mobile_relayed)
    assert job.source_format == "mobile"
    assert job.upwork_job_id is None
    assert (job.connects.required, job.connects.available) == (27, 36)
    eng = job.engagement
    assert eng.duration == "gt6m"
    assert eng.duration_raw == "6+ months"
    assert eng.hourly_rate_min is None and eng.hourly_rate_max is None
    assert eng.experience_level == "intermediate"
    assert (job.activity.proposals_min, job.activity.proposals_max) == (50, None)
    assert job.preferred_qualifications == {
        "Job Success Score": "At least 90%",
        "English level": "Fluent",
    }


def test_mobile_fixture_native_questions(mobile_relayed):
    job = parse_job_post(mobile_relayed)
    assert [q.text for q in job.questions] == [
        "Please include samples of your work as an attachment to your proposal.",
        "Describe your recent experience with similar projects",
    ]
    assert all(q.source == "upwork" for q in job.questions)


def test_mobile_fixture_client_and_history_header_only(mobile_relayed):
    c = parse_job_post(mobile_relayed).client
    assert c.payment_verified is True
    assert c.phone_verified is None  # line absent on this paste
    assert c.rating == Decimal("4.9")
    assert c.review_count == 53
    assert (c.country, c.city) == ("United States", "Fort Lauderdale")
    assert c.total_spent == Decimal("814000")
    assert c.hours_billed == 48648
    assert c.recent_history_count == 50
    assert parse_job_post(mobile_relayed).unparsed_lines == []


# --- R5 boundary ------------------------------------------------------------


@pytest.mark.parametrize(
    "fixture_name", ["desktop_hourly", "desktop_conflict", "mobile_relayed"]
)
def test_claude_input_contains_only_prose(fixture_name, request):
    raw = request.getfixturevalue(fixture_name)
    job = parse_job_post(raw)
    prompt = reading_input(job).to_prompt()
    for marker in CLIENT_SECTION_MARKERS:
        assert marker not in prompt, f"{marker!r} leaked into the Claude input"
    assert job.description in prompt
    for skill in job.skills:
        assert skill in prompt


def test_description_is_a_verbatim_slice_of_the_paste(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    assert job.description in desktop_conflict


# --- garbage in ---------------------------------------------------------------


def test_unrecognised_text_is_not_mistaken_for_a_job():
    job = parse_job_post("Dear hiring manager,\nI am writing to apply.")
    assert job.description == ""
    assert job.skills == []
    assert job.recognised is True  # title guess only
    assert job.title == "Dear hiring manager,"


def test_empty_input():
    job = parse_job_post("")
    assert job.recognised is False
