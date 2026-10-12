"""F6: assemble the Zoho Lead payload and the pre-send checklist.

Field mapping: docs/ZOHO_INTEGRATION.md → Lead out. Deterministic apart from
the three AI-derived fields, which come from the classifier unless the
operator has confirmed values. Everything the operator will see in the
preview — payload, truncations, flags, checklist — is computed here.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any

from app.config.picklists import INDUSTRY, JOB_TYPE, THRESHOLDS
from app.models.job import AiFailure, ExperienceLevel, JobAnalysis, PaymentType
from app.models.proposal import Sections
from app.models.zoho import (
    ChecklistItem,
    Classification,
    FieldFlag,
    LeadFields,
    LeadPreview,
)

LIMITS = {
    "Job_Name": 255,
    "Skills_Required": 255,
    "Tools": 255,
    "Proposal": 32000,
    "Last_Name": 80,
}
EXPERIENCE = {
    ExperienceLevel.ENTRY: "Beginner",
    ExperienceLevel.INTERMEDIATE: "Intermediate",
    ExperienceLevel.EXPERT: "Expert",
}


def _fit(field: str, value: str | None, truncations: list[str]) -> str | None:
    if value is None:
        return None
    limit = LIMITS.get(field)
    if limit and len(value) > limit:
        truncations.append(f"{field}: {len(value)} characters, Zoho allows {limit}")
        return value[:limit]
    return value


def approved_text_and_quote(
    versions: list[dict[str, Any]], approvals: list[dict[str, Any]]
) -> tuple[str | None, Sections | None]:
    """The version of the most recent approval — the text the client saw."""
    if not approvals:
        return None, None
    latest = max(approvals, key=lambda a: a["approved_at"])
    version = next((v for v in versions if v["id"] == latest["draft_version_id"]), None)
    if version is None:
        return None, None
    from app.routes.proposals import section_text  # noqa: PLC0415 - avoids a cycle

    sections = Sections.model_validate(version["sections"])
    return section_text(sections, "all", None), sections


def build_payload(
    analysis: JobAnalysis,
    approved_text: str | None,
    approved: Sections | None,
    fields: LeadFields | None,
    classification: Classification | None,
    on: date,
    *,
    has_lead: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    job = analysis.parsed
    e = job.engagement
    truncations: list[str] = []
    payload: dict[str, Any] = {"Last_Name": "TBD", "Lead_Source": "Upwork"}
    # Lead_Status is set only when creating the Lead. On an update (a Lead ID
    # is known) it is omitted so a status the operator set in Zoho — the F8
    # outcomes — is never reset to "Submitted Proposal" (ADR-006 §5).
    if not has_lead:
        payload["Lead_Status"] = "Submitted Proposal"
    if job.upwork_job_id:
        payload["Upwork_Job_ID"] = job.upwork_job_id
        payload["Job_Link"] = f"https://www.upwork.com/jobs/{job.upwork_job_id}"
    if job.title:
        payload["Job_Name"] = _fit("Job_Name", job.title, truncations)
    if approved_text:
        payload["Proposal"] = _fit("Proposal", approved_text, truncations)
    payload["Proposal_Date"] = on.isoformat()
    if e.payment_type == PaymentType.HOURLY:
        payload["Rate_Type"] = "Hourly"
        if e.hourly_rate_max is not None:
            payload["Budget"] = float(e.hourly_rate_max)
    elif e.payment_type == PaymentType.FIXED:
        payload["Rate_Type"] = "Fixed"
        if e.fixed_budget is not None:
            payload["Budget"] = float(e.fixed_budget)
    if approved and approved.quote and approved.quote.amount is not None:
        if approved.quote.model == "hourly":
            payload["Hourly_Rate"] = float(approved.quote.amount)
        elif approved.quote.model == "fixed":
            payload["Upwork_Fixed_Price"] = float(approved.quote.amount)
    if job.skills:
        payload["Skills_Required"] = _fit(
            "Skills_Required", ", ".join(job.skills), truncations
        )
    if e.experience_level:
        payload["Client_s_Desired_Experience_Level"] = EXPERIENCE[e.experience_level]
    if analysis.ai and analysis.ai.deliverables:
        payload["Deliverables"] = "\n".join(analysis.ai.deliverables)

    confirmed = fields is not None and fields.confirmed_at is not None
    industry = (fields.industry if confirmed else None) or (
        classification.industry if classification else None
    )
    job_type = (fields.job_type if confirmed else None) or (
        classification.job_type if classification else None
    )
    tools = (fields.tools if confirmed else None) or (
        classification.tools if classification else None
    )
    if industry:
        payload["Industry"] = industry
    if job_type:
        payload["Job_Type"] = job_type
    if tools:
        payload["Tools"] = _fit("Tools", tools, truncations)
    if fields:
        if fields.proposal_link:
            payload["Proposal_Link"] = fields.proposal_link
        payload["By_Invitation"] = bool(fields.by_invitation)
    return payload, truncations


def compute_flags(
    classification: Classification | None, fields: LeadFields | None
) -> list[FieldFlag]:
    """Rule 3: below threshold or off-picklist → flagged, until confirmed."""
    if fields is not None and fields.confirmed_at is not None:
        return []
    if classification is None:
        return [
            FieldFlag(
                field=f, reason="not classified — set it yourself", confidence=None
            )
            for f in ("Industry", "Job_Type", "Tools")
        ]
    flags: list[FieldFlag] = []
    checks = [
        (
            "Industry",
            classification.industry,
            classification.confidence.industry,
            INDUSTRY,
        ),
        (
            "Job_Type",
            classification.job_type,
            classification.confidence.job_type,
            JOB_TYPE,
        ),
        ("Tools", classification.tools, classification.confidence.tools, None),
    ]
    for name, value, conf, allowed in checks:
        if allowed is not None and value not in allowed:
            flags.append(
                FieldFlag(
                    field=name,
                    reason=f'"{value}" is not on the picklist',
                    confidence=conf,
                )  # type: ignore[arg-type]
            )
        elif conf < THRESHOLDS[name]:
            flags.append(
                FieldFlag(  # type: ignore[arg-type]
                    field=name,
                    reason=f"confidence {conf:.2f} below {THRESHOLDS[name]:.2f}",
                    confidence=conf,
                )
            )
    return flags


def build_preview(
    analysis: JobAnalysis,
    versions: list[dict[str, Any]],
    approvals: list[dict[str, Any]],
    fields: LeadFields | None,
    classification: Classification | None,
    classification_failure: AiFailure | None,
    connected: bool,
    *,
    has_lead: bool = False,
) -> LeadPreview:
    approved_text, approved = approved_text_and_quote(versions, approvals)
    payload, truncations = build_payload(
        analysis,
        approved_text,
        approved,
        fields,
        classification,
        datetime.now(UTC).date(),
        has_lead=has_lead,
    )
    flags = compute_flags(classification, fields)
    checklist = [
        ChecklistItem(key="connected", label="Zoho is connected", ok=connected),
        ChecklistItem(
            key="approved",
            label="The proposal has been copied (approved) at least once",
            ok=approved_text is not None,
        ),
        ChecklistItem(
            key="job_id", label="Upwork job ID is known", ok="Upwork_Job_ID" in payload
        ),
        ChecklistItem(
            key="industry", label="Industry is set", ok="Industry" in payload
        ),
        ChecklistItem(
            key="flags", label="Flagged fields confirmed", ok=len(flags) == 0
        ),
    ]
    return LeadPreview(
        payload=payload,
        truncations=truncations,
        flags=flags,
        checklist=checklist,
        ready=all(c.ok for c in checklist),
        classification=classification,
        classification_failure=classification_failure,
        lead_fields=fields,
        picklists={"Industry": INDUSTRY, "Job_Type": JOB_TYPE},
        thresholds=THRESHOLDS,
    )


def payload_hash(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
