"""F6 payload, flags and checklist against the fixtures."""

from datetime import date

from app.config.picklists import THRESHOLDS
from app.models.job import AiReading
from app.models.zoho import Classification, LeadFields
from app.services import job_analysis
from app.services.claude import ClaudeReader
from app.services.lead_builder import (
    approved_text_and_quote,
    build_payload,
    build_preview,
    compute_flags,
    payload_hash,
)
from app.services.proposal_fixtures import approvals_for, approved_version  # noqa: F401
from tests.test_claude_service import GOOD_READING, FakeClient, _response

GOOD = Classification.model_validate(
    {
        "industry": "Mortgage / Lending",
        "job_type": "CRM integration",
        "tools": "Zoho CRM, Deluge, Webhooks, Newton Velocity API",
        "confidence": {"industry": 0.9, "job_type": 0.85, "tools": 0.8},
    }
)
NOT_SENT = {
    "First_Name",
    "Email",
    "Phone",
    "Mobile",
    "Company",
    "Website",
    "Description",
    "Hourly",
    "Upwork_Proposal_Link",
    "Upwork_Fee_for_Fixed_Price",
}


def analysis(raw):
    reader = ClaudeReader(
        FakeClient(result=_response(AiReading.model_validate(GOOD_READING))),
        model="m",
    )
    return job_analysis.analyse_job_post(raw, reader)


def test_payload_fields_from_the_mortgage_fixture(desktop_conflict):
    a = analysis(desktop_conflict)
    text = "Hi,\n\nLetter.\n\nKind Regards,\nJohn Lamont"
    version = approved_version(text, quote_amount="65", quote_model="hourly")
    payload, truncations = build_payload(
        a, text, version, None, GOOD, date(2026, 10, 11)
    )
    assert payload["Last_Name"] == "TBD"
    assert payload["Lead_Source"] == "Upwork"
    assert payload["Lead_Status"] == "New Lead"
    assert payload["Upwork_Job_ID"] == "~021000000000000000002"
    assert payload["Job_Link"] == "https://www.upwork.com/jobs/~021000000000000000002"
    assert payload["Job_Name"] == "Looking for Zoho Implementer for CRM"
    assert payload["Proposal"] == text
    assert payload["Proposal_Date"] == "2026-10-11"
    assert payload["Rate_Type"] == "Hourly" and payload["Budget"] == 21.0
    assert payload["Hourly_Rate"] == 65.0 and "Upwork_Fixed_Price" not in payload
    assert payload["Skills_Required"].startswith("Zoho CRM, Zoho Creator")
    assert payload["Client_s_Desired_Experience_Level"] == "Intermediate"
    assert payload["Industry"] == "Mortgage / Lending"
    assert payload["Job_Type"] == "CRM integration"
    assert payload["Tools"].startswith("Zoho CRM")
    assert not (set(payload) & NOT_SENT)
    assert truncations == []


def test_confirmed_fields_override_the_classifier(desktop_conflict):
    a = analysis(desktop_conflict)
    fields = LeadFields(
        industry="Finance & Accounting",
        job_type="Automation / workflow",
        tools="Zoho CRM",
        proposal_link="https://www.upwork.com/ab/proposals/1",
        by_invitation=True,
        confirmed_at="2026-10-11T00:00:00+00:00",
    )
    payload, _ = build_payload(a, None, None, fields, GOOD, date(2026, 10, 11))
    assert payload["Industry"] == "Finance & Accounting"
    assert payload["Job_Type"] == "Automation / workflow"
    assert payload["Proposal_Link"].endswith("/1") and payload["By_Invitation"] is True
    assert "Proposal" not in payload  # nothing approved yet


def test_long_values_are_truncated_and_reported(desktop_conflict):
    a = analysis(desktop_conflict)
    a.parsed.skills = [f"Skill {i}" for i in range(60)]
    payload, truncations = build_payload(a, None, None, None, GOOD, date(2026, 10, 11))
    assert len(payload["Skills_Required"]) == 255
    assert any(t.startswith("Skills_Required") for t in truncations)


def test_flags_threshold_offpicklist_and_confirmation():
    low = GOOD.model_copy(deep=True)
    low.confidence.industry = 0.5
    low.confidence.tools = THRESHOLDS["Tools"] - 0.01
    flags = compute_flags(low, None)
    assert {f.field for f in flags} == {"Industry", "Tools"}
    assert "below" in flags[0].reason

    off = GOOD.model_copy(deep=True)
    off.job_type = "Something Zoho never heard of"
    assert [f.field for f in compute_flags(off, None)] == ["Job_Type"]
    assert "not on the picklist" in compute_flags(off, None)[0].reason

    assert len(compute_flags(None, None)) == 3  # unclassified: all three
    confirmed = LeadFields(confirmed_at="2026-10-11T00:00:00+00:00")
    assert compute_flags(None, confirmed) == []  # operator's word is final


def test_preview_checklist_gates_create_lead(desktop_conflict, mobile_relayed):
    a = analysis(desktop_conflict)
    text = "Hi,\n\nLetter.\n\nKind Regards,\nJohn Lamont"
    versions, approvals = approvals_for(text)
    ok = build_preview(a, versions, approvals, None, GOOD, None, connected=True)
    assert ok.ready and all(c.ok for c in ok.checklist)

    nothing_copied = build_preview(a, versions, [], None, GOOD, None, connected=True)
    assert not nothing_copied.ready
    assert not next(c for c in nothing_copied.checklist if c.key == "approved").ok
    assert "Proposal" not in nothing_copied.payload

    disconnected = build_preview(
        a, versions, approvals, None, GOOD, None, connected=False
    )
    assert not next(c for c in disconnected.checklist if c.key == "connected").ok

    mobile = analysis(mobile_relayed)  # no job id on mobile pastes
    no_id = build_preview(mobile, versions, approvals, None, GOOD, None, connected=True)
    assert not next(c for c in no_id.checklist if c.key == "job_id").ok


def test_payload_hash_is_canonical():
    assert payload_hash({"b": 1, "a": 2}) == payload_hash({"a": 2, "b": 1})
    assert payload_hash({"a": 1}) != payload_hash({"a": 2})


def test_approved_text_uses_the_latest_approval_version():
    v1 = approved_version("Hi,\n\nFirst.\n\nKind Regards,\nJ", version_id="v1")
    v2 = approved_version("Hi,\n\nSecond.\n\nKind Regards,\nJ", version_id="v2")
    versions = [
        {"id": "v1", "sections": v1.model_dump(mode="json")},
        {"id": "v2", "sections": v2.model_dump(mode="json")},
    ]
    approvals = [
        {"draft_version_id": "v2", "approved_at": "2026-10-11T10:00:00+00:00"},
        {"draft_version_id": "v1", "approved_at": "2026-10-11T11:00:00+00:00"},
    ]
    text, _ = approved_text_and_quote(versions, approvals)
    assert text.startswith("Hi,\n\nFirst.")  # v1 was approved most recently
