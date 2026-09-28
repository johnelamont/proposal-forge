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
        ↓                  ↓                  ↓
    ┌────────┐      ┌──────────┐      ┌──────────┐
    │Supabase│      │ Claude   │      │Zoho      │
    │Postgres│      │ API      │      │Webhook   │
    │+ Auth  │      │          │      │(outbound)│
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
- Async I/O for multiple concurrent API calls (Claude parse, Supabase, Zoho webhook)
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

### Parsing: Dual-Mode (Mobile vs Desktop)

**Decision:** Support both Upwork mobile and desktop copy formats.

**Rationale:**
- You use both (mobile while browsing, desktop for detail)
- Different formats → different field order
- Claude can handle both with format hint

**Implementation:**
```python
def parse_upwork_job(raw: str) -> dict:
    # Claude detects format automatically
    # Returns standardized {title, budget, scope, ...}
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

### Webhook Schema: Versioned, Standardized

**Decision:** When proposal marked "won," POST to Zoho webhook with standardized JSON.

**Rationale:**
- Shows data thinking (not ad-hoc integration)
- Zoho can schema-validate incoming proposals
- Versioning allows future breaking changes
- Self-documenting (schema is the contract)
- Decouples app from Zoho CRM internals

**Schema:**
```json
{
  "proposal_id": "uuid",
  "client_name": "string",
  "job_title": "string",
  "budget_min": 5000,
  "budget_max": 15000,
  "vertical": "string",
  "tech_stack": ["Zoho CRM", "Python"],
  "estimated_hours": 120,
  "status": "won",
  "proposal_url": "upwork.com/...",
  "created_at": "2026-09-27T14:30:00Z"
}
```

### Mobile: PWA Instead of Native App

**Decision:** Progressive Web App (install-to-home-screen) instead of native iOS/Android apps.

**Rationale:**
- One codebase (Next.js)
- Works offline (service worker cache)
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

5. User copies all and pastes back to Upwork

6. User marks submitted
   → Status: submitted
   → Similar_past_projects snapshot saved

7. Later: user marks outcome (won/lost/no_response)
   → Status: won
   → Entry added to rag_index
   → If won and zoho_token set: POST to Zoho webhook

8. Next proposal on same vertical:
   → Query rag_index for similar outcomes
   → Claude advisor: "You've won 5 of 7 like this"
```

## Tables & RLS

**proposals**
- Stores job posts, proposal drafts, outcomes
- RLS: Users see only own proposals

**work_history**
- Your historical projects (manually added via modal)
- Extracted tech, complexity, outcome
- RLS: Users see only own work history

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
| Mobile | PWA | React Native | One codebase; no App Store; offline-first; sufficient for use case |

## Repository Structure

```
proposal-forge/
├── docs/
│   ├── ARCHITECTURE.md (this file)
│   ├── WEBHOOK_SCHEMA.md
│   ├── DEPLOYMENT.md
│   ├── RAG.md
│   └── ADRs/ (Architecture Decision Records)
│       ├── ADR-001-fastapi-supabase.md
│       ├── ADR-002-pwa-vs-native.md
│       └── ADR-003-rag-learning.md
├── frontend/
│   ├── pages/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   └── next.config.js
├── backend/
│   ├── main.py
│   ├── routes/
│   ├── services/
│   ├── tests/
│   ├── requirements.txt
│   └── Dockerfile
├── database/
│   └── migrations/
│       ├── 001_create_proposals.sql
│       ├── 002_create_work_history.sql
│       └── 003_create_rag_index.sql
├── docker-compose.yml
├── Dockerfile
├── README.md
└── LICENSE

```
