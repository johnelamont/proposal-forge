# ADR-001: Backend & Database Stack (FastAPI + Supabase)

**Status:** Accepted  
**Date:** 2026-09-27  
**Deciders:** John Lamont

## Context

Building a proposal assistant that:
- Parses Upwork job posts with Claude API
- Stores and refines proposals
- Tracks outcomes for RAG learning
- Syncs wins to Zoho CRM via webhook
- Must cost $0 for MVP (no monthly bills)

Need to choose backend platform + database.

## Options Considered

### Option A: FastAPI + Supabase (Chosen)

| Dimension | Assessment |
|-----------|-----------|
| **Complexity** | Medium (async Python, Postgres) |
| **Cost** | $0 (Fly.io free, Supabase free) |
| **Team familiarity** | High (Python experience, 30 years IT) |
| **Claude API fit** | Excellent (Python SDK best-in-class) |
| **Scalability** | Good (async I/O, scales to 1K+ users on free tier) |
| **Operational burden** | Low (Fly.io managed, Supabase managed) |

**Pros:**
- Zero deployment cost (Fly.io + Supabase free tier)
- Claude Python SDK is mature and well-documented
- Async FastAPI handles concurrent requests well
- PostgreSQL with Row-Level Security = native multi-tenant isolation
- Supabase Auth integrates with Postgres RLS (no separate auth service)
- Postgvector available for future RAG embeddings
- Dockerfile ready for self-hosting later

**Cons:**
- More operational overhead than serverless (but still minimal)
- Free tier has limitations (Supabase pauses after 7 days inactivity)
- Less "magical" than Firebase (more configuration needed)

### Option B: Node.js + Firebase

| Dimension | Assessment |
|-----------|-----------|
| **Complexity** | Low-Medium |
| **Cost** | $0 initially, then usage-based |
| **Claude fit** | Good (Node.js SDK available) |
| **Scalability** | Limited (Firestore document/operation pricing) |

**Pros:**
- Faster initial setup (Firebase console handles everything)
- No server management (fully serverless)
- Generous free tier for storage

**Cons:**
- NoSQL (Firestore) requires denormalization; harder for complex queries
- Auth handled separately (Firebase Auth good but adds complexity)
- No native RLS equivalent; auth logic lives in code
- Document pricing ($0.06 per 100K reads) scales poorly for proposal tracking
- Webhook sync to Zoho requires custom Cloud Functions (cost adds up)
- Locks you into Firebase ecosystem

### Option C: Zoho Catalyst

| Dimension | Assessment |
|-----------|-----------|
| **Complexity** | Medium (Deluge, Creator) |
| **Cost** | Part of Zoho One ecosystem (you have access) |
| **Claude fit** | Possible (API calls work, but less ergonomic) |
| **Scalability** | Fine for SMB scale |

**Pros:**
- Already familiar with Zoho
- Direct integration with Zoho CRM (no webhook needed)
- Included in ecosystem you use for consulting

**Cons:**
- Tightly coupled to Zoho (harder to showcase as independent architecture)
- Deluge is not Python; Claude works better in Python
- Catalyst has quota limits (can hit them with high proposal volume)
- Not a good portfolio piece (looks like "Zoho guy built a Zoho app")
- This app is meant to showcase full-stack thinking, not Zoho expertise

### Option D: Render + Prisma + Postgres

| Dimension | Assessment |
|-----------|-----------|
| **Complexity** | Medium |
| **Cost** | Free tier, but more limited than Fly.io |
| **Claude fit** | OK (Node.js or Python) |
| **Scalability** | Equivalent to Fly.io |

**Pros:**
- Render free tier is generous
- Prisma ORM is excellent (type-safe)

**Cons:**
- Slight learning curve (Prisma schema)
- No meaningful advantage over FastAPI + Supabase
- Same cost tier, more abstraction layers

## Trade-off Analysis

**Cost:** A and D tie ($0). B starts free but scales poorly.

**Claude integration:** A wins (Python SDK maturity).

**Operations:** B (fully serverless) > A (minimal ops) > C (Zoho overhead) > D (similar to A but more layers).

**Portfolio value:** A wins (shows multi-service integration, standardized webhook, async design). C loses (too Zoho-specific).

**Data model:** A wins (SQL for complex queries). B requires rethinking schema (document-oriented).

**Zoho sync:** A best (clean webhook contract). B (Cloud Functions cost). C (native but not showcaseable).

## Decision

**Use FastAPI + Supabase.**

- Zero cost for MVP
- Claude Python SDK is best-in-class
- PostgreSQL + RLS for clean multi-tenant isolation
- Supabase Auth eliminates separate auth service
- Async I/O for concurrent Claude API calls
- Webhook to Zoho demonstrates data thinking
- Fly.io + Supabase proven, low operational burden
- Strong portfolio piece (architecture, standardization, AWS independence)

## Consequences

**What becomes easier:**
- Iterating on Claude API prompts (Python is flexible)
- Multi-tenant data isolation (RLS native)
- Future RAG with pgvector
- Complex queries (SQL beats document model)
- Zoho integration (clean webhook contract)

**What becomes harder:**
- Deploying without Docker (Fly.io uses containers)
- Running without internet (Supabase cloud-only at free tier)
- Real-time collaboration (no Firebase Realtime Database equivalent, would need WebSocket layer)

**What we'll need to revisit:**
- Supabase pause-after-7-days — need keep-alive cron (easy: Vercel function)
- Fly.io free tier limits — if 10K+ concurrent users, need paid VMs ($7/mo)
- RAG quality at low proposal volume — acceptable; improves over time

## Related Decisions

- ADR-002: PWA vs native mobile (affects backend—need JSON API, not server-side rendering)
- ADR-003: RAG learning index (affects database schema; Postgres handles well)
