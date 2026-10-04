# Zoho CRM Integration

How Proposal Forge creates Leads in Zoho CRM and receives outcomes back. Design rationale: [ARCHITECTURE.md — Zoho Integration](ARCHITECTURE.md#zoho-integration-lead-out-outcome-in) and [ADR-005](ADRs/ADR-005-zoho-integration.md).

Field names below are Zoho API names from the operator's Leads module metadata (2026-10-04). Leads are created on the **Upwork** layout.

## Zoho-side setup

1. **Make `Upwork_Job_ID` unique.** The field exists (text, 255) but currently allows duplicates. Upsert needs it unique to match on it.
   - First, check for existing duplicate values.
   - Then enable *Do not allow duplicate values* on the field.
2. **Find the Upwork layout ID.** Lead creation must specify it, so Zoho applies that layout's required fields and picklist values.
3. **Register an API client** for Lead creation. In the Zoho API Console, create a *server-based application* with the backend's OAuth callback as the redirect URI. Scopes:
   - `ZohoCRM.modules.leads.CREATE`
   - `ZohoCRM.modules.leads.UPDATE`
4. **Store the integration secret.** Generate it in Proposal Forge settings, then store it in Zoho as a Connection (preferred) or org variable. Never paste it into function code.
5. **Add the Deluge functions.** Source lives in this repo once written. Deploy manually:
   - a shared helper that builds the allow-listed payload and posts it;
   - the **Won** button on the Lead (Upwork layout), which calls the helper with `won` and shows the result message;
   - *Trigger to be decided:* how `Lost Lead`, `Job Closed`, and `Withdrawn` are sent (workflow rule on `Lead_Status`, buttons, or something else). Whatever is chosen calls the same helper, and must show or notify the result on failure. The endpoint already accepts these outcomes.

## Lead out — on **Create Lead**

`POST /crm/v8/Leads/upsert` with the Upwork `Layout` and `duplicate_check_fields: ["Upwork_Job_ID"]`. The returned Lead ID is stored on the proposal.

| Zoho field (API name) | Type | Value | Source |
|---|---|---|---|
| `Last_Name` | text(80), **layout-required** | `"TBD"` | Constant. No client identity at proposal stage |
| `Lead_Source` | picklist, **layout-required** | `"Upwork"` | Constant |
| `Lead_Status` | picklist, **layout-required** | `"New Lead"` | Constant |
| `Upwork_Job_ID` | text(255), unique | Upwork job ID | Parsed from job URL, or entered by user |
| `Industry` | picklist (values in use on the layout) | Client's industry | **AI-derived** (note 1); required by the app |
| `Job_Name` | text(255) | Job title | Parsed |
| `Job_Link` | url, unique | Job URL | Parsed or pasted |
| `Proposal_Link` | url, unique | Proposal URL | Pasted after submission |
| `Proposal_Date` | date | Date of the **Create Lead** click | App |
| `Proposal` | textarea(32000) | The copied (approved) proposal text, all sections | `proposal_approvals` |
| `Rate_Type` | picklist: Hourly / Fixed | Job's rate type | Parsed |
| `Hourly_Rate` | currency | Quoted rate, if hourly | Approved quote |
| `Upwork_Fixed_Price` | currency | Quoted price, if fixed | Approved quote |
| `Budget` | double | Client's posted budget | Parsed |
| `Skills_Required` | text(255) | Skills listed on the job, comma-separated | Parsed |
| `Client_s_Desired_Experience_Level` | picklist: Expert / Intermediate / Beginner | From job post | Parsed |
| `Deliverables` | textarea | Deliverables from job post | Parsed |
| `By_Invitation` | boolean | Whether the job came by invite | User toggle |
| `Job_Type` | picklist (Zoho CRM, Zoho One, CRM + Creator, …, Other) | Job category | **AI-derived** (note 1) |
| `Tools` | text(255) | Tech stack | **AI-derived** (note 1) |

Notes:

1. **AI-derived fields (Rule 3).** `Industry` and `Job_Type` are constrained to the picklist values in use on the Upwork layout. Each AI-derived field carries a confidence value. Below threshold, the field is flagged in the pre-send preview and must be confirmed or edited. Thresholds are set and recorded in [feature register F6](governance/FEATURE_REGISTER.md).
2. **Length limits.** Values longer than a field's limit (e.g., `Skills_Required` at 255) are shown truncated in the preview before sending, never silently cut.

### Required before **Create Lead**

**Create Lead** stays disabled until all of these have values. The app never sends an incomplete Lead.

- The three layout-required fields: `Lead_Status`, `Last_Name`, `Lead_Source`. These are always set to the constants above.
- `Industry`, confirmed by the operator if below the confidence threshold.
- `Upwork_Job_ID`, the integration key.

**Deliberately not sent (Rule 5):**
- Contact and identity fields: `First_Name`, `Email`, `Phone`, `Mobile`, `Company`, address fields, `Website`. None are known at proposal stage.
- `Company` is not required in this setup. It stays blank until a proposal goes to contract and is never sent back to the app.
- Fields the app has no source for: `Upwork_Fee_for_Fixed_Price`, `Description`.
- Legacy fields: `Hourly` (boolean, superseded by `Rate_Type`) and `Upwork_Proposal_Link` (superseded by `Proposal_Link`).

## Outcome in — pushed by Zoho

`POST /api/integrations/zoho/outcome` with `Authorization: Bearer <integration secret>`.

```json
{
  "schema_version": "1.0",
  "upwork_job_id": "~01a2b3c4d5e6f7a8b9",
  "zoho_lead_id": "4385039000123456789",
  "outcome": "won",
  "lost_reason": null,
  "decided_at": "2026-10-20T09:00:00-07:00",
  "lead": {
    "Industry": "Insurance",
    "Job_Type": "Zoho CRM",
    "Tools": "Zoho CRM, Deluge",
    "Rate_Type": "Fixed",
    "Hourly_Rate": null,
    "Upwork_Fixed_Price": 9500,
    "Budget": 10000
  }
}
```

**Outcome sources:**

| Zoho trigger | `outcome` | `lost_reason` |
|---|---|---|
| **Won** button | `won` | — |
| `Lead_Status` = `Lost Lead` (trigger TBD) | `lost` | `hired_other` |
| `Lead_Status` = `Job Closed` (trigger TBD) | `lost` | `job_closed` |
| `Lead_Status` = `Withdrawn` (trigger TBD) | `withdrawn` | — (recorded and indexed, excluded from win/loss rates) |

**`lead` allow-list (Rule 5).** These are the only Lead fields the helper may send, and the app rejects any others with `400`:
- `Industry`, `Job_Type`, `Tools`
- `Rate_Type`, `Hourly_Rate`, `Upwork_Fixed_Price`, `Budget`
- `Skills_Required`, `Deliverables`, `Client_s_Desired_Experience_Level`

Never sent: `Company`, `First_Name`, `Last_Name`, `Email`, `Secondary_Email`, `Phone`, `Mobile`, address fields, `Website`, `Description`, `Email_1` (Contract Email). To add a field, extend the allow-list deliberately, in both the Deluge helper and the app's validator.

**Processing:** one `SECURITY DEFINER` function, in one transaction:
- resolves the user from the secret hash;
- matches the proposal on `upwork_job_id`;
- appends to `proposal_outcomes`, updates `proposals.status`, and writes the `rag_index` row from the copied (approved) proposal version plus the allow-listed Lead values.

**Responses** (the button shows a message for each):

| Code | Meaning | Message shown on the button |
|---|---|---|
| `200` | Recorded. A repeat of the current outcome is a no-op. | "Recorded as won in Proposal Forge" |
| `202` | No proposal matches the job ID. Held in a review queue in the app, not dropped. | "No matching proposal — held for review in Proposal Forge" |
| `400` | Invalid payload, unsupported `schema_version`, or a field outside the allow-list. | The validation error |
| `401` | Unknown or revoked secret. | "Proposal Forge rejected the integration secret — regenerate it in settings" |

## Open questions

- **Trigger for lost and withdrawn.** Deferred by the operator. The endpoint and contract support all three outcomes now; only the Zoho-side trigger is undecided.

## Resolved (2026-10-04)

- The `lead` allow-list above is confirmed as the full set of fields a win carries.
- Leads are created on the Upwork layout. Its required fields are `Lead_Status` = `New Lead`, `Last_Name` = `TBD`, and `Lead_Source` = `Upwork`.
- The **Won** button posts to the app; it doesn't set a Zoho field.
- `Company` stays blank at Lead creation and is not sent back.
- `Proposal_Link` is the current proposal link field. `Hourly` (boolean) is legacy and not set.
- `Withdrawn` maps to its own `withdrawn` outcome.
- `Industry` values are taken from those in use on the layout. The duplicate `Management ISV` / `ManagementISV` entries are unused.
