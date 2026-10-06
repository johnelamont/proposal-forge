# Proposal Forge — frontend

Next.js (App Router, TypeScript, Tailwind) client for Proposal Forge. Authenticates with Supabase (email + password) and calls the FastAPI backend. Claude API calls never happen here; they live in `backend/app/services/`.

Setup and commands are in the repo [README](../README.md#development). Layout:

```text
src/
├── app/            routes (layout.tsx, page.tsx, globals.css)
├── components/     UI components
└── lib/supabase/   browser and server Supabase clients
```

`AGENTS.md` is generated and maintained by `next dev`; leave it in place.
