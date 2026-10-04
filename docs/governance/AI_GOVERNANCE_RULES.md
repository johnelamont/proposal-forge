# Lamont Consulting
## AI Development Governance Rules
### Human-in-the-Loop & Responsible Automation Standards — v1.0

These rules apply to all AI-assisted features, automations, and agents built under the Lamont Consulting delivery model. They are design requirements, not guidelines — each rule must be satisfied before a feature is considered complete. Rules are grouped by the phase at which they primarily apply, though most have cross-phase implications.

> In this repo: adopted by [ADR-004](../ADRs/ADR-004-ai-governance.md). Per-feature classifications and determinations live in [FEATURE_REGISTER.md](FEATURE_REGISTER.md).

---

## Quick Reference by Phase

| Phase | Rule | Category |
|---|---|---|
| Pre-Engagement | Rule 6 — Regulated Data Checkpoint | Pre-Engagement |
| Pre-Build | Rule 4 — Legal and ToS Compliance | Pre-Build / Legal |
| Design | Rule 7 — High-Stakes Classification | Design / Governance |
| Design | Rule 5 — Minimum Data Access | Data / Privacy |
| Build | Rule 1 — No Auto-Execute on High-Stakes | UX / Architecture |
| Build | Rule 2 — Log the Human Reviewer | Data / Audit |
| Build | Rule 3 — Confidence-Threshold Routing | Architecture |
| Build | Rule 8 — Defined Failure Behavior | Architecture |
| Build | Rule 9 — Client-Facing AI Disclosure | UX / Legal |

---

## The Rules

### Rule 1 — No Auto-Execute on High-Stakes Outputs
*Category: UX / Architecture*

- Any AI-generated output that affects legal, financial, HR, medical, or public-facing content must route through an explicit human approval step before any downstream action (send, save, publish, update).
- The UI must require an affirmative action — no default-proceed, no auto-timeout confirmation.
- This is a UX and architecture requirement. If there is no approval screen, the feature is not complete.
- See Rule 7 for how to classify whether an output qualifies as high-stakes.

---

### Rule 2 — Log the Human Reviewer
*Category: Data / Audit*

- Any system where a human approves AI output must write an audit record: who approved, when, and what was approved.
- This is a schema requirement, not an afterthought. If the data model does not have a reviewer field, the feature is not done.
- Audit records must be write-once or append-only where technically feasible. Post-approval modification of AI output must itself be logged.
- This record is the primary liability defense for the client in the event of audit, litigation, or regulatory inquiry.

---

### Rule 3 — Confidence-Threshold Routing
*Category: Architecture*

- When AI output drives automated data operations (CRM updates, classification, routing), the system must expose a confidence signal.
- A threshold must be defined below which the record routes to a human queue rather than auto-processing.
- The threshold is domain-specific — not a fixed number — and must be explicitly set and documented per use case during design, not tuned post-deployment.
- Failure to meet threshold is not an error state. It is a normal routing outcome and must be handled gracefully.

---

### Rule 4 — Legal and ToS Compliance for Downstream Systems
*Category: Pre-Build / Legal*

- Before building any automation or agent that interacts with an external system, explicitly verify: (a) the applicable ToS permits the intended access method and use, and (b) no applicable law prohibits it.
- Both determinations must be documented at design time.
- If either is ambiguous, flag it to the client before proceeding — do not assume permissibility.
- For long-running automations, include a review trigger when the target system updates its ToS.
- This rule applies regardless of how common or routine the automation pattern appears.

---

### Rule 5 — Minimum Access for PII and Sensitive Data
*Category: Data / Privacy*

- Any AI agent or automation must be scoped to the minimum data necessary to complete the specific task.
- PII, PHI, and financial records must not be passed to an AI component unless that field is explicitly required for the output.
- This is a schema and prompt design requirement — filter before you send, not after.
- Broad context dumps that happen to contain sensitive data are not compliant by design intent.
- Access scope must be documented per feature, not assumed from system-wide access grants.

---

### Rule 6 — Regulated Data Client Engagement Checkpoint
*Category: Pre-Engagement*

Before accepting or continuing work for any client whose data environment may involve HIPAA (US) or GDPR special-category data (EU), the following must be resolved before any build begins:

- Determine if a BAA is required and execute it before any PHI touches any system you build or operate.
- Verify that any third-party AI API vendor (including Anthropic) has a compliant BAA in place for that use case.
- Confirm that AI input/output logs containing PHI are stored in compliant infrastructure.
- For EU clients, assess both GDPR special-category obligations and EU AI Act risk classification independently. Compliance with one does not imply the other.
- Document the determination. "We checked and it does not apply" is as important to record as "it applies and here is how we addressed it."

---

### Rule 7 — Explicit High-Stakes Classification at Design Time
*Category: Design / Governance*

- Every AI-assisted feature must be explicitly classified as high-stakes or standard during the design phase, before any build begins.
- The classification must be documented.
- If a feature touches decisions that affect a person's legal status, financial standing, employment, health, housing, or public reputation, it is high-stakes by default.
- When the classification is ambiguous, it defaults to high-stakes.
- This classification drives which other rules apply. It is not revisited at runtime.

---

### Rule 8 — Defined Failure Behavior
*Category: Architecture*

- Every AI component must have an explicitly designed failure path.
- If the AI returns no result, a malformed result, an error, or a confidence score below threshold, the system must route to a human queue or halt.
- Never silently proceed. Never silently fail.
- The failure behavior must be specified at design time, not handled ad hoc during debugging.
- Silent automation failures in SMB systems are a direct liability risk because no one is watching.

---

### Rule 9 — Client-Facing AI Disclosure
*Category: UX / Legal*

- Any system where an SMB's customer is interacting with or being processed by AI must disclose that fact at the appropriate touchpoint.
- This applies to chatbots, automated email responses, AI-scored applications, and automated decisioning.
- The disclosure must be explicit. "AI-assisted" buried in a terms of service does not qualify.
- Where applicable law mandates specific disclosure language, that language governs.
- Where no law mandates it, disclose anyway as a default position.

---

## Application Notes

These rules are minimum requirements. Client-specific regulatory environments, industry verticals, or contractual obligations may impose additional constraints beyond what is stated here.

Rules 4 and 6 are the only pre-build gates — no code should be written for a feature until both are satisfied where applicable. All other rules are build-time constraints that must be verified during design review and confirmed in delivery.

This document is a living reference. Rules will be updated as regulatory landscape, client experience, and tooling evolve. Version should be incremented on any substantive change to rule text.

---

*Lamont Consulting — AI Governance Rules v1.0*
