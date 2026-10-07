"""Claude layer failure paths (R8). No network: the client is a fake.

Every path must produce an AiFailure with the right kind, and the orchestration
must keep the deterministic fields and set parse_status = ai_failed.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import anthropic
import pytest

from app.models.job import AiFailure, AiReading
from app.services import job_analysis
from app.services.claude import ClaudeReader, ReadingInput

GOOD_READING = {
    "one_line": "Set up drip campaigns in Zoho CRM.",
    "deliverables": ["Drip campaigns", "User support"],
    "requirements": ["US-based"],
    "questions_in_description": [],
    "budget_statement": None,
    "timeline_statement": None,
    "red_flags": [],
    "sensitive_data_domain": {"flag": False, "reason": None},
    "confidence": {
        "one_line": 0.9,
        "deliverables": 0.8,
        "requirements": 0.7,
        "questions_in_description": 0.9,
        "budget_statement": 0.9,
        "timeline_statement": 0.9,
        "red_flags": 0.6,
        "sensitive_data_domain": 0.9,
    },
}

INPUT = ReadingInput(
    title="Zoho Consulting",
    description="We need a consultant for drip campaigns.",
    skills=["Zoho CRM"],
    upwork_questions=[],
)


class FakeClient:
    """Mimics the slice of anthropic.Anthropic that ClaudeReader uses."""

    def __init__(self, *, result=None, raises=None):
        self.calls: list[dict] = []
        self._result = result
        self._raises = raises
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        if self._raises is not None:
            raise self._raises
        return self._result


def _response(parsed=None, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)


def _status_error(cls, status_code):
    response = MagicMock(status_code=status_code, headers={})
    return cls(f"status {status_code}", response=response, body=None)


# --- success ----------------------------------------------------------------


def test_success_returns_reading_and_sends_only_the_prose():
    client = FakeClient(result=_response(AiReading.model_validate(GOOD_READING)))
    reader = ClaudeReader(client, model="claude-opus-5-5")

    result = reader.read_description(INPUT)

    assert isinstance(result, AiReading)
    assert result.one_line.startswith("Set up drip")
    sent = client.calls[0]
    assert sent["model"] == "claude-opus-5-5"
    assert sent["output_format"] is AiReading
    user_text = sent["messages"][0]["content"]
    assert INPUT.description in user_text
    assert "Zoho CRM" in user_text


# --- failure paths ----------------------------------------------------------


@pytest.mark.parametrize(
    ("exc", "kind"),
    [
        (anthropic.APIConnectionError(request=MagicMock()), "error"),
        (_status_error(anthropic.RateLimitError, 429), "error"),
        (_status_error(anthropic.InternalServerError, 500), "error"),
        (_status_error(anthropic.BadRequestError, 400), "error"),
        (ValueError("not json"), "malformed"),
    ],
)
def test_exceptions_become_failures(exc, kind):
    reader = ClaudeReader(FakeClient(raises=exc), model="m")
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure)
    assert result.kind == kind
    assert result.message


def test_empty_response_is_a_failure():
    reader = ClaudeReader(FakeClient(result=_response(parsed=None)), model="m")
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure) and result.kind == "empty"


def test_schema_invalid_dict_is_malformed():
    bad = {"one_line": "x"}  # missing required fields
    reader = ClaudeReader(FakeClient(result=_response(parsed=bad)), model="m")
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure) and result.kind == "malformed"


def test_refusal_is_reported_not_hidden():
    reader = ClaudeReader(
        FakeClient(result=_response(parsed=None, stop_reason="refusal")), model="m"
    )
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure) and result.kind == "refusal"


def test_truncated_output_is_malformed():
    reader = ClaudeReader(
        FakeClient(result=_response(parsed=None, stop_reason="max_tokens")),
        model="m",
    )
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure) and result.kind == "malformed"


def test_no_api_key_is_skipped_not_crashed():
    reader = ClaudeReader(None, model="m")
    result = reader.read_description(INPUT)
    assert isinstance(result, AiFailure) and result.kind == "skipped"


# --- orchestration keeps the deterministic layer ------------------------------


def test_ai_failure_keeps_parsed_fields(desktop_hourly):
    reader = ClaudeReader(
        FakeClient(raises=anthropic.APIConnectionError(request=MagicMock())),
        model="m",
    )
    analysis = job_analysis.analyse_job_post(desktop_hourly, reader)
    assert analysis.parse_status == "ai_failed"
    assert analysis.ai is None
    assert analysis.ai_failure is not None and analysis.ai_failure.kind == "error"
    assert analysis.parsed.title == "Zoho Consulting"
    assert analysis.parsed.client.total_spent is not None
    assert analysis.conflicts == []


def test_conflict_is_listed_not_resolved(desktop_conflict):
    reading = dict(GOOD_READING)
    reading["budget_statement"] = {
        "model": "fixed",
        "amount_raw": "fixed price, paid in 3 milestones",
        "milestones": ["Setup and data import", "Velocity connection", "Handover"],
    }
    reading["questions_in_description"] = [
        "Your price and how long it will take",
        "A similar integration you have done",
    ]
    client = FakeClient(result=_response(AiReading.model_validate(reading)))
    analysis = job_analysis.analyse_job_post(
        desktop_conflict, ClaudeReader(client, model="m")
    )

    assert analysis.parse_status == "ok"
    assert analysis.parsed.engagement.payment_type == "hourly"  # untouched
    assert len(analysis.conflicts) == 1
    conflict = analysis.conflicts[0]
    assert conflict.field == "payment_type"
    assert conflict.upwork_value.startswith("hourly $9.00-$21.00")
    assert conflict.description_value.startswith("fixed")
    # Prose questions merged with source = description
    sources = {q.source for q in analysis.parsed.questions}
    assert sources == {"description"}
    assert len(analysis.parsed.questions) == 2


def test_unrecognised_paste_skips_claude_entirely():
    client = FakeClient(result=_response(AiReading.model_validate(GOOD_READING)))
    analysis = job_analysis.analyse_job_post("", ClaudeReader(client, model="m"))
    assert analysis.parse_status == "unrecognised"
    assert client.calls == []
    assert analysis.ai_failure is not None and analysis.ai_failure.kind == "skipped"
