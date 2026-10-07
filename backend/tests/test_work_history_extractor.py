"""F5 extractor: the R5 prompt boundary and the R8 failure paths."""

from unittest.mock import MagicMock

import anthropic

from app.models.job import AiFailure
from app.models.work_history import DroppedFile, Extraction
from app.services.work_history_extractor import (
    WorkHistoryExtractor,
    files_to_prompt,
)
from tests.test_claude_service import FakeClient, _response

GOOD_EXTRACTION = {
    "name": "Velocity to Zoho integration",
    "summary": "Connected a mortgage system to Zoho CRM.",
    "tech_stack": ["Zoho CRM", "Deluge", "Webhooks"],
    "vertical": "mortgage brokerage",
    "project_type": "CRM integration",
    "complexity": "medium",
    "complexity_reason": "Two systems, idempotent upserts, renewal automation.",
    "role": "sole developer",
    "outcomes": ["Funded deals sync automatically"],
    "client_name_detected": "Northwind Mortgage",
    "duration_hint": "6 weeks",
    "confidence": {
        "name": 0.9,
        "summary": 0.9,
        "tech_stack": 0.95,
        "vertical": 0.9,
        "project_type": 0.9,
        "complexity": 0.7,
        "role": 0.5,
        "outcomes": 0.8,
        "client_name_detected": 0.9,
        "duration_hint": 0.8,
    },
}

FILES = [
    DroppedFile(name="README.md", content="# Velocity sync\n\nSyncs deals."),
    DroppedFile(name="pyproject.toml", content='[project]\nname = "sync"'),
]


def test_prompt_is_exactly_the_files_with_their_names():
    prompt = files_to_prompt(FILES)
    assert prompt.startswith("=== file: README.md ===\n# Velocity sync")
    assert "=== file: pyproject.toml ===" in prompt
    assert 'name = "sync"' in prompt


def test_success_returns_extraction_and_detected_name_is_not_a_permission():
    client = FakeClient(result=_response(Extraction.model_validate(GOOD_EXTRACTION)))
    result = WorkHistoryExtractor(client, model="claude-opus-5-5").extract(FILES)
    assert isinstance(result, Extraction)
    assert result.client_name_detected == "Northwind Mortgage"
    # The record model, not the extraction, owns may_name_client (default false).
    assert not hasattr(result, "may_name_client")
    sent = client.calls[0]
    assert sent["output_format"] is Extraction
    assert files_to_prompt(FILES) == sent["messages"][0]["content"]


def test_no_files_is_skipped_without_a_call():
    client = FakeClient(result=_response(None))
    result = WorkHistoryExtractor(client, model="m").extract([])
    assert isinstance(result, AiFailure) and result.kind == "skipped"
    assert client.calls == []


def test_api_error_is_a_failure():
    client = FakeClient(raises=anthropic.APIConnectionError(request=MagicMock()))
    result = WorkHistoryExtractor(client, model="m").extract(FILES)
    assert isinstance(result, AiFailure) and result.kind == "error"


def test_schema_invalid_output_is_malformed():
    client = FakeClient(result=_response({"name": "only a name"}))
    result = WorkHistoryExtractor(client, model="m").extract(FILES)
    assert isinstance(result, AiFailure) and result.kind == "malformed"


def test_no_api_key_is_skipped():
    result = WorkHistoryExtractor(None, model="m").extract(FILES)
    assert isinstance(result, AiFailure) and result.kind == "skipped"
