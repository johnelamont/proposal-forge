# F5 — Work history: design

Governance entry: [FEATURE_REGISTER.md → F5](governance/FEATURE_REGISTER.md#f5--historical-project-analysis-dropped-files). Screen outline: [FRONTEND.md → Work history](FRONTEND.md#work-history--history-f5). This document is what the F5 code PRs are reviewed against.

## What the operator does

1. `/history` → **Add project** → *drop files* or *enter manually*.
2. Drop one or more files (nine times out of ten a `README.md`). Each file is listed as **accepted** or **refused with a reason** before anything is sent. A one-line reminder notes that a client contract may restrict sharing project docs with an AI processor (R4).
3. **Extract** → Claude's reading prefills an editable form. Low-confidence fields are marked.
4. Edit, decide whether the client may be named, **Save to work history**. Nothing is stored before Save.

## The file gate (R5)

`backend/app/services/file_rules.py`, applied on `extract` and again on save; the browser mirrors it for immediate feedback but the server decides.

| Rule | Outcome |
|---|---|
| Extension `.md .markdown .txt .rst .adoc`, or a manifest by name (`package.json`, `pyproject.toml`, `requirements*.txt`, `Cargo.toml`, `go.mod`, `composer.json`, `Gemfile`, `setup.py/.cfg`, `pom.xml`, `build.gradle`, `*.csproj`) | accepted |
| `.env*`; `.pem .p12 .pfx .key .crt .cer .der .jks .kdbx .ppk`; `id_rsa*`-style; names containing `secret`, `credential`, `token` as a word | refused — credentials |
| Archives; `.csv .tsv .xlsx .xls .db .sqlite .parquet .sql .bak .dump`; other `.json .yaml .toml .ini .cfg .conf .xml` | refused — data/config |
| Anything else | refused — unsupported type |
| Empty; over 200 KB; total over 400 KB; more than 5 files | refused — size/count |
| **Content**: `BEGIN … PRIVATE KEY`; `sk-ant-…`, `AKIA…`, `gh?_…`, `xox?-…` tokens; a `PASSWORD=` / `API_KEY=` / `TOKEN=` assignment whose value is not an obvious placeholder (`your-…`, `<…>`, `${…}`, `changeme`, …); NUL bytes | refused — secret or binary |

Every rule has a test in `backend/tests/test_file_rules.py`, including the placeholder allowance so a README's setup section does not get a project refused.

## The Claude call

Shared core: `structured_call` in `backend/app/services/claude.py` (also used by F1). Input is exactly the accepted files, verbatim, each under a `=== file: <name> ===` header. Output (`Extraction`):

```text
name, summary, tech_stack[], vertical, project_type,
complexity (low|medium|high) + complexity_reason, role, outcomes[],
client_name_detected, duration_hint, confidence per field
```

`client_name_detected` is information for the operator; it never sets `may_name_client`.

## Storage

`work_history` (migration `20261007190000_work_history.sql`), owner-scoped RLS on select/insert/update/delete:

- Operator-confirmed columns: `name`, `summary`, `tech_stack[]`, `vertical`, `project_type`, `complexity`, `role`, `outcomes[]`, `client_name`, `may_name_client` (default false), `budget_band`, `started`, `ended` (`YYYY-MM`)
- `source_files jsonb` — name, size, sha256 and the text of each accepted file, so an entry can be re-extracted after a prompt improvement without re-dropping
- `ai_extraction jsonb` — Claude's original reading, for provenance; the columns hold the operator's version

What F2 reads: `tech_stack`, `vertical`, `project_type`, `complexity`, `budget_band`, `outcomes`, `summary`. What F3 may cite: `summary`, `outcomes`. Neither sends `client_name`. What F7 reads: everything, naming the client only when `may_name_client` is true.

## API

| Route | Does |
|---|---|
| `POST /api/work-history/extract` | screen → Claude → draft. **Never writes.** Returns `accepted`, `refused`, and either `extraction` or `failure`. |
| `POST /api/work-history` | save the operator's record (files re-screened; a refused file rejects the request) |
| `GET /api/work-history` | summaries, newest-ended first |
| `GET/PATCH/DELETE /api/work-history/{id}` | read, partial update (`clear: [...]` nulls fields), delete |

## Failure path (R8)

| Failure | Behaviour |
|---|---|
| All files refused | `extraction = null`, `failure.kind = skipped`, refused list shown; Claude not called |
| Claude error / empty / malformed / refusal | `failure` returned with the kind; the form opens empty with the message; files stay listed; **Retry** or type it in |
| Save with a file that fails screening | 422 naming the file and reason; nothing written |
| No API key configured | `skipped` with a server-configuration message, not a crash |

## Tests the frontend PR must add to the manual plan

- Drop a README with `API_KEY=your-key-here` in it → accepted (placeholder).
- Drop `.env` alongside → listed as refused, README still extracted.
- Extraction failure → form usable, Save works with typed values.
- `may_name_client` stays off unless ticked, even when a client name was detected.
