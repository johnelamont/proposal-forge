# Frontend outline

Screens, routes and flows for the Next.js app, traced back to the use cases in the [README](../README.md) (stages 1–4 and the feature list), the [proposal lifecycle](ARCHITECTURE.md#data-flow-proposal-lifecycle), the mobile requirements in [ADR-002](ADRs/ADR-002-pwa-vs-native.md), and the governance entries in the [feature register](governance/FEATURE_REGISTER.md). The point of this document is coverage: every use case should map to a screen, and every high-stakes screen should show where its approval and audit live.

Single operator, mobile-first. Everything must work one-handed on a phone with a paste, a few taps, and a copy; the desktop gets the same screens with more room.

## Routes

```text
/                      Dashboard — pipeline, attention items, big "Paste a job" button
/login                 Email + password (exists)
/jobs/new              Stage 1: paste → parse → review → Continue / Abandon        F1, F2
/proposals/[id]        Proposal workspace, four tabs:
  ?tab=job               parsed job + advisory (read-only after Stage 1)           F1, F2
  ?tab=draft             Stage 2–3: paste form → draft → refine → Copy             F3, F4
  ?tab=submit            Create Lead preview, sync state, retry                    F6
  ?tab=outcome           outcome history, Zoho link, "still submitted" nudge       F8
/history               Work history list + add-project flow                        F5
/portfolio             PDF export: select → preview → approve → download           F7
/analytics             Win rate by vertical, budget band, tech; abandon stats      —
/settings              Zoho connection, webhook secret, name allow-list, account   F6, F7, F8
/settings/review-queue Outcomes that arrived with an unmatched job ID              F8
```

## Screens

### Dashboard — `/`

The home screen on the phone. Answers "what needs me?" in one glance.

- **Attention** strip at the top, only when non-empty: Lead creation failed (retry), outcomes waiting in the review queue, proposals still `submitted` after N days ("follow up on Upwork?"), draft approvals that failed to log.
- **Paste a job** — the primary button; opens `/jobs/new` with the textarea focused.
- **Pipeline** list grouped by status: `analyzing` → `draft` → `submitted` → `won` / `lost` / `withdrawn` / `abandoned`. Each row: title, budget band, age, Zoho sync state icon. Tap → workspace.
- Quick status check is a README/ADR-002 use case ("quick win/loss status checks" on mobile): the grouped list *is* that feature; no separate screen.

### Stage 1 — `/jobs/new` (F1, F2)

One screen, three states.

1. **Paste.** A single textarea and a **Parse** button. Helper text: "Select all on the Upwork job page, copy, paste here. Works from the mobile app or desktop."
2. **Review.** Per [F1_JOB_PARSING.md](F1_JOB_PARSING.md):
   - *Needs you* banner (only when non-empty): missing job link field (mobile pastes), `conflicts` (Upwork field vs. client prose, both shown, operator picks or leaves), "didn't recognise N lines" (collapsed).
   - *Job* card: title, engagement (type, rate/budget, hours, duration, level), skills, connects, location restriction.
   - *Client* card: verification flags, rating, spend, hire rate, history count. Never sent to Claude; shown because it drives the bid decision.
   - *Reading* card (Claude): one-liner, deliverables, requirements, questions found, budget/timeline statements, red flags, sensitive-domain flag. Low-confidence fields carry a marker and their evidence sentence. If the AI call failed: the card shows the error and **Retry**; everything else stays usable.
   - *Similar past work* card (F2): comparable `work_history` and outcomes with match strength ("3 comparable, 2 won"); or "No advisory available" on failure. Thin evidence is labelled thin.
3. **Decide.** Two buttons, always visible at the bottom: **Continue** (creates the proposal, opens the workspace) and **Abandon** (records the job and the decision for analytics). Nothing is stored as a parsed job until one is tapped.

### Workspace — `/proposals/[id]`

Tabs are the mobile navigation; on desktop they can sit side by side.

**Job tab (F1, F2).** The Stage 1 review, read-only, plus the job link (editable until a Lead exists) and the decision timestamp.

**Draft tab (F3, F4).** Stage 2 and 3 on one tab.

- Before a draft exists: textarea for the Upwork proposal form (the questions Upwork asks at apply time) and **Draft proposal**. Questions already found in Stage 1 (`questions[]`) are pre-listed so the operator sees what Claude will answer.
- With a draft: sections in order — **Cover letter**, one **Q&A** block per question, **Quote**.
  - Each section: the text, an **Edit** control (inline), a **Refine** control ("ask Claude to adjust this section" — new version, other sections untouched), and a **Copy** icon. **Under every Copy icon, persistent, not a tooltip:** *"Copying this content counts as your approval of it."* Nothing is pre-copied; there is no separate Approve button. (F3 R1)
  - **Quote** shows the number alongside the pricing evidence it came from (bid range from the paste, comparable past rates). No comparable data → the field is blank with "no comparable pricing — enter manually". (F4)
  - A **Copy all** control exists for the mobile flow, with the same statement, and logs `section = all`.
  - **Versions**: a list of draft versions (append-only); which version was copied, when, is shown against it. This is the operator-visible face of `proposal_approvals`. (F3 R2)
  - Failure states: draft generation error → no partial draft shown as complete; retry or write manually. Refine error → previous version stays. Approval-row write failure → red banner "approval not logged — retry", retried until it succeeds. (F3 R8)

**Submit tab (F6).** Visible after at least one copy.

- Text at the top: "Submit on Upwork first, then create the Lead. The app never submits to Upwork." (R4)
- **Lead preview**: the full payload the backend will send, as the operator will see it in Zoho — job details, approved proposal text (latest copied version), quote, parsed attributes. AI-derived fields (`Industry`, `Job_Type`, `Tools`) each show their confidence; below threshold they're flagged and must be confirmed or edited. Required-field checklist incl. `upwork_job_id`.
- **Create Lead** button: disabled until the checklist is green. Tapping it is the affirmative action; it marks the proposal `submitted`. Afterwards: sync state (`created` with the Zoho Lead link, or `failed` with the error and **Retry**). Repeat presses upsert — the UI says so.
- Attempt log (payload hash, status, time) under a disclosure.

**Outcome tab (F8).**

- Current status and the `proposal_outcomes` history (append-only; a correction shows as a new row).
- "Outcomes are recorded in Zoho, on the Lead: Won button, or Lead Status for lost/withdrawn" with a link to the Lead. The app offers no outcome-entry controls; it never infers an outcome.
- If `submitted` for more than N days: a nudge to follow up on Upwork.
- What was indexed for learning (the copied version, fields) under a disclosure — transparency for ADR-003.

### Work history — `/history` (F5)

- List of past projects: name, tech stack, vertical, complexity, outcome, whether the client may be named (feeds F7's allow-list).
- **Add project** opens a flow, not a form:
  1. Choose source: *analyse a project folder* or *enter manually*.
  2. For a folder: the operator picks it **on their device**; the browser reads only README/docs, dependency manifests and a file tree, and excludes `.env*`, credentials, data files and anything git-ignored — the exclusion list is shown before upload. Nothing else leaves the device. (F5 R5 — the filter runs client-side, before anything is sent.)
  3. Claude's extracted summary is shown for confirmation; **Save to work history** is the affirmative step. Failure → nothing saved, error shown.
- Open question recorded below: how a hosted web app reads a local folder.

### Portfolio export — `/portfolio` (F7)

1. Select what to include (wins, verticals, tech, date range).
2. **Preview** the rendered PDF in-page. Client names appear only where the work-history row is marked "OK to name".
3. **Approve and download** — one explicit button, labelled as approval. Writes the export record (who, when, content hash).
4. Export log below. Generation error → no download, error shown.

### Analytics — `/analytics`

Win rate by vertical, budget band and tech stack; proposals per month; abandon rate and reasons; average quote vs. bid range. Purely derived from stored data, no AI call, so no register entry. Read-only.

### Settings — `/settings`

- **Zoho**: connect/disconnect (OAuth, Leads create/update only), connection status, last Lead created.
- **Outcome webhook**: the per-user secret (show once, rotate), the endpoint URL to paste into the Deluge function, last outcome received.
- **Review queue** (`/settings/review-queue`): outcomes that arrived with a job ID the app couldn't match — each with the payload Zoho sent and a "match to proposal" picker, or dismiss. (F8 R8: unmatched → held, never dropped.)
- **Naming**: default for "OK to name this client" on new work-history rows (default off).
- **Account**: email, password change, sign out.

## Mobile and PWA (ADR-002)

- Installable: web manifest, icons, `display: standalone`. iOS needs the "Add to Home Screen" hint once.
- Offline: service worker caches the shell and the last-loaded pipeline and drafts, **read-only**. Anything that calls Claude, Supabase or Zoho needs a connection and says so instead of queuing silently.
- Copy on mobile: large tap targets, one **Copy** per section plus **Copy all**; the approval statement is visible without scrolling the icon out of view. Clipboard writes happen inside the tap handler (browser requirement) and the approval row is written in the same handler.
- Paste on mobile: the textarea is the whole screen; Parse is a sticky bottom button.

## Coverage

| Use case (README / ARCHITECTURE / ADR-002) | Screen | Register |
|---|---|---|
| Stage 1: paste job post, parse mobile or desktop format | `/jobs/new` paste + review | F1 |
| "In your wheelhouse? Similar past wins?" | `/jobs/new` similar-past-work card | F2 |
| Continue or Abandon, both tracked | `/jobs/new` decide; abandon stats in `/analytics` | F1 |
| Stage 2: paste proposal form → cover letter + Q&A + quote | Draft tab | F3, F4 |
| Refine inline or ask Claude to adjust a section | Draft tab Edit / Refine | F3 |
| Stage 3: copy-to-clipboard, each copy logged as approval | Draft tab Copy / Copy all + Versions | F3 (R1, R2) |
| Click Create Lead → `submitted`, Lead in Zoho | Submit tab | F6 |
| Stage 4: outcome recorded in Zoho, posted back, indexed | Outcome tab; `/settings/review-queue` | F8 |
| "Next similar proposal: you won 5 of 7 like this" | `/jobs/new` similar-past-work card | F2, F8 |
| Historical projects: analyse a local project directory | `/history` add-project flow | F5 |
| Analytics: win rate by vertical, budget, tech | `/analytics` | — (no AI) |
| PDF portfolio export | `/portfolio` | F7 |
| Mobile-first PWA, install, offline | manifest + service worker; all screens responsive | ADR-002 |
| Quick win/loss status checks on mobile | Dashboard pipeline | — |
| Nothing auto-submitted to Upwork | Submit tab text; no Upwork integration anywhere | Rule 4 |
| Every AI failure surfaced, never silent | Error + Retry states on every AI card | R8 |
| AI disclosure at operator's discretion | no app-added disclosure text | Rule 9 |

## Open questions

1. **F5 — reading a local folder from a hosted web app.** The server (Fly.io) cannot see the operator's disk. Options: the browser's directory picker (`<input webkitdirectory>` works everywhere; the File System Access API gives a nicer flow in Chromium only), with the filtering done in the browser before upload; or a small CLI that runs locally and posts the filtered bundle. Either keeps R5's filter on the device. Needs an ADR before F5 is built.
2. **Offline scope.** The outline makes offline strictly read-only. If drafting-while-offline matters (ADR-002 mentions "service proposal drafts without internet"), that needs a queued-edit design and a conflict story; proposed: defer, read-only first.
3. **Stale `submitted` threshold (N days).** A setting with a default (14?). Decide with F8.
4. **ARCHITECTURE.md "Dual-Mode parsing" section** still says Claude detects the format; F1's design moved format handling to the deterministic parser. Update when the F1 code PR lands.
