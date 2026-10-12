# F8 — Outcomes in, and what the app learns from them: design

Governance entry: [FEATURE_REGISTER.md → F8](governance/FEATURE_REGISTER.md#f8--outcome-feedback-into-rag), **standard** (no AI call when an outcome is recorded; the effect on AI output comes later, through retrieval). Transport and tenancy: [ADR-005](ADRs/ADR-005-zoho-integration.md). Trigger: [ADR-006](ADRs/ADR-006-outcome-trigger.md). Learning approach: [ADR-003](ADRs/ADR-003-rag-learning.md). Wire contract: [ZOHO_INTEGRATION.md → Outcome in](ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho). Screens: [FRONTEND.md](FRONTEND.md).

## What the operator does

1. Once, in **Settings → Outcome webhook**: **Generate secret**. The app shows it once, with the endpoint URL. The operator stores both in Zoho (a Connection, or org variables), adds the `Forge_Sync` field to the Upwork layout, and deploys the three Deluge pieces whose source lives in this repo under `zoho/deluge/`: the shared helper, the **Won** button, and the workflow rule on `Lead_Status`.
2. Weeks after a proposal, in Zoho: clicks **Won**, or changes `Lead_Status` to `Job Closed`, `Lost Lead`, `Junk Lead`, `Not Qualified` or `Withdrawn`. Zoho posts to the app. The Lead's `Forge_Sync` field shows what the app said; on an error the operator also gets an email.
3. In the app, nothing to do. The proposal's **Outcome** tab shows the status, the history, and what was indexed. The home screen's **Attention** strip shows proposals still `submitted` past the nudge age, and any outcomes the app could not match. The **Similar past work** card on the next job review shows the win/loss evidence.

The app never offers an outcome-entry control. The one operator action inside the app is resolving the review queue: telling the app which proposal an unmatched outcome belongs to, or dismissing it.

## Inbound call

```text
Zoho (Deluge helper)
  → POST /api/integrations/zoho/outcome
    Authorization: Bearer <integration secret>        (no user JWT: Zoho has none)
    body: the contract in ZOHO_INTEGRATION.md

backend
  1. size and rate limits (32 KB; 30 requests/min per source IP)
  2. pydantic validation: schema_version, outcome / lost_reason pairing,
     allow-listed `lead` keys only (extra = forbid) → 400 with the error
  3. sha256(secret) → rpc public.record_outcome(secret_hash, payload)
     over PostgREST with the anon key — the only thing that role may call
  4. map the function's result to 200 / 202 / 401 and a message for Forge_Sync
```

`record_outcome` is `SECURITY DEFINER`, `search_path = public`, execute granted to `anon` and nothing else; every other table stays behind RLS. In one transaction it:

- looks up `integration_secrets` by hash → the user, or returns `401`; stamps `last_used_at`;
- finds that user's proposal by `upwork_job_id` (via `job_posts`), or inserts an `outcome_queue` row and returns `202`;
- if the latest `proposal_outcomes` row already has this `outcome` and `lost_reason`, returns `200` as a no-op (a replay changes nothing);
- inserts `proposal_outcomes` (`source = 'zoho'`), updates `proposals.status` and `outcome_recorded_at`, and upserts the proposal's `rag_index` row from the **latest approval's version** (what the client saw) plus the allow-listed Lead values;
- returns `{code, proposal_id, outcome, indexed: true}`.

Any failure rolls back everything and surfaces as `500` to Zoho, which the helper writes to `Forge_Sync` and emails. Nothing is half-recorded.

## The secret

`integration_secrets`: `user_id` PK, `secret_hash` (sha256, unique), `created_at`, `last_used_at`. The plaintext is 32 random bytes, base64url, shown once in Settings and never stored. **Rotate** replaces the row (the old secret stops working at once). RLS: owner select/insert/update/delete; the function reads it as definer. Lookup is by hash, so comparison is not timing-sensitive, and an unknown hash is `401` with the same latency as a known one.

## Storage

One migration, `supabase/migrations/<ts>_outcomes.sql`:

| Table / change | Purpose | RLS |
|---|---|---|
| `integration_secrets` | above | owner all |
| `proposal_outcomes` — **append-only** (`refuse_change` trigger) | `proposal_id`, `user_id`, `outcome`, `lost_reason`, `decided_at`, `zoho_lead_id`, `lead jsonb` (allow-listed values as received), `source` (`zoho` / `manual_match`), `received_at` | owner select; inserts only through the functions |
| `outcome_queue` | unmatched payloads: `user_id`, `upwork_job_id`, `zoho_lead_id`, `payload jsonb`, `received_at`, `resolved_at`, `resolved_proposal_id`, `dismissed_at` | owner select/update |
| `rag_index` | one row per proposal, upserted: `proposal_id` PK, `user_id`, `outcome`, `lost_reason`, `industry`, `job_type`, `tools`, `rate_type`, `budget_band`, `quote_amount`, `job_title`, `job_terms text[]` (F2's normalised terms), `proposal_excerpt` (first 1 500 chars of the copied cover letter), `decided_at`, `archived bool default false`, `indexed_at` | owner select; owner update of `archived` only |
| `proposals` + `outcome_recorded_at` | when the latest outcome landed | existing |
| `profiles` + `stale_submitted_days int default 14` | the nudge age (FRONTEND.md decision, finalised here) | existing |
| `public.record_outcome(secret_hash, payload)` | inbound path, above | execute: `anon` |
| `public.resolve_queued_outcome(queue_id, proposal_id)` | the operator matches a queued outcome; checks `auth.uid()` owns both rows, then does the same write with `source = 'manual_match'`, marks the queue row resolved | execute: `authenticated` |

Append-only is enforced as for approvals and lead attempts: no update/delete policies plus the trigger, with the purge escape for admin sessions.

`rag_index` is derived data. It can always be rebuilt from `proposal_outcomes` + approvals + job posts, which `rebuild_rag_index()` does, behind `POST /api/outcomes/rebuild-index` (built as a function rather than the script first planned, so it also works from the phone).

## Lead out: one change (ADR-006 §5)

`build_payload` includes `Lead_Status = "Submitted Proposal"` only when the proposal has no `zoho_lead_id`. On an update the field is omitted, so a status the operator set is never reset. If Zoho rejects an update-turned-insert for the missing required field, the error is shown and the next press (still no Lead ID) includes it. Test and [ZOHO_INTEGRATION.md](ZOHO_INTEGRATION.md) mapping updated with the code.

## What the app learns (ADR-003)

**Similar past work (F2)** gains a second evidence source. The matcher scores the user's `rag_index` rows with the same term and vocabulary matching it applies to work history (`industry` is Work history's vertical, `job_type` its project type, so they compare directly). `Comparable` gains `kind` (`work_history` / `proposal`) and `outcome`; `MatchStrength` counts both kinds. The card shows "N comparable proposals: W won, L lost" with reasons on hover, replacing the F8 placeholder note. `junk_lead` and `not_qualified` are reported separately from `hired_other` and `job_closed`: "not worth bidding" is a different lesson from "bid and lost". Thin evidence stays labelled thin; fewer than three outcomes in total shows counts only, no verdict.

**Drafting (F3)**, second code PR, behind a profile toggle defaulting to on: when the matcher finds *won* past proposals comparable to the job (the job's industry is not known until the Submit step, so comparability stands in for same-industry), the drafter prompt gets up to three won excerpts (`proposal_excerpt`, the operator's own copied text, nothing from clients) with their job titles, framed as "proposals that won", for voice and structure only. Rule 5 holds: the excerpts are the operator's words, no client data. The prompt section is logged in `ai_meta` so the Outcome tab's "what was indexed" and the version's meta agree.

**Archiving.** The Outcome tab lets the operator mark an indexed proposal `archived` so retrieval skips it (ADR-003 "deprecating old proposals"). The outcome history is untouched.

## Screens (FRONTEND.md)

| Where | What |
|---|---|
| Proposal → **Outcome** tab | status; outcome history (each row: outcome, reason, decided at, received at, source); link to the Lead in Zoho when `zoho_lead_id` is set (`https://crm.zoho.com/crm/tab/Leads/<id>`, with an org-id setting as the fallback if that form does not resolve); "No Lead in Zoho yet" otherwise; the nudge when `submitted` longer than `stale_submitted_days`; **What was indexed** under a disclosure (the `rag_index` row), with **Archive / Unarchive** |
| Home → **Attention** strip | counts with links: Leads whose last attempt failed; outcomes in the review queue; proposals `submitted` past the nudge age |
| Settings → **Outcome webhook** | generate / rotate, secret shown once, endpoint URL, last outcome received, a link to `zoho/README.md` |
| Settings → **Review queue** | each unmatched payload as Zoho sent it, a proposal picker filtered to `submitted` proposals with no outcome, **Match** / **Dismiss** |
| Profile | `stale_submitted_days` |
| Job review → **Similar past work** | the evidence line and comparable proposals, as above |

## Failure path (R8)

| Situation | Behaviour |
|---|---|
| Unknown or rotated secret | `401`; helper writes `ERROR 401 …` to `Forge_Sync` and emails; the app logs the attempt without the payload |
| Invalid payload, unsupported schema, off-allow-list field | `400` with the validation message; same visibility; nothing stored |
| No proposal matches the job ID | `202`; queue row; Attention strip shows it; the operator matches or dismisses |
| Same outcome again | `200` no-op; Forge_Sync says "already recorded" |
| Different outcome later | new history row; status and index follow it |
| Database error mid-write | transaction rolls back; `500`; Forge_Sync + email; the operator re-triggers (re-press **Won**; for a status, set another trigger value then the intended one) |
| App unreachable | Deluge `invokeurl` times out; the helper writes `ERROR timeout` and emails; re-trigger as above |
| Proposal stays `submitted` with no outcome | nudge on the Outcome tab and the Attention strip after `stale_submitted_days` |
| Outcome for a proposal that was never pushed to Zoho | cannot happen from Zoho (no Lead); a manual match from the queue is allowed and records `source = 'manual_match'` |

## API

| Route | Auth | Does |
|---|---|---|
| `POST /api/integrations/zoho/outcome` | bearer secret | the inbound path |
| `GET /api/integrations/outcome-secret` | user JWT | exists?, created, last used, endpoint URL |
| `POST /api/integrations/outcome-secret` | user JWT | generate or rotate; returns the plaintext once |
| `DELETE /api/integrations/outcome-secret` | user JWT | revoke |
| `GET /api/proposals/{id}/outcomes` | user JWT | history + the `rag_index` row + nudge state |
| `PUT /api/proposals/{id}/rag-archived` | user JWT | archive / unarchive |
| `GET /api/outcomes/queue` | user JWT | unmatched outcomes |
| `POST /api/outcomes/queue/{id}/match` | user JWT | `resolve_queued_outcome` |
| `POST /api/outcomes/queue/{id}/dismiss` | user JWT | marks dismissed |
| `GET /api/attention` | user JWT | the strip's counts |
| `GET /api/jobs/{id}/advisory` | user JWT | existing; response gains proposal comparables and outcome counts |

## Zoho side (source in `zoho/`)

- `zoho/deluge/forge_helper.dg` — builds the allow-listed payload from the Lead, posts it with the secret from the Connection, writes `Forge_Sync`, emails on non-2xx or timeout.
- `zoho/deluge/won_button.dg` — calls the helper with `won`; returns the message for the button.
- `zoho/deluge/lead_status_workflow.dg` — called by the workflow rule; maps `Lead_Status` to `outcome` / `lost_reason` per ADR-006 and calls the helper.
- `zoho/README.md` — field, Connection, button, workflow rule and deployment steps, and how to re-trigger.

The allow-list appears in exactly two places, the helper and the app's pydantic model, and the test suite includes the list verbatim so a drift fails CI.

## Tests the code PRs include

Validation: outcome / reason pairing, every allow-listed key accepted, any other key rejected, size limit. Secret: generate → hash stored, plaintext never persisted; rotate invalidates the old hash. Function behaviour, against the local Supabase stack as approvals were: 401, 202 + queue row, first outcome writes all three (history, status, index) or none, replay is a no-op, correction appends, manual match from the queue, `anon` cannot read or write anything but the function. Lead out: `Lead_Status` present on first send, absent on update. Matcher: proposal comparables scored and counted; counts split by reason; fewer than three outcomes → counts only. Drafter: won excerpts included only with a same-industry win and the toggle on; prompt boundary (no client fields) asserted. Attention: each count from fixtures.

## Delivery

1. **F8a** — this design, FRONTEND.md and register pointers (docs PR).
2. **F8b** — migration, functions, inbound route and limiter, secret routes, queue and attention routes, Lead-out change, Deluge source and `zoho/README.md`, rebuild script, tests.
3. **F8c** — Outcome tab, Attention strip, Settings → Outcome webhook and Review queue, Profile setting, Similar past work evidence.
4. **F8d** — drafter context from won proposals (profile toggle), its tests, and the F8 completion docs.

## As built (2026-10-12)

Where the code differs from the plan above:

- `rag_index` has no `job_terms` column. The matcher scores index rows at query time from `skills`, `tools`, title, industry, job type and the excerpt, with the same aliases and stopwords it applies to work history.
- `budget_band` is computed in SQL (`forge_budget_band`) from the Lead's numbers or the quote: under $30/h, $30–75/h, over $75/h; under $1k, $1k–10k, over $10k.
- The rebuild is a SQL function behind a route, not a script.
- Won examples for the drafter are chosen by comparability, not same industry; `ai_meta.won_examples_used` on the version records which titles were shown.
- The Lead snapshot stored with an outcome holds only the fields Zoho actually sent (nulls dropped), so the history shows what arrived.
- The advisory's Claude call still requires at least one work-history comparable; outcome evidence alone is shown as counts without a verdict.
