# F3 — Proposal drafting (with F4 price quote): design

Governance entries: [F3](governance/FEATURE_REGISTER.md#f3--proposal-drafting-cover-letter-qa-answers) and [F4](governance/FEATURE_REGISTER.md#f4--price-quote), both **high-stakes**. Screen outline: [FRONTEND.md → Workspace, Draft tab](FRONTEND.md#workspace--proposalsid). This document is what the F3 code PRs are reviewed against.

## What the operator does

1. Open a job they chose to **Continue** → **Draft proposal**. Claude writes the cover letter and one answer per screening question; F4 proposes a quote from evidence. All of it appears as **version 1**.
2. Per section: **Edit** (type over it), **Refine** (an instruction; Claude rewrites that section only), **Copy**. Under every Copy icon, permanently: *"Copying this content counts as your approval of it."* No separate Approve button; nothing pre-copied; nothing ever sent to Upwork by the app.
3. **Versions** lists every version with its source (`ai`, `refine`, `edit`, `manual`) and marks which were copied, when. **Copy all** exists for the phone.
4. If Upwork's apply form shows a question the job post didn't, paste the form: its questions are merged and the next draft answers them. Pasting is optional.

## Profile (new, F3 prerequisite)

One row per operator (`profiles`): `signature_name`, `positioning` (who they are, what they do), `greeting` (default `Hi,`), `sign_off` (default `Kind Regards,`), `tone_notes`, `never_claim[]` (phrases the draft must never assert, e.g. "Zoho Partner"), `default_hourly_rate`, `fixed_price_range`. Drafting refuses (409) until a name and positioning exist.

## Hard rules, and who enforces them

| Rule | Prompt | Code |
|---|---|---|
| Starts with the greeting, ends with sign-off + name | model told not to write either | `frame()` strips anything the model wrote and applies the operator's |
| Never claim partnership, membership, certification, affiliation | explicit instruction | `never_claim` phrases found in the text → **warning on the version**, shown; never silently edited |
| Never invent experience; cite only the projects given, never by client name | explicit instruction | R5: only allow-listed fields of F2's cited projects are sent |
| One answer per question, in order | explicit instruction | answers aligned to the operator's question list by position; missing → blank + warning |
| No length cap; plain, complete, no hype | explicit instruction | — |

## What crosses the R5 boundary

Sent: profile positioning and tone notes; job title, skills, description; F1's one-liner, deliverables, requirements; F2's angle and gaps; for each project F2 said to cite: `name, summary, tech_stack, vertical, project_type, complexity, outcomes`; the question list. **Never**: `client_name`, `source_files`, client statistics, budget figures of past projects, other jobs, the operator's rates (the quote is computed, not asked).

Refine sends: positioning, the instruction, and the one section (frame stripped).

## F4 — the quote

`backend/app/services/pricing.py`, deterministic. Evidence, each item listed with the quote:

- the job's hourly range or fixed budget, and the bid statistics
- the operator's default hourly rate / fixed-price range
- the `budget_band` of each cited past project

Hourly: the default rate, flagged if above the client's range (never silently clamped). Fixed: midpoint of the cited projects' upper bands. No evidence → `amount = null`, rationale "enter the quote yourself". The operator can overwrite the amount (an `edit` version with "Entered by you").

## Versions and approvals (R1, R2)

`draft_versions` and `proposal_approvals` are **append-only**: no update/delete RLS policies, plus a trigger that refuses UPDATE/DELETE even for superusers. The trigger's one escape is a deliberate purge (`set app.allow_purge = 'on'` in an admin session, e.g. deleting the operator's account); the API never sets it.

The copy flow keeps the hash honest: the frontend asks `GET …/copy-text?section=&version_id=&index=` for the exact text and its SHA-256, writes that text to the clipboard inside the click, and posts the approval with the hash in the same handler. The server recomputes the hash from the stored version and refuses a mismatch (409). `all` is a fixed concatenation (cover letter, question/answer pairs, quote line).

## Failure path (R8)

| Failure | Behaviour |
|---|---|
| Full draft: Claude error / empty / malformed / refusal | Version written with empty cover letter, blank answers, and the failure in `ai_meta`; F4's quote still computed. The screen shows the error with Retry or write-by-hand. Nothing is shown as complete. |
| Refine fails | 502 with the reason; **no version written**; previous version stays current. |
| Fewer answers than questions | Unmatched questions blank + warning on the version. |
| Never-claim phrase present | Warning on the version, shown beside the section. |
| Approval insert fails | Frontend shows "approval not logged — retry" and keeps retrying (the clipboard write already happened). |
| No profile | 409 before any Claude call. |

## API

| Route | Does |
|---|---|
| `GET/PUT /api/profile` | the operator's profile |
| `POST /api/proposals` | create for a job (one per job; returns existing) and write version 1 |
| `GET /api/proposals/{id}`, `GET /api/proposals/by-job/{job_id}` | proposal + versions + approvals |
| `POST …/draft` | fresh full draft → new version |
| `POST …/questions` | merge questions from a pasted apply form |
| `POST …/refine` | one section rewritten → new version, or 502 and nothing |
| `POST …/edit` | operator's own change → new version |
| `GET …/copy-text` | exact text + hash for a section of a version |
| `POST …/approvals` | record a copy; hash must match |

## Tests the code PR includes

Pricing (within range, above range, no rate, fixed from bands, no evidence); drafter (frame add/strip/idempotent, never-claim warnings, prompt boundary with no client names, answer alignment, failure paths, refine); form-paste extraction; routes (profile gate, version 1 with quote, form questions answered, failure stored as a version, refine/edit append and refine-failure keeps previous, copy-text/approval hash accept and reject, abandoned job refused, auth).
