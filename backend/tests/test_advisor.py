"""F2 advisor: the R5 prompt boundary and the R8 failure paths."""

from unittest.mock import MagicMock

import anthropic

from app.models.advisory import AdvisoryReading
from app.models.job import AiReading
from app.services import job_analysis
from app.services.advisor import Advisor, build_prompt
from app.services.claude import ClaudeReader
from app.services.matcher import find_comparables
from tests.test_claude_service import GOOD_READING, FakeClient, _response
from tests.test_matcher import entry

GOOD_ADVISORY = {
    "fit": "strong",
    "reasons": ["Same CRM, same integration pattern (webhooks into Zoho)."],
    "gaps": ["No stated experience with the Velocity API specifically."],
    "cite": [{"entry_id": "e1", "name": "Velocity → Zoho sync", "why": "Same stack."}],
    "angle": "Lead with the renewal automation you have already built.",
    "confidence": {"fit": 0.8, "reasons": 0.85, "gaps": 0.7, "cite": 0.9, "angle": 0.6},
}


def _analysis(raw):
    """A JobAnalysis with a successful F1 reading, no network."""
    reading = AiReading.model_validate(GOOD_READING)
    reader = ClaudeReader(FakeClient(result=_response(reading)), model="m")
    return job_analysis.analyse_job_post(raw, reader)


def test_prompt_contains_job_and_comparables_but_no_client_names(desktop_conflict):
    analysis = _analysis(desktop_conflict)
    history = [entry(client_name="Northwind Mortgage", source_files=[{"x": 1}])]
    comparables = find_comparables(analysis.parsed, None, history)
    prompt = build_prompt(analysis, comparables, history)
    assert "JOB: Looking for Zoho Implementer for CRM" in prompt
    assert "entry_id: e1" in prompt
    assert "Zoho CRM, Deluge, Webhooks" in prompt
    assert "Northwind" not in prompt
    assert "source_files" not in prompt and "client_name" not in prompt


def test_no_history_means_no_call(desktop_conflict):
    client = FakeClient(result=_response(AdvisoryReading.model_validate(GOOD_ADVISORY)))
    advisory = Advisor(client, model="m").advise(_analysis(desktop_conflict), [])
    assert advisory.match_strength.level == "none_history"
    assert advisory.reading is None and advisory.failure is None
    assert client.calls == []


def test_no_comparables_means_no_call(desktop_conflict):
    client = FakeClient(result=_response(AdvisoryReading.model_validate(GOOD_ADVISORY)))
    unrelated = [
        entry(
            id="u",
            name="Bakery site",
            summary="Static site.",
            tech_stack=["Hugo"],
            vertical="food",
            project_type="website",
            outcomes=[],
        )
    ]
    advisory = Advisor(client, model="m").advise(_analysis(desktop_conflict), unrelated)
    assert advisory.match_strength.level == "none_comparable"
    assert client.calls == []


def test_success_filters_citations_to_shown_entries(desktop_conflict):
    reading = dict(GOOD_ADVISORY)
    reading["cite"] = GOOD_ADVISORY["cite"] + [
        {"entry_id": "ghost", "name": "Made up", "why": "Hallucinated."}
    ]
    client = FakeClient(result=_response(AdvisoryReading.model_validate(reading)))
    advisory = Advisor(client, model="m").advise(_analysis(desktop_conflict), [entry()])
    assert advisory.reading is not None
    assert [c.entry_id for c in advisory.reading.cite] == ["e1"]
    assert advisory.match_strength.level == "thin"
    sent = client.calls[0]
    assert sent["output_format"] is AdvisoryReading


def test_claude_failure_keeps_comparables(desktop_conflict):
    client = FakeClient(raises=anthropic.APIConnectionError(request=MagicMock()))
    advisory = Advisor(client, model="m").advise(_analysis(desktop_conflict), [entry()])
    assert advisory.reading is None
    assert advisory.failure is not None and advisory.failure.kind == "error"
    assert len(advisory.comparables) == 1  # the deterministic layer survives


def test_no_api_key_is_skipped(desktop_conflict):
    advisory = Advisor(None, model="m").advise(_analysis(desktop_conflict), [entry()])
    assert advisory.failure is not None and advisory.failure.kind == "skipped"
