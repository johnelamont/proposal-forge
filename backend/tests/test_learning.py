"""F8d: what the app learns from outcomes — matcher over rag_index rows, the
evidence counts, the advisor's outcomes section (no excerpts), and the
drafter's won examples (excerpts, behind the profile toggle)."""

from app.models.advisory import AdvisoryReading
from app.models.proposal import Profile
from app.services.advisor import Advisor, build_prompt
from app.services.drafter import Drafter, build_draft_prompt
from app.services.matcher import (
    MIN_OUTCOMES_FOR_VERDICT,
    find_comparables,
    find_proposal_comparables,
    outcome_evidence,
    score_proposal,
)
from tests.test_advisor import GOOD_ADVISORY, _analysis
from tests.test_claude_service import FakeClient, _response
from tests.test_drafter import PROFILE, good_draft
from tests.test_matcher import entry


def row(**over):
    base = {
        "proposal_id": "p1",
        "outcome": "won",
        "lost_reason": None,
        "industry": "Mortgage / Lending",
        "job_type": "CRM integration",
        "tools": "Zoho CRM, Deluge",
        "skills": ["Zoho CRM", "API Integration"],
        "job_title": "Zoho CRM for a mortgage broker",
        "proposal_excerpt": "Hi,\n\nI connected Velocity to Zoho for a broker last "
        "year, with renewal reminders. Client name: Northwind.",
        "decided_at": "2026-10-20T16:00:00+00:00",
        "archived": False,
    }
    return {**base, **over}


# --- matcher -----------------------------------------------------------------------


def test_past_proposal_matches_on_skills_tools_and_prose(desktop_conflict):
    a = _analysis(desktop_conflict)
    c = score_proposal(a.parsed, None, row())
    assert c is not None and c.outcome == "won"
    assert "Zoho CRM" in c.shared_tech
    assert any(t in c.shared_terms for t in ("velocity", "renewal", "mortgage"))
    assert c.score > 2


def test_unrelated_past_proposal_is_not_comparable(desktop_conflict):
    a = _analysis(desktop_conflict)
    bakery = row(
        proposal_id="p9",
        industry="Hospitality / Travel",
        job_type="Other",
        tools="Hugo",
        skills=["Hugo"],
        job_title="Static site for a bakery",
        proposal_excerpt="Hi,\n\nA small static site with a menu page.",
    )
    assert score_proposal(a.parsed, None, bakery) is None
    assert find_proposal_comparables(a.parsed, None, [bakery]) == []


def test_evidence_counts_split_by_reason_and_gate_the_verdict(desktop_conflict):
    a = _analysis(desktop_conflict)
    rows = [
        row(proposal_id="p1", outcome="won"),
        row(proposal_id="p2", outcome="lost", lost_reason="job_closed"),
        row(proposal_id="p3", outcome="lost", lost_reason="junk_lead"),
        row(proposal_id="p4", outcome="withdrawn"),
    ]
    comps = find_proposal_comparables(a.parsed, None, rows)
    ev = outcome_evidence(comps, len(rows))
    assert (ev.won, ev.lost_bid, ev.lost_not_worth, ev.withdrawn) == (1, 1, 1, 1)
    assert ev.label.startswith("4 comparable past proposals: 1 won, 1 lost, ")
    assert "judged not worth bidding" in ev.label and ev.verdict_allowed

    thin = outcome_evidence(comps[:1], 1)
    assert not thin.verdict_allowed and "too few outcomes" in thin.label
    assert MIN_OUTCOMES_FOR_VERDICT == 3

    assert outcome_evidence([], 0).label == "No proposal outcomes recorded yet"
    assert outcome_evidence([], 5).label.startswith("No comparable past proposals")


# --- advisor -------------------------------------------------------------------------


def test_advisor_prompt_lists_outcomes_without_excerpts(desktop_conflict):
    a = _analysis(desktop_conflict)
    history = [entry()]
    comps = find_comparables(a.parsed, None, history)
    pcomps = find_proposal_comparables(
        a.parsed,
        None,
        [row(), row(proposal_id="p2", outcome="lost", lost_reason="hired_other")],
    )
    prompt = build_prompt(a, comps, history, pcomps)
    assert "PAST PROPOSAL OUTCOMES" in prompt
    assert "Zoho CRM for a mortgage broker" in prompt and "lost (hired_other)" in prompt
    assert "Northwind" not in prompt  # the excerpt never reaches the advisor
    assert "I connected Velocity to Zoho" not in prompt


def test_advisor_returns_evidence_even_without_work_history(desktop_conflict):
    client = FakeClient(result=_response(AdvisoryReading.model_validate(GOOD_ADVISORY)))
    adv = Advisor(client, model="m").advise(_analysis(desktop_conflict), [], [row()])
    assert adv.reading is None and client.calls == []  # no past work → no verdict
    assert len(adv.proposal_comparables) == 1
    assert adv.outcome_evidence is not None and adv.outcome_evidence.won == 1
    assert adv.outcomes_note == adv.outcome_evidence.label


def test_advisor_with_history_and_outcomes_calls_once(desktop_conflict):
    client = FakeClient(result=_response(AdvisoryReading.model_validate(GOOD_ADVISORY)))
    adv = Advisor(client, model="m").advise(
        _analysis(desktop_conflict), [entry()], [row()]
    )
    assert adv.reading is not None and len(client.calls) == 1
    assert "PAST PROPOSAL OUTCOMES" in client.calls[0]["messages"][0]["content"]


# --- drafter -------------------------------------------------------------------------


def test_draft_prompt_includes_won_excerpts_only_when_given(desktop_conflict):
    a = _analysis(desktop_conflict)
    without = build_draft_prompt(a, None, [], PROFILE, [])
    assert "PROPOSALS THAT WON" not in without
    with_ex = build_draft_prompt(a, None, [], PROFILE, [], [row()])
    assert "PROPOSALS THAT WON" in with_ex
    assert "Zoho CRM for a mortgage broker (Mortgage / Lending)" in with_ex
    assert "I connected Velocity to Zoho" in with_ex


def test_draft_sends_only_allowed_fields_and_records_what_was_used(desktop_conflict):
    a = _analysis(desktop_conflict)
    client = FakeClient(result=_response(good_draft([])))
    example = row(
        zoho_lead_id="123", quote_amount="65", skills=["Zoho CRM"], budget="9000"
    )
    _, meta = Drafter(client, "m").draft(
        a, None, [], PROFILE, [], won_examples=[example]
    )
    sent = client.calls[0]["messages"][0]["content"]
    assert "I connected Velocity to Zoho" in sent
    assert "9000" not in sent and "123" not in sent  # not in WON_EXAMPLE_FIELDS
    assert meta.won_examples_used == ["Zoho CRM for a mortgage broker"]


def test_profile_toggle_defaults_on():
    assert Profile.model_validate(
        {**PROFILE.model_dump(), "use_won_examples": True}
    ).use_won_examples
    assert PROFILE.use_won_examples is True
