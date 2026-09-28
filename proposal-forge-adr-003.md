# ADR-003: Learning Strategy (RAG Index vs Fine-Tuning)

**Status:** Accepted  
**Date:** 2026-09-27  
**Deciders:** John Lamont

## Context

As proposals are submitted and outcomes recorded, the system should improve:
- "You've won 5 of 7 similar jobs in compliance"
- "Budget is low for scope; similar deal failed in Q1"
- "This client type responds better to technical tone"

Need to choose: in-context RAG (store outcomes, query at draft time) or fine-tune Claude model.

## Options Considered

### Option A: RAG Index (Retrieval-Augmented Generation) — Chosen

| Dimension | Assessment |
|-----------|-----------|
| **Setup cost** | Low (add rag_index table, query function) |
| **Ongoing cost** | $0 (query cost is negligible) |
| **Quality ramp** | Slow (needs 20-30 outcomes to show signal) |
| **Accuracy** | Improves with context, not retrained |
| **Iteration speed** | Instant (add outcome, next proposal sees it) |
| **Transparency** | High (you can see exactly what Claude learns) |

**Pros:**
- Zero cost (no fine-tuning fee)
- Works with Claude API directly (no training pipeline)
- Instant updates (record outcome, immediately available for next proposal)
- Fully versioned (can deprecate old proposals over time)
- Transparent (you can inspect rag_index to see what "works")
- Decoupled from Claude's model version (works with Claude 3, 4, future versions)
- Easy to experiment (adjust what goes into RAG context)
- Works with prompting (no model changes needed)

**Cons:**
- Quality improves slowly (needs 30+ outcomes to have strong signal)
- Requires active participation (you must record outcomes)
- No generalization across similar tasks (only works for exact context matches)
- Prompt complexity grows (more context to include)
- Query latency (slight overhead for Postgres similarity search)

**Implementation:**
```
1. User marks proposal "won"
   → Entry added to rag_index {proposal_id, outcome, vertical, budget, draft}

2. Next proposal in same vertical
   → Query rag_index for similar outcomes (WHERE vertical = X AND budget IN range)
   → Include in Claude prompt: "Similar past proposals: [list of wins/losses]"
   → Claude advisor: "You won X of Y like this"

3. Learning is implicit (via context, not explicit training)
```

### Option B: Fine-Tune Model

| Dimension | Assessment |
|-----------|-----------|
| **Setup cost** | High (data pipeline, training infra) |
| **Ongoing cost** | High ($25-100+ per fine-tune run) |
| **Quality ramp** | Fast (can see improvement in 10-20 examples) |
| **Accuracy** | Can generalize better (model learns patterns) |
| **Iteration speed** | Slow (retrain takes hours) |
| **Transparency** | Low (black box; hard to see what model learned) |

**Pros:**
- Better generalization (model learns patterns, not just memorizes)
- Quality ramp is faster (10-20 examples can shift behavior)
- Can apply to new situations (model doesn't need exact match)
- Works better for complex patterns (e.g., "this tone works for this client type")

**Cons:**
- High cost ($25-100 per fine-tune, recurring)
- Slow iteration (hours to days per retrain)
- Requires substantial data first (need 50+ examples for meaningful fine-tune)
- Vendor lock-in (if Claude deprecates a model, fine-tune invalidates)
- Hard to debug (why did the model learn that?)
- Overkill for MVP with sparse data
- Ongoing cost scales linearly with retrains

**When it makes sense:**
- After 100+ proposals with consistent patterns
- If RAG accuracy plateaus and fine-tuning lifts performance
- If you're willing to pay for better results

### Option C: Simple Rules Engine

| Dimension | Assessment |
|-----------|-----------|
| **Setup cost** | Medium (decision tree logic) |
| **Ongoing cost** | $0 |
| **Quality** | Limited (rules are brittle) |
| **Iteration speed** | Instant (code update) |

**Pros:**
- Zero cost
- Instant iteration
- Easy to understand

**Cons:**
- Breaks down with edge cases
- Can't learn subtlety (tone, client psychology)
- Requires manual rule tuning
- Doesn't scale (5 rules works, 50 rules unmaintainable)

**Example rule:**
```
IF vertical = "compliance" AND budget < 10K
THEN confidence = "high"
```

Too simplistic for real judgment.

## Trade-off Analysis

**Cost:**
- RAG (A) = $0 ✓
- Fine-tune (B) = $100+/month
- Rules (C) = $0

**Quality at MVP (30 proposals):**
- RAG (A) = Emerging (some useful patterns, not all)
- Fine-tune (B) = Too early (underfitting, poor ROI)
- Rules (C) = Very limited

**Quality at scale (200 proposals):**
- RAG (A) = Good (strong contextual matching)
- Fine-tune (B) = Excellent (generalized patterns)
- Rules (C) = Still limited

**Iteration speed:**
- RAG (A) = Instant ✓
- Fine-tune (B) = Hours-to-days
- Rules (C) = Code deploy

**Learning experience for you:**
- RAG (A) = Learn RAG patterns, prompt engineering ✓
- Fine-tune (B) = Learn fine-tuning (less relevant to consulting)
- Rules (C) = Learn nothing new

**Portfolio value:**
- RAG (A) = Modern AI skill (RAG is industry trend) ✓
- Fine-tune (B) = Advanced ML (overkill for this project)
- Rules (C) = Boring (rules engines aren't impressive)

## Decision

**Use RAG Index (Option A).**

- Zero cost (MVP constraint)
- Instant updates (immediate learning)
- Transparent (you can audit what works)
- Scales to 200+ proposals without cost increase
- Modern skill (RAG is relevant to GitHub portfolio)
- Clear path to fine-tuning later (if ROI justifies it)

Implementation:
1. Create `rag_index` table (proposal_id, outcome, vertical, budget, draft_excerpt)
2. On outcome record: INSERT into rag_index
3. On new proposal draft: Query rag_index for similar outcomes, include in Claude prompt
4. Monitor quality; consider fine-tuning at 100+ proposals with clear patterns

## Consequences

**What becomes easier:**
- Experimenting with what goes into RAG context (no retraining cost)
- Auditing what Claude learned (query rag_index directly)
- Deprecating old proposals (mark as archived, exclude from future queries)
- Multi-version models (works with Claude 3, 4, future versions)

**What becomes harder:**
- Generalizing across dissimilar contexts (RAG is exact-match-ish)
- Improving without more proposals (needs 20+ outcomes to help)
- Subtle pattern detection (model fine-tune would catch this faster)

**What we'll need to revisit:**
- After 30 proposals: Is RAG advisory useful? (probably emerging signal)
- After 100 proposals: Should we fine-tune? (calculate ROI: cost vs. win rate lift)
- Query performance: If rag_index grows >1K entries, add indexing/caching

## Related Decisions

- ADR-001: Database choice (PostgreSQL supports full-text search for RAG)
- Proposal workflow: Two-stage design (job analysis + draft) enables RAG at draft time
- Historical projects: Bootstrap from GitHub/local (warm-start RAG before real proposals)
