# F6 — Zoho Lead out: design

Governance entry: [FEATURE_REGISTER.md → F6](governance/FEATURE_REGISTER.md#f6--zoho-lead-creation-webhook), **high-stakes** (a CRM write, a financial pipeline record). Transport, auth and tenancy: [ADR-005](ADRs/ADR-005-zoho-integration.md). Field mapping: [ZOHO_INTEGRATION.md](ZOHO_INTEGRATION.md). Screen: [FRONTEND.md → Submit tab](FRONTEND.md#workspace--proposalsid).

## What the operator does

1. Once, in **Settings → Zoho**: **Connect**. Zoho asks them to approve two scopes (create and update Leads); the app stores their refresh token encrypted. **Disconnect** revokes it.
2. After submitting a proposal on Upwork by hand, open the proposal's **Submit** tab. The app shows the **Lead preview**: every field it will send, with the AI-derived ones carrying a confidence; below-threshold or off-picklist values are flagged amber and must be confirmed or edited. A required-field checklist sits above the button.
3. **Create Lead**. The app upserts the Lead (matched on `Upwork_Job_ID`, so a second press changes nothing), marks the proposal `submitted`, stores the Zoho Lead ID, and logs the attempt. Failure → "Lead not created — retry", never silent.

## Connecting Zoho (OAuth, per user)

Server-based client (`ZOHO_CLIENT_ID` / `ZOHO_CLIENT_SECRET` in the backend's environment); scopes `ZohoCRM.modules.leads.CREATE,ZohoCRM.modules.leads.UPDATE`; no read scope — the app never reads Leads.

```text
Settings → Connect
  → GET /api/integrations/zoho/connect        (user JWT) creates a one-time state
                                                row for this user, returns Zoho's
                                                authorize URL
  → browser: Zoho consent
  → Zoho → GET /api/integrations/zoho/callback?code&state   (no JWT: a redirect)
                                                backend only redirects the browser to
                                                FRONTEND_URL/settings/zoho?code&state
  → frontend: POST /api/integrations/zoho/complete {code, state}   (user JWT)
                                                backend checks the state row is this
                                                user's and unexpired (then deletes
                                                it), exchanges the code at
                                                ZOHO_ACCOUNTS_URL/oauth/v2/token,
                                                encrypts the refresh token
                                                (AES-GCM, TOKEN_ENCRYPTION_KEY) and
                                                upserts zoho_connections for the user
```

Completing the exchange from the frontend keeps every database write under the user's own JWT and RLS — no `SECURITY DEFINER`, no service-role key. The authorization code is single-use and expires within a minute, so carrying it through the browser is the standard flow. Access tokens are minted from the refresh token on demand and cached in memory until they expire; they are never stored.

## The Lead

Payload per [ZOHO_INTEGRATION.md → Lead out](ZOHO_INTEGRATION.md#lead-out--on-create-lead). Sources:

| Field group | From |
|---|---|
| Constants: `Last_Name="TBD"`, `Lead_Source="Upwork"`; `Lead_Status="Submitted Proposal"` on the first send only (omitted on an update once a Zoho Lead ID is known, ADR-006 §5) | code |
| `Upwork_Job_ID`, `Job_Name`, `Job_Link`, `Budget`, `Rate_Type`, `Skills_Required`, `Client_s_Desired_Experience_Level`, `Deliverables` | F1's parse and reading |
| `Proposal`, `Hourly_Rate` / `Upwork_Fixed_Price` | the **latest copied (approved) version** — the text the client actually saw — and its quote |
| `Proposal_Date` | the Create Lead click |
| `Proposal_Link`, `By_Invitation` | typed / toggled by the operator on the Submit tab |
| `Industry`, `Job_Type`, `Tools` | **AI-derived** (below) |

**Create Lead is disabled until**: Zoho is connected; at least one approval exists (nothing has been copied → nothing was submitted → no Lead); `Upwork_Job_ID` is present; `Industry` is set and confirmed; every flagged field is confirmed. Values longer than a field's limit are shown truncated in the preview before sending.

## AI-derived fields (Rule 3)

One Claude call (`services/lead_classifier.py`) receives the job title, description, skills and F1's reading, and returns `Industry` and `Job_Type` **constrained to the picklists in `app/config/picklists.json`**, plus `Tools` (free text, ≤255), each with a confidence 0–1.

Thresholds, recorded in the register and in `picklists.json`: **`Industry` 0.7, `Job_Type` 0.7, `Tools` 0.6**. Below threshold → flagged, must be confirmed. A value not on the picklist → always flagged, whatever the confidence (the API would reject it anyway). The operator's confirmation or edit is stored on the proposal (`lead_fields`) and reused on retry; the classifier is not re-run unless asked.

The picklists are **the shared vocabulary**: the same `industry` list is Work history's vertical and the same `job_type` list is its project type, so a Lead's industry and a past project's vertical compare directly in F2. Zoho's picklists must be changed to match the file before it is changed (the API rejects unknown values).

## Storage

Migration adds:

- `zoho_connections` — `user_id` PK, `refresh_token_enc`, `api_domain`, `accounts_url`, `scopes[]`, `connected_at`, `last_used_at`. RLS: owner select/insert/update/delete.
- `zoho_oauth_states` — `nonce`, `user_id`, `expires_at`. RLS owner; rows live ten minutes.
- `proposals` + `zoho_lead_id`, `lead_sync_state` (`none` | `created` | `failed`), `lead_fields jsonb` (the operator-confirmed AI fields, `Proposal_Link`, `By_Invitation`), `submitted_at`.
- `lead_attempts` — **append-only** (same trigger as approvals): `proposal_id`, `payload_hash`, `response_status`, `zoho_lead_id`, `error`, `attempted_by`, `attempted_at`. This is F6's R2 record.

## Failure path (R8)

| Situation | Behaviour |
|---|---|
| Not connected | Submit tab shows **Connect Zoho** instead of the preview |
| Refresh token rejected (revoked, expired) | "Zoho connection needs renewing" → **Reconnect**; nothing sent |
| Classifier error / empty / malformed | AI fields blank and flagged; operator fills them; Create Lead still possible once confirmed |
| Upsert error (4xx/5xx, network) | `lead_sync_state = failed`, attempt logged with Zoho's message, proposal stays as it was; visible **Retry** |
| Zoho reports a duplicate on a *different* key (e.g. `Job_Link` unique clash) | surfaced verbatim; the operator resolves in Zoho |
| Repeat press after success | upsert on `Upwork_Job_ID` → same Lead; a new attempt row, no new Lead |

## API

| Route | Does |
|---|---|
| `GET /api/integrations/zoho/status` | connected?, since when, scopes |
| `GET /api/integrations/zoho/connect` | state + authorize URL |
| `GET /api/integrations/zoho/callback` | redirect to the frontend with code and state |
| `POST /api/integrations/zoho/complete` | exchange + store (user JWT) |
| `DELETE /api/integrations/zoho/connection` | revoke at Zoho, delete row |
| `GET /api/proposals/{id}/lead-preview` | payload, flags, checklist, truncations (runs the classifier once; cached on the proposal) |
| `PUT /api/proposals/{id}/lead-fields` | operator's confirmations: Industry, Job_Type, Tools, Proposal_Link, By_Invitation |
| `POST /api/proposals/{id}/create-lead` | upsert, log, set state |

## Tests the code PR includes

Token encryption round-trip; state nonce single-use and expiry; payload builder against the three fixtures with an approved version (field by field, constants, truncation markers, nothing from the Rule 5 "not sent" list); classifier constrained to picklists with mocked outputs incl. off-picklist → flagged; threshold flagging; checklist gating (no approval, no job ID, flagged Industry); create-lead with a fake Zoho client: success, 4xx, network, repeat press; attempts append.
