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
Copy-to-clipboard buttons (mobile-friendly)
→ Paste back into Upwork
→ Mark status: submitted
```

### Stage 4: Track Outcome

```
Later: Mark as won/lost/no response
→ Proposal + outcome indexed for learning
→ Next similar proposal: Claude says "You won 5 of 7 like this"
```

## Features

- **Dual-parse job posts** — Handles mobile and desktop Upwork copy-paste formats
- **Historical projects** — Add your past projects (point to GitHub repo or local directory) → Claude analyzes code/docs → extracts tech stack, complexity, type
- **Real-time advisor** — Compare incoming job to your past projects; show similar outcomes
- **Analytics** — Win rate by vertical, budget range, tech stack frequency
- **RAG learning loop** — Each proposal outcome improves future drafts
- **Zoho webhook** — When proposal is won, sync to Zoho CRM with standardized schema
- **PDF portfolio export** — Generate report of wins, verticals, tech stack for attaching to job applications
- **Mobile-first PWA** — Install on home screen (iOS/Android), offline support
- **Copy-to-clipboard** — Frustration-free paste back to Upwork

## Getting Started

See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for free-tier setup (Vercel, Fly.io, Supabase).

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design, [WEBHOOK_SCHEMA.md](docs/WEBHOOK_SCHEMA.md) for Zoho integration.

## Development

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn main:app --reload

# Database
# Supabase console: https://app.supabase.com
```

## License

MIT
