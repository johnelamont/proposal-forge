# ADR-004: Adopt Lamont Consulting AI Governance Rules

**Status:** Accepted  
**Date:** 2026-10-04  
**Deciders:** John Lamont

## Context

Proposal Forge uses Claude to parse job posts, draft proposals (including price quotes), summarize past work, and classify outcomes that feed a RAG index and a Zoho CRM webhook. Several of those outputs leave the app: proposals go to prospective clients on Upwork, leads land in a CRM, and the portfolio PDF is attached to job applications.

Lamont Consulting applies a fixed set of AI governance rules to every AI-assisted feature it builds. This project is both a working tool and a public portfolio piece, so it should demonstrate those rules in practice, not just claim them.

## Decision

Adopt [AI Governance Rules v1.0](../governance/AI_GOVERNANCE_RULES.md) for everything built in this repo.

Concretely:

1. **Classify before building (Rule 7).** Every AI-assisted feature gets an entry in [FEATURE_REGISTER.md](../governance/FEATURE_REGISTER.md) with a high-stakes/standard classification, data scope (Rule 5), failure path (Rule 8), and any ToS/legal determination (Rule 4) — before code for that feature is written.
2. **Pre-build gates (Rules 4 and 6).** A feature whose register entry has an unresolved ToS/legal question does not start until the question is resolved or explicitly accepted by the decider.
3. **Approval and audit are schema, not UI polish (Rules 1, 2).** High-stakes outputs require an explicit affirmative action and an append-only approval record (who, when, which exact content version). Migrations for those features include the audit table.
4. **Definition of done** for an AI feature includes: register entry complete, failure path implemented and tested, and (if high-stakes) approval + audit record implemented.

The register is a living document; this ADR is not edited when classifications change. A change to the rules themselves, or to how this repo applies them, gets a new ADR.

## Consequences

**What becomes easier:**
- Reviewers can see, per feature, why it is or isn't gated and what data reaches Claude.
- Audit trail of what was approved and sent exists from day one rather than being retrofitted.

**What becomes harder:**
- Every AI feature carries extra design work and a small schema cost (approval/audit tables).
- Some planned flows gain a click or an audit write (e.g., copying a proposal is logged as its approval).

**What we'll need to revisit:**
- Open questions listed in the register before the affected features are built.
- Rule versions: if the governance rules move past v1.0, update the copy in `docs/governance/` and note the change in a new ADR.

## Related Decisions

- ADR-001: Supabase — RLS and Postgres make append-only audit tables straightforward.
- ADR-003: RAG learning — outcome classification feeding the index falls under Rules 3 and 5.
