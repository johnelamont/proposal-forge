# F1 — Job post parsing: design

Governance entry: [FEATURE_REGISTER.md → F1](governance/FEATURE_REGISTER.md#f1--job-post-parsing). Evidence: three real pastes in [`backend/tests/fixtures/`](../backend/tests/fixtures/README.md). This document is what the F1 code PR is reviewed against.

## What the operator does

1. On Upwork (desktop or the mobile app), open a job, select all, copy.
2. In Proposal Forge, paste into one text box and click **Parse**.
3. Review the result: structured fields on one side, Claude's reading of the description on the other, with any `conflicts` and missing-field prompts on top.
4. Click **Continue** (to F2 / F3) or **Abandon**. Both are recorded; nothing is saved as a parsed job until one is clicked.

## Two layers, by design

An Upwork paste is ~80% machine-formatted (one label per line, in sections) and ~20% prose. The two parts get different treatment:

| Layer | Reads | Produces | Why |
|---|---|---|---|
| **Deterministic parser** (Python, no AI) | Everything except the *Summary* body | Every labelled field: engagement, rates, skills, activity, connects, client statistics, job link | Exact, free, testable against fixtures, and keeps *About the client* and *Client's recent history* out of any prompt (R5) |
| **Claude** | Title + *Summary* body + skills + Upwork-native questions | Scope, requirements, questions found in prose, the client's own budget/timeline statements, red flags, a sensitive-domain flag, per-field confidence | Prose needs reading, and only prose |

The deterministic layer runs first and always. The Claude layer is additive: if it fails, the operator still gets every structured field (R8).

## Section detection

Observed layouts (see fixtures): desktop and mobile differ in order and in which sections exist. The parser therefore does not assume order. It scans for **section heading lines** and treats the text between two headings as that section's body:

```text
Summary
Skills and Expertise
Preferred qualifications
Activity on this job
About the client
Job link
Client's recent history (N)
Other open jobs by this Client (N)
You will be asked to answer the following questions when submitting a proposal:
```

- Lines **before** `Summary` are the header: title (first non-empty line), `Posted …`, and the location restriction (`Worldwide` / `Only freelancers located in … may apply.`). On mobile, `Send a proposal for: N Connects` / `Available Connects: N` can appear here too; they are matched wherever they occur.
- The **engagement block** (`More than 30 hrs/week`, `Hourly`, `1 to 3 months`, `Duration`, `Intermediate`, rate range, `Project Type: …`, `Contract-to-hire opportunity`) has no heading. It is located as the run of recognised engagement lines between the end of the *Summary* body and `Skills and Expertise` (or the questions heading). The *Summary* body is everything after `Summary` up to the first recognised engagement line.
- Boilerplate lines are dropped: `Copy link`, `Learn more`, `This lets talent know that this job could become full time.`, `Duration`, `Experience Level`, `I am looking for a mix of experience and value` (the last two are the desktop/mobile variants of the same explanatory line).
- Unrecognised lines are kept in `unparsed_lines` and shown in a collapsed "Didn't understand" panel, so layout changes are visible rather than silent.

## Field normalisation

Raw text is kept alongside the normalised value wherever the wording varies between layouts.

| Field | Observed wordings | Normalised |
|---|---|---|
| Hours per week | `More than 30 hrs/week`, `Less than 30 hrs/week` | `gt30` / `lt30` |
| Duration | `More than 6 months`, `6+ months`, `1 to 3 months`, `3 to 6 months`, `Less than 1 month` | `gt6m` / `3to6m` / `1to3m` / `lt1m` |
| Experience level | `Entry level`, `Intermediate`, `Expert` | enum |
| Payment type | `Hourly` (in engagement block), fixed-price variants to be confirmed from a fixed-price fixture | `hourly` / `fixed` |
| Rate range | `$25.00` / `-` / `$65.00` across five lines, then `Hourly` | `hourly_rate_min`, `hourly_rate_max` as `Decimal` |
| Proposals | `20 to 50`, `15 to 20`, `50+`, `Less than 5` | `proposals_min`, `proposals_max` (`null` max for `50+`) |
| Bid range | `Bid range - High $75.00 Avg $54.62 Low $30.00` | three `Decimal`s |
| Total spent | `$11K`, `$814K`, `$1.2M` | `Decimal` dollars |
| Hire rate | `45% hire rate, 2 open jobs` | `hire_rate_pct`, `open_jobs` |
| Hires | `5 hires, 1 active` | `hires`, `active_hires` |
| Job link | `https://www.upwork.com/jobs/~0221…` | `upwork_job_id` = the `~…` token |

Every field is nullable. Absence is `null`; the parser never fills a default that looks like data (R8).

## Parse result (shape)

```text
ParsedJob
  source_format        "desktop" | "mobile" | "unknown"   (heuristic: job link present + history entries → desktop)
  title                str
  posted_ago_raw       str | null
  location_restriction str | null
  upwork_job_id        str | null          ← null is expected on mobile; F6 requires it
  description          str                 (Summary body, verbatim)
  engagement
    hours_per_week     enum | null, hours_per_week_raw
    payment_type       enum | null
    duration           enum | null, duration_raw
    experience_level   enum | null
    hourly_rate_min/max  Decimal | null
    fixed_budget       Decimal | null
    project_type       "ongoing" | "one_time" | null
    contract_to_hire   bool
  skills               [str]
  preferred_qualifications  { job_success_score_min, english_level, ... }  raw label → value pairs
  activity             { proposals_min, proposals_max, last_viewed_raw, interviewing, invites_sent, unanswered_invites, bid_high, bid_avg, bid_low }
  connects             { required, available }
  client               { payment_verified, phone_verified, rating, review_count, country, city, jobs_posted, hire_rate_pct, open_jobs, total_spent, hires, active_hires, avg_hourly_paid, hours_billed, industry, company_size, member_since }
  questions            [ { text, source: "upwork" | "description" } ]
  ai                   AiReading | null     ← null when the Claude layer failed; see failure path
  conflicts            [ { field, upwork_value, description_value, evidence } ]
  unparsed_lines       [str]
```

`questions` merges the Upwork-native list (deterministic) with questions Claude finds in the prose; F3 treats both the same.

## The Claude call

**Input (R5):** `title`, `description`, `skills`, and the Upwork-native `questions` (so Claude does not duplicate them). Nothing else from the paste. The prompt states that the text is a public job advertisement pasted by the operator and asks for JSON only.

**Output (`AiReading`):**

```text
AiReading
  one_line                str        what the client actually wants, in one sentence
  deliverables            [str]
  requirements            [str]      must-haves stated by the client (tools, timezone, NDA, examples to share)
  questions_in_description [str]     e.g. under "When you apply, please tell us:"
  budget_statement        { model: "hourly" | "fixed" | "unstated", amount_raw, milestones: [str] } | null
  timeline_statement      str | null
  red_flags               [str]      e.g. rate ceiling vs scope, vague scope, unpaid test work
  sensitive_data_domain   { flag: bool, reason: str | null }   health, immigration/legal status, finance → operator's own R6/R7 checkpoint
  confidence              { field_name: 0.0–1.0 }   for each field above
```

**Conflicts** are computed after both layers finish: if `budget_statement.model` is `fixed` and `engagement.payment_type` is `hourly` (or vice versa), or if a stated amount is outside the Upwork range, a `conflicts` entry is added with Claude's evidence sentence. The parser never resolves a conflict; the operator does, on the review screen.

**Confidence** is display-only. F1 is Standard and drives no automated write, so there is no routing threshold; fields under 0.6 are rendered with a "low confidence" marker and their evidence sentence so the operator checks them. (R3 thresholds that *do* route appear first in F6.)

## Failure path (R8)

| Failure | Behaviour |
|---|---|
| Claude API error, timeout, or empty response | Deterministic fields shown normally. The AI panel shows the error text and a **Retry** button. `ai = null`. Nothing is saved until the operator clicks Continue or Abandon; Continue is allowed with `ai = null` (the operator can fill scope manually in F3). |
| Claude returns non-JSON or JSON that fails schema validation | Same as above, with "malformed response" as the message. The raw response is logged server-side (no paste content in the log line, just the error class and length). |
| Paste too short / no recognised sections | Parse returns the title guess and `unparsed_lines` only, with a banner: "This doesn't look like an Upwork job post." Claude is not called. |
| No job link in the paste | Parse succeeds; `upwork_job_id = null`; a field "Job link — paste the URL from Upwork's Share button" is shown and persists until filled. F6 refuses to create a Lead without it. |
| Fields absent (mobile rate range, new-client stats) | `null`, displayed as "—", never as 0 or a default. |

## Storage (outline for the code PR's migration)

One `job_posts` table, owned by the user (`user_id` = `auth.uid()`, RLS on every statement):

- `raw_paste text` — kept so a job can be re-parsed after a parser fix without a new copy-paste
- `parsed jsonb` — the deterministic result
- `ai_reading jsonb null` — the Claude result, `null` on failure
- `parse_status` — `ok` | `ai_failed` | `unrecognised`
- `upwork_job_id text null`, unique per user when not null
- `decision` — `continue` | `abandon` | `null` (unset until clicked), `decided_at`

Proposals (F3) reference a `job_posts` row. The approval and audit tables belong to F3's migration, not this one.

## Tests the code PR must include

- Each fixture parses with the expected structured values (golden JSON per fixture).
- Each fixture's *Summary* body matches exactly what would be sent to Claude — the R5 boundary is asserted, not assumed.
- Neither *About the client* nor *Client's recent history* text appears anywhere in the Claude input, for all three fixtures.
- The conflict fixture yields exactly one `conflicts` entry for budget model.
- The mobile fixture yields `upwork_job_id = null` and two Upwork-native questions.
- Claude layer: mocked error, empty, non-JSON, and schema-invalid responses each produce `ai = null` with the right `parse_status`, and the deterministic fields are unaffected.

## Open items

- No fixed-price fixture yet. The fixed-price budget line's exact wording is unconfirmed; `fixed_budget` parsing ships behind a test the moment a fixture exists.
- The mobile fixture was relayed through a chat app; replace with a raw paste when available.
