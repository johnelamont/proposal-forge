"""Deterministic matching (F2 layer one): aliases, scoring, evidence labels."""

from app.services.job_parser import parse_job_post
from app.services.matcher import (
    expand,
    find_comparables,
    match_strength,
    score_entry,
    tokens,
)


def entry(**overrides):
    base = {
        "id": "e1",
        "name": "Velocity → Zoho sync",
        "summary": "Connected a mortgage broker's Velocity system to Zoho CRM "
        "with webhooks and Deluge; renewal reminders automated.",
        "tech_stack": ["Zoho CRM", "Deluge", "Webhooks"],
        "vertical": "mortgage brokerage",
        "project_type": "CRM integration",
        "complexity": "medium",
        "outcomes": ["Funded deals sync automatically"],
        "budget_band": "$1–5K",
    }
    return {**base, **overrides}


# --- aliases and tokens -------------------------------------------------------


def test_aliases_expand_both_ways():
    assert "zoho" in expand("Zoho CRM")
    assert "react" in expand("Next.js")
    assert "python" in expand("FastAPI")
    assert expand("Unknown Tool") == {"unknown tool"}


def test_tokens_drop_stopwords_and_short_words():
    t = tokens("We are looking for an expert in Zoho CRM and AI for our team")
    assert "zoho" in t and "ai" in t
    assert "looking" not in t and "for" not in t and "team" not in t


# --- scoring -----------------------------------------------------------------


def test_zoho_job_matches_zoho_entry_with_shared_tech(desktop_conflict):
    job = parse_job_post(desktop_conflict)  # Zoho + Velocity mortgage job
    c = score_entry(job, None, entry())
    assert c is not None
    assert "Zoho CRM" in c.shared_tech
    assert c.score >= 2
    # Shared prose terms are reported too (velocity, renewal, mortgage ...).
    assert any(t in c.shared_terms for t in ("velocity", "renewal", "mortgage"))


def test_unrelated_entry_is_not_comparable(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    unrelated = entry(
        id="e2",
        name="Bakery website",
        summary="A static marketing site for a bakery.",
        tech_stack=["Hugo", "Netlify"],
        vertical="food retail",
        project_type="website",
        outcomes=[],
    )
    assert score_entry(job, None, unrelated) is None


def test_alias_match_zoho_creator_counts_as_zoho(desktop_hourly):
    job = parse_job_post(desktop_hourly)  # skills: Zoho CRM, Zoho Creator
    e = entry(
        id="e3",
        name="Internal tool",
        summary="Built an approvals app for a finance team.",
        tech_stack=["Zoho"],
        vertical="finance",
        project_type="internal app",
    )
    c = score_entry(job, None, e)
    assert c is not None and c.shared_tech == ["Zoho"]


def test_vertical_overlap_adds_a_bonus(desktop_hourly):
    job = parse_job_post(desktop_hourly)  # client industry: Finance & Accounting
    with_vertical = entry(id="a", tech_stack=["Zoho CRM"], vertical="finance")
    without = entry(id="b", tech_stack=["Zoho CRM"], vertical=None)
    a = score_entry(job, None, with_vertical)
    b = score_entry(job, None, without)
    assert a and b and a.score > b.score


def test_find_comparables_sorts_and_caps(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    history = [entry(id=f"e{i}", name=f"Zoho project {i}") for i in range(7)]
    history[3]["tech_stack"] = ["Zoho CRM", "Deluge", "Webhooks", "Zoho Creator"]
    result = find_comparables(job, None, history)
    assert len(result) == 5
    assert result[0].entry_id == "e3"  # most shared tech first


# --- evidence labels -----------------------------------------------------------


def test_match_strength_labels(desktop_conflict):
    job = parse_job_post(desktop_conflict)
    assert match_strength([], 0).level == "none_history"
    assert match_strength([], 4).level == "none_comparable"
    one = find_comparables(job, None, [entry()])
    assert match_strength(one, 1).level == "thin"
    assert "Thin evidence" in match_strength(one, 1).label
    three = find_comparables(job, None, [entry(id=f"e{i}") for i in range(3)])
    assert match_strength(three, 3).level == "some"
    five = find_comparables(job, None, [entry(id=f"e{i}") for i in range(6)])
    assert match_strength(five, 6).level == "strong"
    assert match_strength(five, 6).comparable_count == 5
