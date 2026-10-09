# proposal-forge

Upwork proposal assistant: parse job posts, draft proposals with the Claude API, track outcomes, feed outcomes back as retrieval context. Also a public portfolio piece, so code and docs should read well to a reviewer.

## Where things are

- `README.md` — product overview
- `docs/ARCHITECTURE.md` — system design and data flow
- `docs/ADRs/` — decisions. Read the relevant ADR before changing stack, auth, or the learning approach. New decisions get a new ADR (`ADR-NNN-short-name.md`), not edits to accepted ones.
- `docs/governance/` — AI governance rules (`AI_GOVERNANCE_RULES.md`) and the per-feature register (`FEATURE_REGISTER.md`). See below.
- `backend/` — FastAPI on Python 3.12, managed with uv. `app/main.py` (app factory), `app/routes/` (one module per resource), `app/services/` (the only home for Claude and Zoho clients), `app/core/config.py` (pydantic-settings from `.env`), `tests/`. Ruff for lint and format, pytest, Dockerfile for Fly.io.
- `frontend/` — Next.js App Router + TypeScript under `src/`, Tailwind, ESLint + Prettier. Supabase auth via `src/lib/supabase/` (email + password; magic link or OAuth can be added later). Deploys to Vercel.
- `supabase/` — Supabase CLI project. Schema lives in `supabase/migrations/` (SQL, versioned); local stack runs in Docker with `supabase start`.
- `.github/workflows/ci.yml` — on every PR and push to `main`: Ruff + pytest; ESLint + Prettier + `tsc` + `next build`.
- Full tree and local setup commands: ARCHITECTURE.md *Repository Structure* and README *Development*.

## Status

Scaffolding merged 2026-10-06. **F1 (job post parsing) complete 2026-10-07**: register entry and design note (#5), backend parser + Claude reader + routes + `job_posts` migration (#8), paste → review → decide screen (#9). **F5 (work history) complete 2026-10-08**: file gate, extractor, routes and `work_history` migration (#11), list / add-a-project / edit screens (#12). **F2 (wheelhouse advisory) complete 2026-10-09**: matcher, advisor, advisory route (#14), Similar past work card (#15). **Next: first deploy** (`docs/DEPLOYMENT.md`), then F3 (proposal drafting), which starts with its register entry, not code.

## AI governance (mandatory)

Everything built here follows Lamont Consulting AI Governance Rules v1.0 (`docs/governance/AI_GOVERNANCE_RULES.md`, adopted in ADR-004). They are requirements, not suggestions:

- Before writing code for an AI-assisted feature, it must have a complete entry in `docs/governance/FEATURE_REGISTER.md`: high-stakes/standard classification (ambiguous → high-stakes), data sent to Claude, failure path, ToS/legal determination. If the entry is missing or has an *Open* blocker, stop and raise it instead of building.
- High-stakes outputs (proposals, price quotes, CRM writes, portfolio export): an explicit affirmative action in the UI (for proposals and quotes, clicking Copy is the approval and says so under the icon), nothing auto-sends, nothing is ever submitted to Upwork automatically (ToS), and an append-only approval record (who, when, content version/hash) in the same migration as the feature.
- Filter data before it reaches a Claude prompt; never send whole records, repos, or `.env`-like files "for context."
- Every Claude call has a handled failure path for error, empty, malformed, and low-confidence results — surface it to the user, never swallow it or proceed with partial output.
- AI-derived values that drive automated writes (e.g., Zoho webhook fields) carry a confidence signal and a documented threshold; below it, route to a review queue.
- A feature is not done until its register entry is satisfied in code and tests.

## Environment

- Windows 11, VS Code, PowerShell + Git Bash. Give Windows-correct commands (no `source venv/bin/activate`).
- Repo lives at `C:\dev\proposal-forge`, outside OneDrive. It is used from two machines and GitHub is the only sync: commit and push before switching machines, pull on arrival. Don't move it back into OneDrive (synced `.venv` / `node_modules` / `.next` cause conflicts).
- Tooling installed: Node 24 LTS, uv, Docker Desktop, Supabase CLI (via Scoop), GitHub CLI (authenticated), Vercel CLI, Scoop.
- Hosted: frontend `https://upworkforge.techledger.ai` (Vercel), backend `https://api.upworkforge.techledger.ai` (Fly.io app `upworkforge-api`), database on Supabase hosted. Setup and day-to-day commands in `docs/DEPLOYMENT.md`. The hosted stack is where real data lives; local stacks are test beds.
- Line endings are LF (`.gitattributes`, `.editorconfig`); containers run Linux.

## Conventions

- Work on a branch and open a PR; never commit to `main` directly. PRs are squash-merged after CI passes and the operator says so.
- Secrets only in `.env` files (git-ignored); commit a `.env.example` with names, never values. Note: pydantic-settings lets a process environment variable override `.env`, and this machine has a user-level `ANTHROPIC_API_KEY` — so the local backend uses *that* key, whatever `.env` says. Keep the two identical, or unset the user-level one, so local and production never run on different keys.
- Python: Ruff for lint and format. TypeScript: ESLint + Prettier.
- Local database: apply new migrations with `supabase migration up`, which keeps data. **Never run `supabase db reset` on a stack that holds data the operator wants** -- it rebuilds from scratch. Use `supabase db dump --local --data-only -f backup.sql` first if a reset is unavoidable.
- Supabase RLS is the tenant boundary: backend calls on behalf of a user must use that user's JWT, not the service-role key.
- Claude API calls live in backend services, never in the frontend.
