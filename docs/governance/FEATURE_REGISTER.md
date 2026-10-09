# AI Feature Register

Design-time record required by [AI Governance Rules v1.0](AI_GOVERNANCE_RULES.md) and [ADR-004](../ADRs/ADR-004-ai-governance.md). Every AI-assisted feature needs an entry here before it is built. Update entries as designs change; this is a living document.

**Status of this register:** reviewed by John Lamont (2026-10-04), covering features planned in [ARCHITECTURE.md](../ARCHITECTURE.md). F1, F2 and F6 revised 2026-10-07 after reviewing three real job-post pastes (desktop and mobile; copies in `backend/tests/fixtures/`), which showed how much of a paste is machine-formatted, that Upwork fields and client prose can disagree, and that the mobile format omits the job link. Entries marked *Open* have unresolved questions that block the build of that feature.

## Project-level determinations

### Rule 6 — Regulated data

**Determination: does not apply (2026-10-04).** Proposal Forge processes the operator's own Upwork job posts, proposals, and work history. It is not built for or operated on behalf of a client whose environment involves PHI or GDPR special-category data. No BAA is required.

Upwork exposes no contact details or regulated data in job posts. Sections that are irrelevant to drafting a proposal (client statistics, recent history) are excluded from prompts under R5's minimum-necessary principle, not because they contain regulated data (see F1). Re-evaluate if the app is ever offered to other users or used for a healthcare client's data.

### Rule 4 — Upwork

**Determination (2026-10-04):** the app never transfers content into Upwork automatically — automated submission is prohibited by Upwork's ToS. All movement of text between Upwork and the app is a manual copy-paste by the operator. No feature may add Upwork scraping, browser automation, or API submission without a new ADR and a fresh ToS review.

### Rule 9 — AI disclosure

**Determination (2026-10-04): at the operator's discretion.** Prospective clients do not interact with or get processed by an AI system: the operator reviews, edits, and manually submits every proposal under their own name. Whether to mention AI assistance in a given proposal is the operator's judgement. The app does not add disclosure text.

---

## Features

### F1 — Job post parsing

*Built 2026-10-07 (PR #8 backend, PR #9 screen). Satisfied in code and tests: `backend/tests/test_job_parser.py` (incl. the R5 boundary), `test_claude_service.py` (all R8 failure paths), `test_jobs_routes.py`, `test_auth.py`.*

| | |
|---|---|
| **Classification** | Standard |
| **Why** | Extracts fields from text the user pasted; user sees and confirms the result before anything else happens. Nothing leaves the app. Design: [F1_JOB_PARSING.md](../F1_JOB_PARSING.md). |
| **Approach** | Two layers. A deterministic parser splits the paste into its Upwork sections and reads every labelled field (engagement, rates, skills, activity, connects, client stats, job link) with no AI. Claude reads only the prose. Desktop and mobile pastes differ in section order and content; sections are optional and may appear in any order. |
| **Data sent to Claude (R5)** | Only what drafting needs: job title, the *Summary* / description text, the skills list, and any Upwork-native screening questions (so Claude does not re-extract them). Not sent, because not needed for the output: *About the client* (parsed by regex to numbers and flags), *Client's recent history* (dropped entirely), activity and bid statistics, connects. |
| **Confidence (R3)** | Not an automated operation: the operator reviews every parse before continuing. Claude returns a confidence per extracted field; low confidence is shown as such, with the source sentence, and never routes anywhere automatically. |
| **Failure path (R8)** | Claude error, empty, or malformed JSON → the deterministic fields are still shown, the prose fields are marked "not extracted" with the error, and the operator can retry or enter them manually. Never store a partial parse as if it were complete. Fields absent from the paste are `null`, never guessed (mobile omits the rate range; new clients have no rating or spend). Where Upwork's structured fields and the client's prose disagree (e.g., *Hourly $9–21* vs "fixed price, 3 milestones"), both values are kept and listed under `conflicts`; the parser never picks one. A paste with no job link parses successfully with `upwork_job_id = null` and a visible prompt to paste the link; the ID is required later by F6. |
| **ToS / legal (R4)** | Manual copy-paste only; the app does not access Upwork (see project-level Rule 4). |

### F2 — Wheelhouse advisory ("Similar past wins?")

| | |
|---|---|
| **Classification** | Standard |
| **Why** | Advisory to the operator only; the continue/abandon decision is always a manual click. |
| **Approach** | Two layers. A deterministic matcher (`backend/app/services/matcher.py`) scores every work-history entry against the job by shared technology (with a short alias table) and shared vocabulary, keeping the top five with the terms they share. Claude is asked for a fit verdict only when at least one comparable exists. Until F8 records outcomes, the evidence is work history only, and the card says so. |
| **Data sent to Claude (R5)** | Job: title, description, skills, and F1's one-liner and deliverables. For each comparable work-history entry only: `name, summary, tech_stack, vertical, project_type, complexity, outcomes, budget_band`. Never: `client_name`, `source_files`, `ai_extraction`, dates, client statistics from the paste, or any entry the matcher did not select. |
| **Confidence (R3)** | Not an automated operation. Match strength is the deterministic count with an honest label — *No work history yet*, *No comparable work history*, *Thin evidence: 1 comparable project*, *N comparable projects* — shown before any verdict. Claude's per-field confidence is display-only. |
| **When and where** | Computed on demand (`POST /api/jobs/{id}/advisory`) when the review opens and work history exists; stored on the job (`job_posts.advisory`) so reopening costs nothing; **Refresh** recomputes after new history is added. No work history → no call, no cost. |
| **Failure path (R8)** | No comparables → the card says so; Claude is not called. Claude error, empty, malformed or refused → "No advisory available — reason" with **Retry**; the comparables list still shows; Continue / Abandon are unaffected. Citations naming entries Claude was not shown are dropped. |
| **Signals shown** | Alongside similar past outcomes, surface the F1 facts an operator weighs before bidding: budget vs. scope, client payment verification and history, F1 `conflicts`, and a *sensitive-data domain* flag when the description indicates the work would handle regulated or special-category data (health, immigration or legal status, finance). The flag is a reminder that the operator's own Rule 6 / Rule 7 engagement checkpoint applies before taking the job; the app makes no determination. |

### F3 — Proposal drafting (cover letter, Q&A answers)

| | |
|---|---|
| **Classification** | **High-stakes** |
| **Why** | Public-facing content sent to prospective clients; affects the operator's reputation and income. |
| **Approval (R1)** | Copying is the approval. Under each Copy icon, a persistent statement reads: *"Copying this content counts as your approval of it."* Clicking Copy is the affirmative action — there is no separate Approve button and nothing is pre-copied. The app never submits to Upwork. |
| **Audit (R2)** | Every copy writes a row to an append-only `proposal_approvals` table: `proposal_id`, `draft_version_id`, `section` (or `all`), `approved_by` (auth user id), `approved_at`, `content_hash`. Draft versions are append-only (`draft_versions[]`); editing after a copy creates a new version, and copying that version writes a new approval row. |
| **Data sent to Claude (R5)** | Parsed job fields, proposal form questions, relevant work history summaries, RAG outcome excerpts. Not: other clients' names or contact details, rates from unrelated contracts. |
| **Failure path (R8)** | Drafting: error, empty, or truncated output → no draft shown as complete; user sees the error and can retry or write manually. Section-level refine failures leave the previous version intact. Audit: the clipboard write happens immediately (browsers require it inside the click), and the approval row is written in the same handler; if that write fails, show a visible "approval not logged — retry" banner and keep retrying. Never fail silently. |

### F4 — Price quote

| | |
|---|---|
| **Classification** | **High-stakes** |
| **Why** | Financial: binds the operator to a price if accepted. |
| **Approval / audit (R1, R2)** | Covered by F3 — copying the quote is its approval and is logged the same way. The quote is shown alongside the historical pricing evidence it was based on. |
| **Failure path (R8)** | If no comparable pricing data exists, say so and leave the quote blank for manual entry rather than inventing a number. |

### F5 — Historical project analysis (dropped files)

*Built 2026-10-08 (PR #11 backend, PR #12 screens). Satisfied in code and tests: `backend/tests/test_file_rules.py` (every accept and refuse rule), `test_work_history_extractor.py` (R5 prompt boundary, R8 failure paths), `test_work_history_routes.py` (extract never writes; save re-screens).*

| | |
|---|---|
| **Classification** | Standard for extraction; output becomes high-stakes when used in F7 |
| **Source** | Files the operator drops into the UI — in practice a project's `README.md`, sometimes a dependency manifest or a short design doc (decided 2026-10-07; replaces the earlier "local project directory"). The app never reads a folder, a repo, or anything the operator did not explicitly drop. |
| **Data sent to Claude (R5)** | Exactly the dropped files that pass `backend/app/services/file_rules.py`, verbatim with their names. Accepted: Markdown, plain text, dependency manifests; at most 5 files, 200 KB each. Refused with a visible reason: `.env*`, key, certificate and credential files, archives, data and config files, binaries. **Content is scanned too**: a file containing a private key, an API token, or a non-placeholder `PASSWORD=`/`API_KEY=` assignment is refused outright, whatever its name. The operator sees the accepted and refused lists before anything is sent, and the screen runs again on save. |
| **Confidence (R3)** | Not an automated operation. Per-field confidence from Claude is display-only; fields under 0.6 carry a marker on the form. |
| **Client naming** | Claude reports `client_name_detected` when the files name the client. It is never written to `may_name_client`, which defaults to false and is set only by the operator. F2/F3 never send `client_name` to Claude; F7 names a client only when `may_name_client` is true. |
| **Failure path (R8)** | `extract` never writes. Claude's reading prefills an editable form; **Save to work history** is the affirmative step. Extraction error, empty, malformed or refused → the form opens empty with the error shown and the files still listed; the operator can retry or type the entry in. Nothing is saved on failure. |
| **ToS / legal (R4)** | No external system is accessed. For client projects, the contract may restrict sharing code or docs with an AI processor; the drop zone shows this reminder, and the decision is the operator's. |

### F6 — Zoho Lead creation (webhook)

| | |
|---|---|
| **Classification** | **High-stakes** (CRM write; financial pipeline record) |
| **Trigger** | The operator clicks **Create Lead** after submitting the proposal on Upwork. Nothing else signals that the copy-paste is done. Keyed on `upwork_job_id`. Field mapping: [ZOHO_INTEGRATION.md](../ZOHO_INTEGRATION.md). |
| **Automated operation (R3)** | Each AI-derived Lead field (`Industry`, `Job_Type`, `Tools`) carries a confidence value. Threshold: *to be set at design of this feature, per field, and recorded here.* The operator sees the payload before it is sent; below-threshold fields are flagged and must be confirmed or edited before **Create Lead** is enabled. |
| **Approval / audit (R1, R2)** | Clicking **Create Lead** is the affirmative action. Log each attempt (payload hash, response status, timestamp, triggering user). |
| **Data sent (R5)** | No client name or PII is known at the proposal stage: `Last_Name` is always `"TBD"`; contact fields are never sent. |
| **Failure path (R8)** | POST failure → proposal stays `submitted` with a visible "Lead not created — retry"; never drop silently. Repeat clicks upsert on `upwork_job_id`, so no duplicate Leads. **Create Lead** is disabled until all required fields (`upwork_job_id`, `Industry`, plus the list in ZOHO_INTEGRATION.md) are filled; a Lead is never sent incomplete. `upwork_job_id` can be missing after a mobile paste (F1); the UI asks for the job link before enabling the button. |
| **ToS / legal (R4)** | Operator's own Zoho account via its documented REST API and OAuth (create/update on Leads only) and its own Deluge functions — permitted. Review on Zoho API version or terms changes. |

### F7 — PDF portfolio export

| | |
|---|---|
| **Classification** | **High-stakes** |
| **Why** | Public-facing: attached to job applications; misstatements affect reputation. |
| **Approval / audit (R1, R2)** | Preview + explicit approve before download; record who exported what (content hash) and when. |
| **Data (R5)** | Exclude client names unless the operator has marked that client as OK to name. |
| **Failure path (R8)** | Generation errors halt the export; no partial PDF. |

### F8 — Outcome feedback into RAG

| | |
|---|---|
| **Classification** | Standard |
| **Why** | Records what happened to a proposal so future drafts (F2, F3) can learn from it ([ADR-003](../ADRs/ADR-003-rag-learning.md)). No AI call when an outcome is recorded; the effect on AI output comes later, through retrieval. |
| **Outcomes** | `won`, `lost`, or `withdrawn` (operator withdrew; recorded and indexed but excluded from win/loss rates). Clients rarely decline explicitly; a proposal usually goes quiet, and a follow-up on Upwork shows the client hired someone else (most common) or closed the job. So `lost` carries a `lost_reason`: `hired_other` or `job_closed`. Until an outcome is recorded, the proposal stays `submitted`. |
| **Who records it (R1)** | Always the operator, manually, in Zoho: the **Won** button, or a `Lead_Status` change for lost/withdrawn (trigger TBD). The app never infers an outcome. |
| **Source** | Per [ADR-005](../ADRs/ADR-005-zoho-integration.md): Zoho pushes to `POST /api/integrations/zoho/outcome` with a per-user secret; one insert-only `SECURITY DEFINER` function writes the outcome. [Contract](../ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho). Allow-list confirmed. *Open:* the Zoho-side trigger for lost/withdrawn (the endpoint already accepts them). |
| **What gets indexed (R5)** | The version the operator actually copied (latest `proposal_approvals` row), not the latest draft — that is what the client saw. Plus parsed job fields, industry, budget band, quote, outcome, and the allow-listed Lead fields sent with the outcome. Zoho sends no client identity, and the endpoint rejects any field outside the allow-list. |
| **Audit (R2)** | Outcomes go into an append-only `proposal_outcomes` history (outcome, recorded_by or source, recorded_at); `proposals.status` and `rag_index` reflect the latest. A corrected outcome (e.g., `lost` → `won`) adds a row, never overwrites. |
| **Failure path (R8)** | Outcome, status, and `rag_index` row are written in one transaction, so it all succeeds or all fails, and Zoho gets the error. The **Won** button shows the operator the result; the lost/withdrawn trigger, once chosen, must do the same. An unmatched job ID is held in a review queue (`202`). The app lists proposals still `submitted` after N days, so a missed push is visible. |

---

## Adding a feature

Copy this template:

```markdown
### FN — Name

| | |
|---|---|
| **Classification** | Standard / High-stakes (ambiguous → high-stakes) |
| **Why** | |
| **Approval / audit (R1, R2)** | High-stakes only |
| **Confidence (R3)** | If it drives automated data operations: signal + threshold |
| **Data sent to Claude (R5)** | Fields included, fields excluded |
| **Failure path (R8)** | No result / malformed / error / below threshold |
| **ToS / legal (R4)** | External systems touched and determination |
| **Disclosure (R9)** | If third parties are processed by or receive AI output |
```
