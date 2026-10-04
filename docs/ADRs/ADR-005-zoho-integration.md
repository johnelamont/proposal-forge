# ADR-005: Zoho CRM Integration — Transport, Authentication, and Tenancy

**Status:** Accepted  
**Date:** 2026-10-04  
**Deciders:** John Lamont

## Context

Proposal Forge exchanges two things with the operator's Zoho CRM ([ARCHITECTURE.md — Zoho Integration](../ARCHITECTURE.md#zoho-integration-lead-out-outcome-in)):

1. **Lead out.** When the operator clicks **Create Lead** after submitting a proposal on Upwork, a Lead is created on the *Upwork* layout, keyed on the existing `Upwork_Job_ID` field.
2. **Outcome in.** Weeks later, the operator records the result in Zoho, and the app needs it to feed the RAG index ([ADR-003](ADR-003-rag-learning.md), [feature register F8](../governance/FEATURE_REGISTER.md)).
   - **Won:** a **Won** button on the Lead posts the win to the app, together with Lead details added since creation.
   - **Lost / withdrawn:** recorded as `Lead_Status` values (`Lost Lead`, `Job Closed`, `Withdrawn`).

Constraints:

- **Tenant boundary.** Supabase RLS is the tenant boundary. Backend calls made for a user must use that user's JWT, not the service-role key (CLAUDE.md). An inbound call from Zoho has no user JWT.
- **Governance.**
  - Rule 4: the access method must be permitted.
  - Rule 5: minimum data. By the time a Lead is won it may hold client identity (`Company`, names, email), none of which the app or RAG needs.
  - Rule 8: failures are visible, never silent.
- **Cost.** Zoho API calls consume credits.

## Options Considered

### Outcome in

#### Option A: Zoho pushes to the app — **Recommended**

Zoho calls `POST /api/integrations/zoho/outcome`:
- **Won:** the **Won** button's Deluge function makes the call.
- **Lost / withdrawn:** the same endpoint and contract. The Zoho-side trigger (workflow rule, buttons, or other) is deferred; whichever is chosen calls the same helper.

The request carries a per-user bearer secret. The backend passes the payload and the secret's hash to one narrowly scoped `SECURITY DEFINER` Postgres function. That function:
- resolves the user from the secret hash;
- matches the proposal on that user's `upwork_job_id`;
- appends to `proposal_outcomes` and writes the `rag_index` row in one transaction.

The endpoint can execute only that function; it holds no service-role key.

| | |
|---|---|
| **Fit with the workflow** | Matches how the operator works: a deliberate button click is the moment a win is recorded |
| **Latency** | Real-time |
| **Tenant boundary** | Preserved through a narrow, auditable mechanism (secret → one user, one function, insert-only), not a general-purpose key |
| **Attack surface** | A public write endpoint. Mitigated by a 256-bit secret compared by hash, rate limiting, strict payload validation, and idempotency (a replay can't change anything) |
| **Zoho-side work** | Won button function + shared helper + stored secret (plus the lost/withdrawn trigger, once chosen), maintained outside this repo. Their source is kept in this repo for review. |
| **Failure visibility** | Button: Zoho shows the function's return message to the operator, success or error. Workflow: the function notifies the operator on any non-2xx. App: lists proposals still `submitted` after N days. |

#### Option B: The app pulls from Zoho

While signed in, the backend reads Lead state through the user's Zoho OAuth connection and writes under the user's JWT.

Not chosen, for two reasons. A won Lead carries information the operator adds at the moment of winning, and a deliberate push from the button captures exactly that. Pull would also need broad read access to Leads, which by then hold client PII; the push side decides exactly which fields leave Zoho. Pull remains a possible fallback for reconciliation (see *What we'll need to revisit*).

#### Option C: Push, written with the service-role key — Rejected

It bypasses RLS for a public endpoint and contradicts the tenant-boundary convention.

#### Option D: Backend mints a JWT for the user on inbound calls — Rejected

The backend would have to hold the Supabase JWT signing secret, which is as powerful as the service-role key.

### Lead out

| Option | Assessment |
|---|---|
| **Zoho CRM REST API `upsert`, called by the backend — Recommended** | No Zoho-side code for creation. The field mapping lives in this repo, versioned and tested. Zoho validates picklists, types, and layout-required fields. |
| POST to a Deluge function that creates the Lead | The mapping would live in Zoho, outside review and tests, and would need its own auth. |

## Decision

1. **Outcomes: Option A (push).** **Won** button for wins. `Lost Lead`, `Job Closed`, and `Withdrawn` use the same endpoint, helper, and contract; their Zoho-side trigger is decided later and needs no change to the app. Contract: ([ZOHO_INTEGRATION.md](../ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho)).
2. **Inbound auth: per-user integration secret.**
   - **Issuing:** generated in the app's settings and shown once. The app stores only its hash; rotating it revokes the old one immediately.
   - **Storage in Zoho:** in a Connection (preferred) or an org variable, never hard-coded in function source.
   - **Writes:** go through a single `SECURITY DEFINER` function, executable by the endpoint's role and nothing else.
3. **Minimum data on the way in (Rule 5).**
   - The Deluge helper builds the payload from an explicit allow-list of Lead fields.
   - The app rejects (`400`) any payload with fields outside the allow-list, so drift is caught loudly instead of storing PII quietly.
   - `Company`, contact names, email, phone, and address are never sent.
4. **Lead creation: CRM REST API upsert** on the *Upwork* layout with `duplicate_check_fields: ["Upwork_Job_ID"]`.
   - **OAuth:** one Zoho OAuth connection per user (server-based client). Scopes are limited to create and update on Leads.
   - **Token storage:** the refresh token is kept in a user-owned table under RLS, encrypted with a key held only by the backend.
5. **Failure behavior (Rule 8):**
   - **Button:** returns a message the operator sees ("Recorded as won in Proposal Forge" / "No matching proposal — held for review" / the error).
   - **Lost / withdrawn trigger:** whichever is chosen must show or notify the result on failure.
   - **Unmatched job ID:** the outcome is held in a review queue, never dropped.
   - **App side:** surfaces stale `submitted` proposals.
   - **Lead creation:** a failure shows "Lead not created — retry".

## Consequences

**What becomes easier:**
- Wins are recorded at the moment the operator decides, with whatever they added to the Lead, in one click.
- Zoho decides exactly which fields leave it; the app never has read access to client PII.
- The RLS convention holds: no service-role key, and the inbound exception is one insert-only function tied to one user's secret.

**What becomes harder:**
- A public endpoint to secure and monitor; secret rotation must be supported.
- Deluge functions live in Zoho. Their source is kept in this repo, but deployment is manual.
- The app still handles Zoho OAuth for Lead creation.

**What we'll need to revisit:**
- If pushes are missed in practice (the stale-`submitted` list keeps growing), add a pull-based reconciliation using Option B with a narrowly scoped read.
- Zoho API version upgrades, and Zoho API terms or credit limits per edition (Rule 4 review trigger).
- The allow-list, whenever fields are added to the Upwork layout.

## Related Decisions

- ADR-001: Supabase — RLS as the tenant boundary drives the inbound auth design.
- ADR-003: RAG learning — the consumer of outcomes.
- ADR-004: AI governance — Rules 4, 5, and 8 shape the access method, payload, and failure paths.
