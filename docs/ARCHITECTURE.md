# Architecture

## System Overview

```
┌──────────────────────────────────────────────────────┐
│ Frontend (React + Next.js)                           │
│ - Job post input (mobile/desktop dual-parse)         │
│ - Proposal draft UI (inline editing)                 │
│ - Copy-to-clipboard (all sections)                   │
│ - Work history browser + add project modal           │
│ - Analytics dashboard + PDF export                   │
└──────────────────────────┬───────────────────────────┘
                           │ JSON over HTTP
                    ┌──────▼──────┐
                    │ FastAPI     │
                    │ Backend     │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        ↓                  ↓                  ↕
    ┌────────┐      ┌──────────┐      ┌──────────┐
    │Supabase│      │ Claude   │      │Zoho CRM  │
    │Postgres│      │ API      │      │lead out, │
    │+ Auth  │      │          │      │outcome in│
    └────────┘      └──────────┘      └──────────┘
```

## Design Decisions

### Frontend: React + Next.js on Vercel

**Decision:** Use Next.js, deploy to Vercel.

**Rationale:**
- Zero-cost deployment (Vercel Hobby)
- Automatic CI/CD from GitHub
- Image optimization, code splitting built-in
- Typescript for safety
- Good PWA support (service worker)

**Trade-off:** Not a native app. Mitigation: PWA install-to-home-screen bridges 90% of the gap.

### Backend: FastAPI on Fly.io

**Decision:** Python FastAPI instead of Catalyst or Node.js.

**Rationale:**
- Claude API has excellent Python SDK
- Async I/O for multiple concurrent API calls (Claude parse, Supabase, Zoho)
- You're comfortable with Python
- Fly.io free tier includes 3 shared-cpu VMs
- Easy Docker deployment

**Trade-off:** More operational overhead than managed Catalyst. Mitigation: Minimal—Fly.io CLI handles deploys.

### Database: Supabase (Postgres + Auth)

**Decision:** Supabase instead of Firebase or custom auth.

**Rationale:**
- Real PostgreSQL (not NoSQL abstraction)
- Free tier: 50K MAU, 500MB storage
- Auth integrated with Row-Level Security (RLS) → no separate auth service
- pgvector built-in (for RAG embeddings later)
- Multi-tenant isolation is native (partition by user_id)

**Trade-off:** Project pauses after 7 days inactivity (free tier). Mitigation: Keep-alive cron job (Vercel function once/week).

### Parsing: Deterministic Sections, Claude for Prose

**Decision:** Support both Upwork mobile and desktop copy formats with a two-layer parser: a deterministic section parser for every labelled field, and Claude for the description text only. Design: [F1_JOB_PARSING.md](F1_JOB_PARSING.md).

**Rationale:**
- You use both (mobile while browsing, desktop for detail); the layouts differ in section order and in which sections exist (mobile has no job link).
- About 80% of a paste is one-label-per-line structure that regular expressions read exactly and for free; sending it to Claude would cost tokens and invite errors.
- Upwork's fields and the client's prose can disagree; keeping both layers separate lets the app show the conflict instead of letting one source silently win.
- Client statistics and history never need to reach a prompt (R5).

**Implementation (outline):**
```python
def parse_job_post(raw: str) -> ParsedJob:
    sections = split_sections(raw)          # heading lines, any order, all optional
    parsed = parse_fields(sections)         # engagement, skills, activity, client, job link
    reading = read_description(             # Claude; None on failure, never a guess
        title=parsed.title, description=sections.summary,
        skills=parsed.skills, questions=parsed.questions,
    )
    return merge(parsed, reading)           # adds conflicts[], keeps nulls
```

### Workflow: Two-Stage Proposal

**Decision:** Separate job post analysis from proposal drafting.

**Rationale:**
- Abandons without friction (job posted but you pass)
- Reduces Claude API calls (analyze once, reuse context)
- Lets user decide to continue before committing to draft
- Tracks all interests (even abandoned) for analytics

**Trade-off:** Two round-trips instead of one-click. Mitigation: Each stage is 30 seconds.

### Learning: RAG Index Instead of Fine-Tuning

**Decision:** Store proposal outcomes in RAG index; Claude queries at draft time.

**Rationale:**
- No retraining, no fine-tuning cost
- Works with Claude API directly
- Scales: add new proposals continuously
- Versioning: can deprecate old proposals over time
- Transparency: you can see what Claude learned

**Trade-off:** Quality improves slowly (needs 30+ outcomes to matter). Mitigation: Acceptable for MVP; you'll hit 30 proposals in 2-3 months.

### Zoho Integration: Lead Out, Outcome In

**Decision:** Exchange data with the operator's Zoho CRM through the Zoho CRM REST API, keyed on the Upwork Job ID. Transport, auth, and tenancy are in [ADR-005](ADRs/ADR-005-zoho-integration.md). Field mapping and Zoho-side setup are in [ZOHO_INTEGRATION.md](ZOHO_INTEGRATION.md).

1. **Lead out.** When the proposal has been pasted into Upwork and submitted, the user clicks **Create Lead**. The backend upserts a Lead in Zoho.
2. **Outcome in.** The user later records the result on the Lead in Zoho: a **Won** button, or a `Lead_Status` of `Lost Lead`, `Job Closed`, or `Withdrawn`. Zoho posts it to the app, which records it and indexes it for RAG.

**Why it works this way:**
- **Nobody knows the outcome at proposal time.** The app can't know a proposal is won; that comes weeks later, if at all. The most it can do at submission is create a Lead.
- **A button, not an automatic trigger.** Nothing signals when the copy-pasting into Upwork is done, and the app never touches Upwork (its ToS prohibits automated submission). Clicking **Create Lead** is that signal. It also marks the proposal `submitted`.
- **Zoho is where outcomes are decided.** The user follows up on Upwork and updates the Lead in Zoho (usually the client hired someone else or closed the job). Zoho pushes it to the app rather than asking the user to record it twice.
- **Push from Zoho, with Zoho choosing the fields.** Recording a win is a deliberate click in Zoho, and by then the Lead may hold client identity. So Zoho posts only an allow-listed set of fields, and the app rejects anything else. The inbound call has no user JWT, so it authenticates with a per-user secret and can execute exactly one insert-only database function — no service-role key. See ADR-005 for the pull alternative.
- **The Upwork Job ID is the shared key.** Both systems already have it (`Upwork_Job_ID` exists on the Leads module). Upsert on it makes **Create Lead** idempotent: pressing it twice can't create duplicate Leads.
- **Mapping is configuration.** Zoho picklists change. Field mappings are versioned in this repo, the Deluge function source is kept here too, and both are validated against the Upwork layout's picklists.

**Upwork Job ID capture:** extracted during job parsing when the pasted text includes the job URL; otherwise the user pastes the job URL or ID. It's required before **Create Lead** is enabled, and unique per user (one proposal per job).

**Lead out, in brief:**
- Created on the Upwork layout with its required fields: `Lead_Status` = `New Lead`, `Last_Name` = `TBD`, `Lead_Source` = `Upwork`. No client identity or other PII is sent.
- The Lead carries the job details, the approved proposal text, the quote, and the parsed job attributes ([full mapping](ZOHO_INTEGRATION.md#lead-out--on-create-lead)).
- The user previews the Lead before sending. AI-derived fields (including `Industry`) below their confidence threshold are flagged and must be confirmed ([feature register F6](governance/FEATURE_REGISTER.md)).
- **Create Lead** stays disabled until required fields (`Industry` and others, [listed here](ZOHO_INTEGRATION.md#required-before-create-lead)) are filled. An incomplete Lead is never sent.
- `Company` is left blank; it isn't known until a proposal goes to contract, and it's never read back.
- Sync state is tracked on the proposal (`pending` / `created` / `failed`). A failed call leaves the proposal `submitted` with a visible "Lead not created — retry".

**Outcome in, in brief** ([contract](ZOHO_INTEGRATION.md#outcome-in--pushed-by-zoho)):
- Zoho calls `POST /api/integrations/zoho/outcome` with the outcome (`won`, `withdrawn`, or `lost` with a `lost_reason` of `hired_other` or `job_closed`), the Upwork Job ID, and allow-listed Lead fields.
- One `SECURITY DEFINER` function matches the proposal, appends to `proposal_outcomes`, and writes the `rag_index` row from the version that was actually copied, all in one transaction.
- The **Won** button shows the operator the result (recorded, held for review, or the error). An unmatched job ID is held in a review queue, never dropped. The app lists proposals still `submitted` after N days, so missed outcomes are visible.

**Trade-off:** One extra click per proposal (Create Lead), Zoho OAuth for Lead creation, a public endpoint to secure, and two Deluge functions deployed by hand. In return, outcomes are recorded once, where the user already works. The RAG stays current without double entry, and the app never has read access to client data in Zoho.

### Mobile: PWA Instead of Native App

**Decision:** Progressive Web App (install-to-home-screen) instead of native iOS/Android apps.

**Rationale:**
- One codebase (Next.js)
- No App Store submission process
- Faster iteration
- Zero cost

**Trade-off:** Not true native (no deep OS integration). Mitigation: 95% of use cases don't need it; PWA is sufficient for paste/copy/edit.

## Data Flow: Proposal Lifecycle

```
1. User pastes job post
   → /api/parse-job (FastAPI endpoint)
   → Claude parses format
   → Returns {title, budget, questions, complexity}
   → Stored in proposals.job_post_parsed
   → Similar projects queried from work_history
   → Advisory generated

2. User decides to continue
   → Status: draft

3. User pastes proposal form
   → /api/stage-2-draft
   → Claude sees: job context (cached) + similar past projects + historical pricing
   → Generates draft with context
   → Stored in proposals.current_draft (+ version history)

4. User refines in UI
   → /api/refine-section (Claude edits one Q&A, preserves others)
   → New version appended to draft_versions[]

5. User copies sections and pastes them into Upwork
   → Each copy is logged as approval of that version (proposal_approvals)

6. User submits on Upwork, then clicks Create Lead in the app
   → Status: submitted
   → Similar_past_projects snapshot saved
   → Lead payload reviewed (low-confidence fields confirmed)
   → Upsert Lead in Zoho (Last_Name "TBD", keyed on Upwork_Job_ID)
   → Lead sync state: created, or failed → visible retry

7. Weeks later: user follows up on Upwork and records the result in Zoho
   → Won: clicks the Won button on the Lead
   → Lost / withdrawn: sets Lead_Status (Lost Lead, Job Closed, Withdrawn)

8. Zoho posts to POST /api/integrations/zoho/outcome (per-user secret)
   → Allow-listed Lead fields only; anything else rejected
   → Matched on upwork_job_id (unmatched → review queue)
   → Outcome appended to proposal_outcomes; status: won | lost | withdrawn
   → rag_index updated from the copied (approved) version
   → Won button shows the result to the user

9. Next proposal on same vertical:
   → Query rag_index for similar outcomes
   → Claude advisor: "You've won 5 of 7 like this"
```

## Tables & RLS

**proposals**
- Stores job posts, proposal drafts, current status, `upwork_job_id` (unique per user), Zoho lead sync state
- RLS: Users see only own proposals

**work_history**
- Your historical projects (manually added via modal)
- Extracted tech, complexity, outcome
- RLS: Users see only own work history

**proposal_approvals** / **proposal_outcomes**
- Append-only audit: each copy (approval) and each outcome received
- RLS: Users see only own rows; no updates or deletes

**rag_index**
- Denormalized view of proposal outcomes (for RAG queries)
- Stores proposal_id, outcome, vertical, budget, draft excerpt
- RLS: Users query only own outcomes

## Scaling Path

**MVP (now):** Single Fly.io VM, single Supabase instance, in-memory RAG queries.

**100 proposals:** No changes needed.

**1K proposals:** Add Redis for rag_index caching, move to Supabase Pro ($25/mo).

**Beyond:** Migrate to vector DB (Pinecone, Weaviate) if RAG query latency matters.

## Known Limitations

1. **Supabase free tier pauses after 7 days inactivity** → mitigate with weekly keep-alive (Vercel function)
2. **RAG quality requires 30+ outcomes** → acceptable for learning curve
3. **No real-time collab** → single user, not team
4. **Claude API costs ~$1-2 per proposal** → manageable for MVP, watch if high volume
5. **Mobile copy-paste context loss** → Upwork mobile strips some fields. Dual-parse mitigates but not 100%.

## Technology Choices: Alternatives Considered

| Decision | Choice | Rejected | Why |
|----------|--------|----------|-----|
| Frontend | React + Next.js | Vue, Svelte | React ecosystem largest; Next.js best for SSR + Vercel |
| Backend | FastAPI | Node.js, Catalyst | Python + async best for Claude SDK; Catalyst tied to Zoho |
| Database | Supabase | Firebase, Neon | Supabase: Auth + RLS integrated; Firebase: NoSQL, less control |
| Auth | Supabase Auth | Clerk, Auth0 | Tied to Postgres RLS; no vendor cost at free tier |
| Deployment | Vercel + Fly.io | Railway, Render | Both free tiers; Vercel + Fly is proven combo; lower complexity |
| Learning | RAG index | Fine-tune GPT | No cost to add proposals; no retraining; versioning easier |
| Mobile | PWA | React Native | One codebase; no App Store; sufficient for paste/copy/edit |

## Repository Structure

Three deployable units (`frontend/`, `backend/`, `supabase/`), each self-contained with its own tooling, plus docs and CI. Entries marked *(planned)* do not exist yet.

```text
proposal-forge/
├── docs/
│   ├── ARCHITECTURE.md              (this file)
│   ├── ZOHO_INTEGRATION.md          field mapping, Deluge contract
│   ├── F1_JOB_PARSING.md            F1 design: deterministic parser + Claude on prose only
│   ├── F5_WORK_HISTORY.md           F5 design: file gate, extraction, confirm-then-save
│   ├── F2_WHEELHOUSE.md             F2 design: deterministic comparables + Claude fit verdict
│   ├── F3_DRAFTING.md               F3/F4 design: hard rules, versions, copy-as-approval, quote evidence
│   ├── DEPLOYMENT.md                Vercel + Fly.io + Supabase setup, DNS, data move
│   ├── RAG.md                       (planned) retrieval design and index schema
│   ├── governance/
│   │   ├── AI_GOVERNANCE_RULES.md
│   │   └── FEATURE_REGISTER.md      per-feature gate; must be satisfied before a build
│   └── ADRs/
│       ├── ADR-001-fastapi-supabase.md
│       ├── ADR-002-pwa-vs-native.md
│       ├── ADR-003-rag-learning.md
│       ├── ADR-004-ai-governance.md
│       └── ADR-005-zoho-integration.md
├── frontend/                        Next.js App Router + TypeScript, deployed to Vercel
│   ├── src/
│   │   ├── app/                     routes: layout.tsx, page.tsx, globals.css
│   │   ├── components/              auth status, sign-in form, sign-out button
│   │   └── lib/
│   │       └── supabase/            browser + server auth clients (email + password)
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   ├── tsconfig.json
│   ├── eslint.config.mjs            Next presets + eslint-config-prettier
│   ├── .prettierrc
│   ├── AGENTS.md                    generated by `next dev`; not hand-edited
│   └── .env.example                 NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY, NEXT_PUBLIC_API_URL
├── backend/                         FastAPI, Python 3.12, managed with uv, deployed to Fly.io
│   ├── app/
│   │   ├── main.py                  app factory, CORS, router registration
│   │   ├── core/
│   │   │   └── config.py            pydantic-settings, loaded from .env
│   │   ├── routes/                  one module per resource; /health first
│   │   └── services/                Claude client, Zoho client (added with F1 and F6)
│   ├── tests/
│   ├── pyproject.toml               deps + Ruff + pytest config
│   ├── uv.lock
│   ├── .python-version
│   ├── Dockerfile
│   ├── fly.toml                     Fly.io app config (secrets via `fly secrets`)
│   └── .env.example                 SUPABASE_URL, SUPABASE_ANON_KEY, ANTHROPIC_API_KEY, ...
├── supabase/                        Supabase CLI project; local stack via `supabase start`
│   ├── config.toml
│   └── migrations/                  versioned SQL; empty until F1 adds the first tables
├── scripts/
│   └── migrate_local_to_cloud.py    one-time local → hosted data move
├── .github/
│   └── workflows/
│       ├── ci.yml                   Ruff + pytest; ESLint + Prettier + tsc + next build
│       └── deploy-backend.yml       Fly.io deploy on push to main (backend/ changes)
├── .editorconfig
├── .gitattributes                   LF line endings
├── .gitignore
├── .vscode/
├── CLAUDE.md                        working agreement for AI-assisted development in this repo
├── README.md
└── LICENSE
```

Notes:

- There is no root `Dockerfile` or `docker-compose.yml`. The only container image is the backend's; the local database is the Supabase CLI's own Docker stack.
- Secrets live in git-ignored `.env` files beside each `.env.example`. Claude API calls are made only from `backend/app/services/`, never from the frontend.
- Schema changes are Supabase migrations and are the tenant boundary (RLS). A high-stakes feature's approval/audit table ships in the same migration as the feature ([FEATURE_REGISTER.md](governance/FEATURE_REGISTER.md)).
