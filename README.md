# proposal-forge

Upwork proposal assistant. Parse job posts, draft responses with Claude AI, track outcomes, learn from patterns.

## What It Does

1. **Parse job posts** — Paste Upwork job posting → Claude extracts fields (budget, scope, questions). Analyzes whether it's in your wheelhouse based on past work.

2. **Draft proposals** — Paste proposal form → Claude generates cover letter + answers + price quote, informed by your historical projects and past proposal outcomes.

3. **Track wins/losses** — Record outcome → system indexes the proposal and outcome. Over time, learns what works in each vertical and budget range.

4. **Showcase** — GitHub repo demonstrates full-stack architecture. PDF export for attaching to job applications.

## Stack

- **Frontend:** React + Next.js (Vercel Hobby, $0)
- **Backend:** FastAPI + Python (Fly.io free tier, $0)
- **Database:** PostgreSQL + Supabase Auth (free tier, $0)
- **AI:** Claude API (pay-per-use, ~$1-2 per proposal)

**Total out-of-pocket:** $0 (except Claude API credits you likely have)

## How It Works

### Stage 1: Job Analysis

```
Find job on Upwork → Select All → Paste into app
→ Claude parses (mobile or desktop format)
→ Shows: "In your wheelhouse? Similar past wins?"
→ Continue or Abandon (both tracked)
```

### Stage 2: Draft Proposal

```
Paste Upwork proposal form
→ Claude sees job context + your past similar projects
→ Generates: cover letter + Q&A answers + price quote
→ You refine inline or ask Claude to adjust specific sections
```

### Stage 3: Copy & Submit

```
Copy-to-clipboard buttons (mobile-friendly; each copy is logged as approval)
→ Paste into Upwork and submit
→ Click Create Lead → status: submitted, Lead created in Zoho CRM
```

### Stage 4: Track Outcome

```
Later: follow up on Upwork, record the result on the Lead in Zoho
→ Zoho posts the outcome to the app (Won button, or Lead status for lost/withdrawn), matched on Upwork Job ID
→ Proposal + outcome indexed for learning
→ Next similar proposal: Claude says "You won 5 of 7 like this"
```

## Features

- **Dual-parse job posts** — Handles mobile and desktop Upwork copy-paste formats
- **Historical projects** — Add your past projects (drop in the README or docs) → Claude extracts tech stack, complexity, type
- **Real-time advisor** — Compare incoming job to your past projects; show similar outcomes
- **Analytics** — Win rate by vertical, budget range, tech stack frequency
- **RAG learning loop** — Each proposal outcome improves future drafts
- **Zoho integration** — Create a Lead from a submitted proposal; Zoho posts won/lost/withdrawn back to the app for the learning loop. Keyed on Upwork Job ID
- **PDF portfolio export** — Generate report of wins, verticals, tech stack for attaching to job applications
- **Mobile-first PWA** — Install on home screen (iOS/Android)
- **Copy-to-clipboard** — Frustration-free paste back to Upwork

## Getting Started

Local setup is under [Development](#development). Hosted deployment (Vercel, Fly.io, Supabase) is not set up yet; `docs/DEPLOYMENT.md` will be added with the first deploy.

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design, [ZOHO_INTEGRATION.md](docs/ZOHO_INTEGRATION.md) for Zoho integration.

## Responsible AI

Built to [Lamont Consulting AI Governance Rules](docs/governance/AI_GOVERNANCE_RULES.md) ([ADR-004](docs/ADRs/ADR-004-ai-governance.md)). Every AI feature is classified before it is built — see the [feature register](docs/governance/FEATURE_REGISTER.md). In practice: copying a proposal or quote counts as approving it, and every copy and portfolio export is logged to an append-only audit record; nothing is ever auto-submitted to Upwork; only the minimum data needed reaches Claude; and every AI failure is surfaced, never silent.

## Development

Developed on Windows 11; commands below are PowerShell and work unchanged in Git Bash. Prerequisites: [Node 24 LTS](https://nodejs.org), [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/), and the [Supabase CLI](https://supabase.com/docs/guides/local-development/cli/getting-started) (`scoop install supabase`; not installable with `npm install -g`).

Three parts run side by side: the local Supabase stack (database + auth), the FastAPI backend, and the Next.js frontend.

### 1. Database and auth (local Supabase stack)

```powershell
supabase start     # first run pulls the Docker images (a few minutes); prints API URL, anon key, JWT secret
supabase status    # prints them again later
supabase stop      # when done
```

Studio (database UI): <http://127.0.0.1:54323>. Schema changes are SQL files in `supabase/migrations/`. After pulling new ones, apply them with `supabase migration up` -- this keeps your data. `supabase db reset` rebuilds the database from scratch and **deletes local data**; only use it on an empty stack (take `supabase db dump --local --data-only -f backup.sql` first if not).

### 2. Backend (FastAPI)

```powershell
cd backend
Copy-Item .env.example .env          # then set SUPABASE_JWT_SECRET from `supabase status`
uv sync                              # creates .venv and installs locked dependencies
uv run uvicorn app.main:app --reload # http://127.0.0.1:8000/health, docs at /docs
```

Checks: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`.

### 3. Frontend (Next.js)

```powershell
cd frontend
Copy-Item .env.example .env.local    # then set NEXT_PUBLIC_SUPABASE_ANON_KEY from `supabase status`
npm install
npm run dev                          # http://localhost:3000
```

Checks: `npm run lint`, `npm run format:check`, `npm run typecheck`, `npm run build`.

### CI

GitHub Actions ([ci.yml](.github/workflows/ci.yml)) runs the same backend and frontend checks on every pull request and on pushes to `main`.

## License

MIT
