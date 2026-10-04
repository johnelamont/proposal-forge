# proposal-forge

Upwork proposal assistant: parse job posts, draft proposals with the Claude API, track outcomes, feed outcomes back as retrieval context. Also a public portfolio piece, so code and docs should read well to a reviewer.

## Where things are

- `README.md` — product overview
- `docs/ARCHITECTURE.md` — system design and data flow
- `docs/ADRs/` — decisions. Read the relevant ADR before changing stack, auth, or the learning approach. New decisions get a new ADR (`ADR-NNN-short-name.md`), not edits to accepted ones.
- `docs/governance/` — AI governance rules (`AI_GOVERNANCE_RULES.md`) and the per-feature register (`FEATURE_REGISTER.md`). See below.
- `frontend/` (Next.js + TypeScript), `backend/` (FastAPI), `database/migrations/` — planned, not yet created.

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
- Repo lives in OneDrive and is used from two machines. Keep machine-specific, heavy directories (virtualenvs, `node_modules`, `.next`) out of the synced tree.
- Line endings are LF (`.gitattributes`, `.editorconfig`); containers run Linux.

## Conventions

- Secrets only in `.env` files (git-ignored); commit a `.env.example` with names, never values.
- Python: Ruff for lint and format. TypeScript: ESLint + Prettier.
- Supabase RLS is the tenant boundary: backend calls on behalf of a user must use that user's JWT, not the service-role key.
- Claude API calls live in backend services, never in the frontend.
