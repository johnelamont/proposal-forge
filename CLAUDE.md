# proposal-forge

Upwork proposal assistant: parse job posts, draft proposals with the Claude API, track outcomes, feed outcomes back as retrieval context. Also a public portfolio piece, so code and docs should read well to a reviewer.

## Where things are

- `README.md` — product overview
- `docs/ARCHITECTURE.md` — system design and data flow
- `docs/ADRs/` — decisions. Read the relevant ADR before changing stack, auth, or the learning approach. New decisions get a new ADR (`ADR-NNN-short-name.md`), not edits to accepted ones.
- `frontend/` (Next.js + TypeScript), `backend/` (FastAPI), `database/migrations/` — planned, not yet created.

## Environment

- Windows 11, VS Code, PowerShell + Git Bash. Give Windows-correct commands (no `source venv/bin/activate`).
- Repo lives in OneDrive and is used from two machines. Keep machine-specific, heavy directories (virtualenvs, `node_modules`, `.next`) out of the synced tree.
- Line endings are LF (`.gitattributes`, `.editorconfig`); containers run Linux.

## Conventions

- Secrets only in `.env` files (git-ignored); commit a `.env.example` with names, never values.
- Python: Ruff for lint and format. TypeScript: ESLint + Prettier.
- Supabase RLS is the tenant boundary: backend calls on behalf of a user must use that user's JWT, not the service-role key.
- Claude API calls live in backend services, never in the frontend.
