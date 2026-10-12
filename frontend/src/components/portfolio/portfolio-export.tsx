"use client";

// Portfolio export (F7): tick entries and options → Preview (the PDF in the
// page, with warnings about what is left out) → Approve and download, which
// is the approval: the server re-renders, checks the hash against the
// preview, logs the export, then returns the file. Export log below.

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";

import { ApiError, portfolioApi } from "@/lib/api";
import {
  MAX_ENTRIES,
  type ExportRecord,
  type PortfolioEntryOption,
  type PreviewOut,
  type Selection,
} from "@/lib/types/portfolio";

const INPUT =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900";

function selectionKey(s: Selection): string {
  return JSON.stringify({ ...s, entry_ids: [...s.entry_ids].sort() });
}

export function PortfolioExport() {
  const [entries, setEntries] = useState<PortfolioEntryOption[] | null>(null);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [includeResults, setIncludeResults] = useState(true);
  const [includeTech, setIncludeTech] = useState(true);
  const [preview, setPreview] = useState<PreviewOut | null>(null);
  const [previewKey, setPreviewKey] = useState<string | null>(null);
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [log, setLog] = useState<ExportRecord[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<"preview" | "export" | null>(null);
  const urlRef = useRef<string | null>(null);

  function loadLog() {
    portfolioApi
      .exports()
      .then(setLog)
      .catch(() => {});
  }

  useEffect(() => {
    portfolioApi
      .entries()
      .then((rows) => {
        setEntries(rows);
        setChosen(new Set(rows.slice(0, MAX_ENTRIES).map((r) => r.id)));
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load entries."),
      );
    loadLog();
    return () => {
      if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    };
  }, []);

  const selection: Selection = useMemo(
    () => ({
      entry_ids: entries
        ? entries.filter((e) => chosen.has(e.id)).map((e) => e.id)
        : [],
      title: title.trim() || null,
      from: from.trim() || null,
      to: to.trim() || null,
      include_results: includeResults,
      include_tech: includeTech,
    }),
    [entries, chosen, title, from, to, includeResults, includeTech],
  );
  const currentKey = selectionKey(selection);
  const previewFresh = preview !== null && previewKey === currentKey;
  const monthOk = (v: string) => v === "" || /^\d{4}-\d{2}$/.test(v);
  const canPreview =
    selection.entry_ids.length > 0 &&
    selection.entry_ids.length <= MAX_ENTRIES &&
    monthOk(from) &&
    monthOk(to);

  function showPdf(base64: string) {
    const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(
      new Blob([bytes], { type: "application/pdf" }),
    );
    if (urlRef.current) URL.revokeObjectURL(urlRef.current);
    urlRef.current = url;
    setPdfUrl(url);
  }

  async function doPreview() {
    setBusy("preview");
    setError(null);
    setNotice(null);
    try {
      const p = await portfolioApi.preview(selection);
      setPreview(p);
      setPreviewKey(currentKey);
      showPdf(p.pdf_base64);
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : "Could not render.");
    } finally {
      setBusy(null);
    }
  }

  async function approve() {
    if (!preview || !previewFresh) return;
    setBusy("export");
    setError(null);
    setNotice(null);
    try {
      const { blob, filename } = await portfolioApi.export(
        selection,
        preview.content_hash,
      );
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      setNotice(`Exported and logged: ${filename}`);
      loadLog();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setPreview(null); // stale: force a fresh preview
        setPreviewKey(null);
      }
      setError(e instanceof Error ? e.message : "Could not export.");
    } finally {
      setBusy(null);
    }
  }

  function toggle(id: string) {
    setChosen((cur) => {
      const next = new Set(cur);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  return (
    <section className="flex flex-col gap-5">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
        <Link href="/history" className="underline">
          Work history
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Portfolio</h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          A PDF of selected work from your own records, for attaching to
          applications. Clients are named only where the entry is marked “OK to
          name”. Nothing is written by Claude; nothing is sent anywhere.
        </p>
      </header>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}
      {notice && !error && (
        <p
          role="status"
          className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
        >
          {notice}
        </p>
      )}

      {entries === null && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}
      {entries?.length === 0 && (
        <p className="text-sm text-neutral-500">
          No work history yet.{" "}
          <Link href="/history/new" className="underline">
            Add a project
          </Link>{" "}
          first.
        </p>
      )}

      {entries && entries.length > 0 && (
        <div className="grid gap-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
          {/* options + entries */}
          <div className="flex flex-col gap-4 text-sm">
            <label className="flex flex-col gap-1">
              <span className="text-xs text-neutral-500">Title</span>
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Your name — Selected work"
                className={INPUT}
              />
            </label>
            <div className="grid grid-cols-2 gap-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs text-neutral-500">From (YYYY-MM)</span>
                <input
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                  placeholder="2024-01"
                  className={INPUT}
                />
              </label>
              <label className="flex flex-col gap-1">
                <span className="text-xs text-neutral-500">To (YYYY-MM)</span>
                <input
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  placeholder="2026-12"
                  className={INPUT}
                />
              </label>
            </div>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeTech}
                onChange={(e) => setIncludeTech(e.target.checked)}
              />
              Tech stack summary
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={includeResults}
                onChange={(e) => setIncludeResults(e.target.checked)}
              />
              Upwork results (counts and industries only; shown when any outcome
              is recorded)
            </label>

            <div className="flex items-baseline justify-between">
              <span className="text-xs font-semibold tracking-wide text-neutral-500 uppercase">
                Entries ({chosen.size} of {entries.length})
              </span>
              <span className="flex gap-3 text-xs">
                <button
                  type="button"
                  className="underline"
                  onClick={() =>
                    setChosen(
                      new Set(entries.slice(0, MAX_ENTRIES).map((e) => e.id)),
                    )
                  }
                >
                  All
                </button>
                <button
                  type="button"
                  className="underline"
                  onClick={() => setChosen(new Set())}
                >
                  None
                </button>
              </span>
            </div>
            <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
              {entries.map((e) => (
                <li key={e.id} className="px-3 py-2">
                  <label className="flex items-start gap-2">
                    <input
                      type="checkbox"
                      checked={chosen.has(e.id)}
                      onChange={() => toggle(e.id)}
                      className="mt-1"
                    />
                    <span className="flex min-w-0 flex-1 flex-col">
                      <span className="flex items-baseline justify-between gap-2">
                        <span className="truncate">{e.name}</span>
                        <span className="shrink-0 text-xs text-neutral-500">
                          {e.ended ?? e.started ?? "undated"}
                        </span>
                      </span>
                      <span className="text-xs text-neutral-500">
                        {e.vertical ?? "—"}
                        {e.has_client_name &&
                          (e.may_name_client ? (
                            <span className="ml-2 rounded bg-green-100 px-1.5 py-0.5 text-green-800 dark:bg-green-900 dark:text-green-200">
                              names client
                            </span>
                          ) : (
                            <span className="ml-2 rounded bg-neutral-100 px-1.5 py-0.5 dark:bg-neutral-800">
                              client not named
                            </span>
                          ))}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>
            {chosen.size > MAX_ENTRIES && (
              <p className="text-xs text-amber-800 dark:text-amber-200">
                At most {MAX_ENTRIES} entries per PDF.
              </p>
            )}

            <div className="flex items-center gap-3">
              <button
                type="button"
                onClick={() => void doPreview()}
                disabled={busy !== null || !canPreview}
                className="rounded border border-neutral-300 px-4 py-2 text-sm disabled:opacity-50 dark:border-neutral-700"
              >
                {busy === "preview" ? "Rendering…" : "Preview"}
              </button>
              {preview && !previewFresh && (
                <span className="text-xs text-amber-800 dark:text-amber-200">
                  Selection changed — preview again to approve the new version.
                </span>
              )}
            </div>
          </div>

          {/* preview + approve */}
          <div className="flex flex-col gap-3">
            {preview && pdfUrl ? (
              <>
                {preview.warnings.length > 0 && (
                  <ul className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
                    {preview.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                )}
                <iframe
                  title="Portfolio preview"
                  src={pdfUrl}
                  className="h-[70vh] w-full rounded border border-neutral-200 dark:border-neutral-800"
                />
                <div className="flex flex-col gap-2 rounded-lg border border-neutral-200 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-neutral-800">
                  <div className="text-sm">
                    <p className="font-medium">
                      {preview.manifest.entries.length} entr
                      {preview.manifest.entries.length === 1
                        ? "y"
                        : "ies"} · {preview.page_count} page
                      {preview.page_count === 1 ? "" : "s"}
                    </p>
                    <p className="text-xs text-neutral-500">
                      Clicking is the approval; every export is logged with the
                      document’s hash. Hash {preview.content_hash.slice(0, 12)}…
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={() => void approve()}
                    disabled={busy !== null || !previewFresh}
                    className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                  >
                    {busy === "export" ? "Exporting…" : "Approve and download"}
                  </button>
                </div>
              </>
            ) : (
              <p className="rounded border border-dashed border-neutral-300 p-6 text-center text-sm text-neutral-500 dark:border-neutral-700">
                Preview to see the PDF here before approving.
              </p>
            )}
          </div>
        </div>
      )}

      <section className="text-sm">
        <h2 className="mb-2 text-xs font-semibold tracking-wide text-neutral-500 uppercase">
          Export log
        </h2>
        {log.length === 0 ? (
          <p className="text-neutral-500">No exports yet.</p>
        ) : (
          <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
            {log.map((r) => (
              <li
                key={r.id}
                className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2"
              >
                <span>
                  {new Date(r.exported_at).toLocaleString()} · {r.entry_count}{" "}
                  entr{r.entry_count === 1 ? "y" : "ies"} · {r.page_count} page
                  {r.page_count === 1 ? "" : "s"}
                </span>
                <code className="text-xs text-neutral-500">
                  {r.content_hash.slice(0, 12)}…
                </code>
              </li>
            ))}
          </ul>
        )}
      </section>
    </section>
  );
}
