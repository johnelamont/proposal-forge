"""F3 drafter: the frame is the operator's, claims are checked, R5 holds."""

from unittest.mock import MagicMock

import anthropic

from app.models.advisory import Advisory, AdvisoryReading
from app.models.job import AiReading
from app.models.proposal import DraftOutput, Profile, RefineOutput
from app.services import job_analysis
from app.services.claude import ClaudeReader
from app.services.drafter import (
    Drafter,
    build_draft_prompt,
    frame,
    never_claim_warnings,
    questions_for,
)
from app.services.matcher import find_comparables, match_strength
from tests.test_advisor import GOOD_ADVISORY
from tests.test_claude_service import GOOD_READING, FakeClient, _response
from tests.test_matcher import entry

PROFILE = Profile(
    user_id="u",
    created_at="t",
    updated_at="t",
    signature_name="John Lamont",
    positioning="Independent Zoho consultant for small firms.",
    greeting="Hi,",
    sign_off="Kind Regards,",
    tone_notes="Plain. No hype.",
    never_claim=["Zoho Partner", "certified"],
)


def analysis(raw):
    reader = ClaudeReader(
        FakeClient(result=_response(AiReading.model_validate(GOOD_READING))),
        model="m",
    )
    return job_analysis.analyse_job_post(raw, reader)


def advisory_for(raw, history):
    a = analysis(raw)
    comps = find_comparables(a.parsed, None, history)
    return Advisory(
        comparables=comps,
        match_strength=match_strength(comps, len(history)),
        reading=AdvisoryReading.model_validate(GOOD_ADVISORY),
        failure=None,
    )


# --- frame ---------------------------------------------------------------------


def test_frame_adds_operator_greeting_and_sign_off():
    out = frame("I have built this exact integration.", PROFILE)
    assert out.startswith("Hi,\n\nI have built")
    assert out.endswith("\n\nKind Regards,\nJohn Lamont")


def test_frame_strips_a_greeting_and_sign_off_the_model_wrote_anyway():
    body = "Hello there,\n\nBody text.\n\nBest regards,\nSomeone Else"
    out = frame(body, PROFILE)
    assert out == "Hi,\n\nBody text.\n\nKind Regards,\nJohn Lamont"


def test_frame_is_idempotent():
    once = frame("Body.", PROFILE)
    assert frame(once, PROFILE) == once


# --- never-claim -------------------------------------------------------------


def test_never_claim_phrases_are_reported_not_removed():
    warnings = never_claim_warnings(["As a Zoho Partner I can…"], PROFILE)
    assert len(warnings) == 1 and "Zoho Partner" in warnings[0]
    assert never_claim_warnings(["Plain text."], PROFILE) == []


# --- prompt boundary (R5) --------------------------------------------------------


def test_prompt_has_job_profile_questions_and_no_client_names(desktop_conflict):
    a = analysis(desktop_conflict)
    history = [entry(client_name="Northwind Mortgage", source_files=[{"x": 1}])]
    adv = advisory_for(desktop_conflict, history)
    qs = questions_for(a, ["Do you work weekends?"])
    prompt = build_draft_prompt(a, adv, history, PROFILE, qs)
    assert "CONSULTANT\nIndependent Zoho consultant" in prompt
    assert "TONE NOTES\nPlain. No hype." in prompt
    assert "JOB: Looking for Zoho Implementer for CRM" in prompt
    assert "ANGLE" in prompt and "Known gaps" in prompt
    assert "Velocity → Zoho sync" in prompt  # cited project by name
    assert "Northwind" not in prompt and "source_files" not in prompt
    # The mortgage fixture's questions live in the description, which the
    # fake F1 reading does not extract, so only the extra question appears.
    assert "QUESTIONS\n1. Do you work weekends?" in prompt


def test_questions_merge_dedupes_case_insensitively(mobile_relayed):
    a = analysis(mobile_relayed)  # two Upwork-native questions
    qs = questions_for(
        a, ["describe your recent experience with similar projects", "New one?"]
    )
    assert qs.count("Describe your recent experience with similar projects") == 1
    assert len(qs) == 3 and qs[-1] == "New one?"


# --- draft ------------------------------------------------------------------


def good_draft(questions):
    return DraftOutput.model_validate(
        {
            "cover_letter": "Hi John,\n\nI built the same Velocity link.\n\nBest,\nX",
            "answers": [
                {"question": q, "answer": f"Answer to: {q}"} for q in questions
            ],
            "confidence": {"cover_letter": 0.8, "answers": 0.7},
        }
    )


def test_draft_frames_cover_letter_and_aligns_answers(desktop_conflict):
    a = analysis(desktop_conflict)
    qs = questions_for(a, [])
    client = FakeClient(result=_response(good_draft(qs)))
    sections, meta = Drafter(client, "m").draft(a, None, [], PROFILE, qs)
    assert sections.cover_letter.startswith("Hi,\n\nI built the same Velocity link.")
    assert sections.cover_letter.endswith("Kind Regards,\nJohn Lamont")
    assert [x.question for x in sections.answers] == qs
    assert meta.failure is None and meta.confidence["cover_letter"] == 0.8
    assert meta.warnings == []


def test_draft_with_fewer_answers_than_questions_warns(desktop_conflict):
    a = analysis(desktop_conflict)
    qs = ["How soon can you start?", "Have you used Velocity?"]
    short = good_draft(qs[:1])
    client = FakeClient(result=_response(short))
    sections, meta = Drafter(client, "m").draft(a, None, [], PROFILE, qs)
    assert sections.answers[0].answer and sections.answers[1].answer == ""
    assert any("unmatched questions are blank" in w for w in meta.warnings)


def test_draft_failure_yields_empty_sections_and_the_failure(desktop_conflict):
    a = analysis(desktop_conflict)
    qs = questions_for(a, [])
    client = FakeClient(raises=anthropic.APIConnectionError(request=MagicMock()))
    sections, meta = Drafter(client, "m").draft(a, None, [], PROFILE, qs)
    assert sections.cover_letter is None
    assert all(x.answer == "" for x in sections.answers)
    assert meta.failure is not None and meta.failure.kind == "error"


# --- refine ------------------------------------------------------------------


def test_refine_cover_letter_reframes_and_warns_on_claims():
    client = FakeClient(
        result=_response(
            RefineOutput(
                content="Hello!\n\nAs a certified expert, shorter.\n\nThanks",
                confidence=0.6,
            )
        )
    )
    text, meta = Drafter(client, "m").refine(
        "Hi,\n\nLong.\n\nKind Regards,\nJohn Lamont", "shorter", PROFILE, True
    )
    assert (
        text == "Hi,\n\nAs a certified expert, shorter.\n\nKind Regards,\nJohn Lamont"
    )
    assert any("certified" in w for w in meta.warnings)
    sent = client.calls[0]["messages"][0]["content"]
    assert "SECTION\nLong." in sent  # frame stripped before sending


def test_refine_failure_returns_none():
    client = FakeClient(raises=anthropic.APIConnectionError(request=MagicMock()))
    text, meta = Drafter(client, "m").refine("x", "shorter", PROFILE, False)
    assert text is None and meta.failure is not None
