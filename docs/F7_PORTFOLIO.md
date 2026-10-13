# F7 — PDF portfolio export: design

Governance entry: [FEATURE_REGISTER.md → F7](governance/FEATURE_REGISTER.md#f7--pdf-portfolio-export), **high-stakes** (public-facing: attached to job applications). Screens: [FRONTEND.md → Portfolio export](FRONTEND.md#portfolio-export--portfolio-f7).

**No AI call.** The PDF is assembled from records the operator already confirmed: their profile, their work history (F5), and outcome counts (F8). Claude writes none of it, so there is nothing to classify or threshold; the high-stakes handling is about what leaves the system and who approved it.

## What the operator does

1. Open **Portfolio**. Every work-history entry is listed with a tick box (all ticked by default), its vertical, and a badge where the client will be named because the entry is marked *OK to name*. Options: a title, a date range, whether to include the **Upwork results** section and the **Tech stack** summary.
2. **Preview**. The app renders the PDF and shows it in the page, together with the list of entries whose client name is *not* shown and why.
3. **Approve and download**. One button, labelled as the approval. The app renders the same document again, checks it is byte-for-byte what was previewed, records the export (who, when, content hash, what was selected) in an append-only table, and returns the file. If anything changed since the preview, nothing is downloaded and the operator is asked to preview again.
4. **Export log** below: each export with its time, entry count and hash.

## The document

Rendered with ReportLab (pure Python, no system libraries; runs the same on Fly's Linux image and on Windows). One template, A4 and Letter switchable later.

| Section | From | Rule 5 boundary |
|---|---|---|
| Title block: operator's name, positioning paragraph, generated date | `profiles.signature_name`, `profiles.positioning` | No contact details are stored, so none appear; the operator adds them on Upwork |
| **Selected work**, one block per entry: name, period, role, vertical, summary, tech stack, outcomes | `work_history` | `client_name` appears only when `may_name_client` is true; otherwise the line reads "for a [vertical] client" or is omitted. `budget_band`, `source_files`, `ai_extraction`, `client_name_detected` never appear |
| **Tech stack**: each technology with the number of selected entries that used it | aggregated from the selected entries | — |
| **Upwork results** (optional, shown only when at least one outcome is recorded): proposals won / bid-and-lost / withdrawn, and the industries won in | `rag_index` counts (non-archived) | Counts and industry names only; no job titles, no Lead or client data. "Judged not worth bidding" outcomes are left out: they describe the job, not the operator |
| Footer on every page: "Prepared from the consultant's own records with Proposal Forge · page n of N" | code | Plain statement of origin; no AI involvement to disclose |

## Determinism and the approval record (R1, R2)

The PDF is built from a **manifest**: a canonical JSON document holding exactly the text that will be rendered (title, operator block, entries in order with their shown fields, tech counts, results counts, generated date). `content_hash` = SHA-256 of the manifest. The renderer is a pure function of the manifest with ReportLab's `invariant` mode on, so the same manifest gives the same bytes; the export row also stores the SHA-256 of the bytes.

Preview returns the manifest, its hash and the PDF. Approve sends the selection and the hash back. The server rebuilds the manifest from current data and compares: a match logs the export and streams the file; a mismatch (an entry edited, a client-naming flag flipped, an outcome arrived) is a `409` and the operator previews again. The approval therefore covers exactly the document that was seen.

`portfolio_exports` — **append-only** (same `refuse_change` trigger): `id`, `user_id`, `content_hash`, `pdf_hash`, `selection jsonb` (entry ids and options), `entry_count`, `page_count`, `exported_by`, `exported_at`. RLS: owner select and insert; no update or delete policy.

## Failure path (R8)

| Situation | Behaviour |
|---|---|
| No entries selected, or none match the date range | `422` before rendering; the button is disabled in the UI too |
| Profile has no name or positioning | `409` "Set up your profile first" with the link; nothing rendered |
| Renderer raises | `500` "Could not generate the PDF; nothing was exported"; no row written; the error is logged server-side |
| Approve after data changed | `409`; the preview is marked stale and the operator previews again |
| Export row cannot be written | the file is **not** returned; `500`; the operator retries. An export without its record never happens |
| Very large selection | the renderer paginates; a soft cap of 40 entries is enforced with `422` so a PDF cannot run to dozens of pages by accident |

## API

| Route | Does |
|---|---|
| `GET /api/portfolio/entries` | the selectable entries: id, name, vertical, period, `may_name_client`, `has_client_name` |
| `POST /api/portfolio/preview` | body: selection → `{manifest, content_hash, pdf_base64, page_count, warnings[]}` |
| `POST /api/portfolio/exports` | body: selection + `content_hash` → verifies, logs, returns `application/pdf` with `Content-Disposition: attachment` |
| `GET /api/portfolio/exports` | the export log |

Selection: `{entry_ids: [...], title: str | null, from: "YYYY-MM" | null, to: "YYYY-MM" | null, include_results: bool, include_tech: bool}`.

## Screens (FRONTEND.md → `/portfolio`)

- Left (or top on the phone): the options and the entry list with tick boxes and the "names client" badge; a note under entries whose client will not be named.
- **Preview** button; the PDF in an `<iframe>` from a blob URL, with page count.
- **Approve and download**: enabled only while the preview matches the current selection (any change re-disables it with "Preview again to approve the new version"). Under the button: "Clicking is the approval; every export is logged."
- **Export log**: time, entries, pages, hash prefix.

## Tests the code PR includes

Manifest: client name present only with `may_name_client`; budget band, source files and extraction never present; entries filtered by date range and ordered newest first; tech counts; results section absent with no outcomes and excludes not-worth-bidding outcomes; canonical hash stable across key order. Renderer: produces a PDF (magic bytes, page count) and is deterministic for the same manifest. Routes: preview with no selection → 422; profile not ready → 409; approve with stale hash → 409 and no row; approve success writes one row and returns `application/pdf`; renderer failure → 500 and no row; log lists exports newest first. Migration: append-only trigger refuses update/delete.

## Delivery

1. **F7a** — register entry completed and this design (docs PR).
2. **F7b** — migration, manifest builder, renderer, routes, tests.
3. **F7c** — the `/portfolio` screen, nav link, completion docs.
