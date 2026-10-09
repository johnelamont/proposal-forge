# F2 — Wheelhouse advisory: design

Governance entry: [FEATURE_REGISTER.md → F2](governance/FEATURE_REGISTER.md#f2--wheelhouse-advisory-similar-past-wins). Screen slot: the *Similar past work* card on the Stage 1 review ([FRONTEND.md](FRONTEND.md#stage-1--jobsnew-f1-f2)). Learning approach: [ADR-003](ADRs/ADR-003-rag-learning.md).

## What the operator sees

On the job review, a card titled **Similar past work**:

1. An evidence line first: *3 comparable projects* / *Thin evidence: 1 comparable project* / *No comparable work history* / *No work history yet — add projects to compare*.
2. The comparable projects, each with the technology and terms it shares with the job.
3. Claude's verdict, only when there are comparables: **fit** (strong / partial / weak / none), reasons, gaps, which projects are worth citing in a proposal, and a one-sentence angle. Low-confidence fields are marked.
4. A fixed line: *Win/loss evidence appears once proposal outcomes are recorded (F8).*
5. **Refresh** (recompute after adding history) and, on failure, **Retry**.

Continue / Abandon never depend on it.

## Layer one: deterministic matching

`backend/app/services/matcher.py`. For each work-history entry:

- **Shared technology** — the job's `skills` against the entry's `tech_stack`, both expanded through a short alias table (`Zoho CRM → zoho, crm`; `Next.js → react`; `FastAPI → python`; `Supabase → postgres`; `Zapier → automation`; …). The table is deliberately small and grows as real jobs show gaps.
- **Shared vocabulary** — stop-word-filtered tokens of the job's title, description, F1 one-liner and the paste's client industry, against the entry's name, summary, vertical, project type and outcomes.
- An entry is **comparable** if it shares at least one technology or at least three vocabulary terms. `score = 2 × tech + 0.5 × min(terms, 10) + 1 if the entry's vertical appears in the job`. Top five kept, each with its shared terms so the card can show *why*.
- **Match strength** is the comparable count, labelled as above. This is the R3 signal and it exists before Claude is involved.

## Layer two: Claude

Shared core `structured_call` (as F1 and F5). Called **only** when comparables exist.

Input: the job's title, description, skills, F1 one-liner and deliverables; for each comparable entry the allow-listed fields (`name, summary, tech_stack, vertical, project_type, complexity, outcomes, budget_band`) and the matched terms. Nothing else — see the register's R5 row.

Output `AdvisoryReading`: `fit`, `reasons[]`, `gaps[]`, `cite[]` (entry id, name, why), `angle`, per-field confidence. Citations of entries Claude was not shown are discarded.

## Storage and lifecycle

- `job_posts.advisory jsonb` + `advisory_at` (migration `20261009090000_job_posts_advisory.sql`).
- `POST /api/jobs/{id}/advisory` computes and stores; the job's `GET` returns it. The review triggers it once when work history exists; **Refresh** calls it again.
- The `Advisory` keeps `comparables`, `match_strength`, `reading` or `failure`, and the F8 note. `cite[]` is what F3 will read when drafting.

## Failure path (R8)

| Situation | Behaviour |
|---|---|
| No work history | `none_history`, no call, card says "add projects" |
| History but nothing comparable | `none_comparable`, no call |
| Claude error / empty / malformed / refusal | `failure` stored and shown with Retry; comparables still listed |
| No API key | `skipped`, configuration message |

## Open items

- Alias table coverage — extend from real jobs, with a test per alias added.
- When F8 lands, add outcome counts per comparable ("won 2 of 3 like this") and replace the fixed note.
