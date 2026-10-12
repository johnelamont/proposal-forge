# Zoho-side pieces for Proposal Forge

Everything the app needs inside Zoho CRM, with the source kept here for review. Deployment is manual; nothing in this folder is executed by the app. Design: [docs/F8_OUTCOMES.md](../docs/F8_OUTCOMES.md), trigger decision: [ADR-006](../docs/ADRs/ADR-006-outcome-trigger.md), wire contract: [docs/ZOHO_INTEGRATION.md](../docs/ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho).

## One-time setup

1. **Field.** Leads module, Upwork layout: add a single-line field **Forge_Sync** (API name `Forge_Sync`, 255 chars). Both functions write their result there.
2. **Secret.** In the app, Settings → Outcome webhook → **Generate secret**. Copy the secret and the endpoint URL; they are shown once.
3. **Org variables.** Setup → Developer Space → Organization Variables:
   - `forge_endpoint` = the endpoint URL from the app
   - `forge_secret` = the secret
   - `forge_alert_to` = your email, for failure alerts
4. **Helper function.** Setup → Developer Space → Functions → New: category *Standalone*, name `forge_post_outcome`, arguments `leadId` (Int), `outcome` (String), `lostReason` (String). Paste [deluge/forge_helper.dg](deluge/forge_helper.dg).
5. **Won button.** Leads → Links and Buttons → New button, Upwork layout, detail page, action *Writing function*: name `forge_won`, argument `leadId` = `Lead Id`. Paste [deluge/won_button.dg](deluge/won_button.dg).
6. **Workflow rule.** Setup → Automation → Workflow Rules → Leads: *On edit*, when **Lead Status** is modified, condition **Lead Status** is one of `Job Closed`, `Lost Lead`, `Junk Lead`, `Not Qualified`, `Withdrawn`, layout Upwork. Instant action → Function: name `forge_lead_status`, argument `leadId` = `Lead Id`. Paste [deluge/lead_status_workflow.dg](deluge/lead_status_workflow.dg).

## How outcomes flow

| Operator does | Zoho sends | App answers (written to `Forge_Sync`) |
|---|---|---|
| Clicks **Won** | `won` | `Recorded won …` |
| Sets Lead Status to Lost Lead | `lost` / `hired_other` | `Recorded lost (hired_other) …` |
| … Job Closed | `lost` / `job_closed` | |
| … Junk Lead | `lost` / `junk_lead` | |
| … Not Qualified | `lost` / `not_qualified` | |
| … Withdrawn | `withdrawn` | `Recorded withdrawn …` |
| Same outcome again | same | `Already recorded …` |
| Lead whose job ID the app does not know | any | `No matching proposal — held for review …` (Settings → Review queue in the app) |

On any error (`ERROR 401 …`, `ERROR 400 …`, `ERROR 500 …`, `ERROR timeout …`) the helper also emails `forge_alert_to`.

## Re-triggering

- **Won:** press the button again.
- **Lost / withdrawn:** the rule fires on a change of Lead Status. Set it to another closing value, save, then set the intended one and save again.

## Rotating the secret

Generate a new one in the app (the old one stops working at once), then update `forge_secret`. Until you do, every post returns `ERROR 401` and you get an email.

## Allow-list

The helper sends only these Lead fields: `Industry`, `Job_Type`, `Tools`, `Rate_Type`, `Hourly_Rate`, `Upwork_Fixed_Price`, `Budget`, `Skills_Required`, `Deliverables`, `Client_s_Desired_Experience_Level`. The app rejects anything else (`400`). Names, email, phone, company and address never leave Zoho. The same list lives in `backend/app/models/outcomes.py`; a test keeps the two identical.
