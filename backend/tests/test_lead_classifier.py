from unittest.mock import MagicMock

import anthropic
import pytest
from pydantic import ValidationError

from app.config.picklists import INDUSTRY, JOB_TYPE
from app.models.job import AiFailure, AiReading
from app.models.zoho import Classification
from app.services import job_analysis
from app.services.claude import ClaudeReader
from app.services.lead_classifier import (
    ClassificationOut,
    LeadClassifier,
    classification_prompt,
)
from tests.test_claude_service import GOOD_READING, FakeClient, _response


def analysis(raw):
    reader = ClaudeReader(
        FakeClient(result=_response(AiReading.model_validate(GOOD_READING))),
        model="m",
    )
    return job_analysis.analyse_job_post(raw, reader)


def test_schema_only_accepts_picklist_values():
    good = ClassificationOut.model_validate(
        {
            "industry": INDUSTRY[0],
            "job_type": JOB_TYPE[0],
            "tools": "Zoho",
            "confidence": {"industry": 0.9, "job_type": 0.9, "tools": 0.9},
        }
    )
    assert good.industry == INDUSTRY[0]
    with pytest.raises(ValidationError):
        ClassificationOut.model_validate(
            {
                "industry": "Banking",
                "job_type": JOB_TYPE[0],
                "tools": "x",
                "confidence": {"industry": 0.9, "job_type": 0.9, "tools": 0.9},
            }
        )


def test_prompt_is_job_only_and_lists_the_allowed_values(desktop_conflict):
    a = analysis(desktop_conflict)
    a.parsed.client.industry = "Finance & Accounting"
    prompt = classification_prompt(a)
    assert "JOB: Looking for Zoho Implementer for CRM" in prompt
    assert "Allowed Industry values: " + "; ".join(INDUSTRY) in prompt
    assert "Allowed Job_Type values" in prompt
    for forbidden in ("hire rate", "total spent", "Bid range", "Member since"):
        assert forbidden not in prompt


def test_success_and_failure(desktop_conflict):
    a = analysis(desktop_conflict)
    out = ClassificationOut.model_validate(
        {
            "industry": "Mortgage / Lending",
            "job_type": "CRM integration",
            "tools": "Zoho CRM, Deluge",
            "confidence": {"industry": 0.9, "job_type": 0.8, "tools": 0.7},
        }
    )
    ok = LeadClassifier(FakeClient(result=_response(out)), "m").classify(a)
    assert isinstance(ok, Classification) and ok.industry == "Mortgage / Lending"

    bad = LeadClassifier(
        FakeClient(raises=anthropic.APIConnectionError(request=MagicMock())), "m"
    ).classify(a)
    assert isinstance(bad, AiFailure) and bad.kind == "error"
