"use client";

// Settings → Review queue (F8, R8): outcomes Zoho posted for an Upwork job ID
// the app does not know. Each shows the payload as sent, and the operator
// either matches it to one of their continued jobs' proposals or dismisses
// it. Nothing is dropped silently.

import Link from "next/link";
import { useEffect, useState } from "react";

import { jobsApi, outcomesApi, proposalsApi } from "@/lib/api";
import type { JobPostSummary } from "@/lib/types/job";
import type { QueuedOutcome } from "@/lib/types/outcomes";

export function ReviewQueue() {
  const [queue, setQueue] = useState<QueuedOutcome[] | null>(null);
  const [jobs, setJobs] = useState<JobPostSummary[]>([]);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function load() {
    Promise.all([outcomesApi.queue(), jobsApi.list()])
      .then(([q, j]) => {
        setQueue(q);
        setJobs(j.filter((x) => x.decision === "continue"));
      })
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load."),
      );
  }

  useEffect(load, []);

  async function match(item: QueuedOutcome) {
    const jobId = choice[item.id];
    if (!jobId) return;
    setBusy(item.id);
    setError(null);
    setNotice(null);
    try {
      const proposal = await proposalsApi.forJob(jobId);
      if (!proposal) {
        setError("That job has no proposal yet; draft one first, then match.");
        return;
      }
      const result = await outcomesApi.match(item.id, proposal.proposal.id);
      setNotice(result.message);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not match.");
    } finally {
      setBusy(null);
    }
  }

  async function dismiss(item: QueuedOutcome) {
    if (
      !window.confirm(
        "Dismiss this outcome? It stays in the database but leaves the queue and is not recorded against any proposal.",
      )
    )
      return;
    setBusy(item.id);
    setError(null);
    try {
      await outcomesApi.dismiss(item.id);
      setNotice("Dismissed.");
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not dismiss.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
        <Link href="/settings/outcomes" className="underline">
          Outcome webhook
        </Link>
      </nav>
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Review queue</h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          Outcomes Zoho sent for a job this app could not match (usually a Lead
          created by hand, or a job pasted without its link). Match each to the
          right proposal, or dismiss it.
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
      {queue === null && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}
      {queue?.length === 0 && (
        <p className="text-sm text-neutral-500">Nothing waiting.</p>
      )}

      {queue && queue.length > 0 && (
        <ul className="flex flex-col gap-3">
          {queue.map((item) => {
            const p = item.payload as Record<string, unknown>;
            return (
              <li
                key={item.id}
                className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p>
                    <span className="font-medium">{String(p.outcome)}</span>
                    {p.lost_reason ? (
                      <span className="text-neutral-500">
                        {" "}
                        ({String(p.lost_reason)})
                      </span>
                    ) : null}{" "}
                    <span className="text-neutral-500">
                      for Upwork job <code>{item.upwork_job_id}</code>
                    </span>
                  </p>
                  <span className="text-xs text-neutral-500">
                    received {new Date(item.received_at).toLocaleString()}
                    {item.zoho_lead_id && ` · Lead ${item.zoho_lead_id}`}
                  </span>
                </div>
                <details>
                  <summary className="cursor-pointer text-xs text-neutral-500">
                    Payload as Zoho sent it
                  </summary>
                  <pre className="mt-2 max-h-48 overflow-auto rounded bg-neutral-50 p-2 text-xs dark:bg-neutral-900">
                    {JSON.stringify(item.payload, null, 2)}
                  </pre>
                </details>
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <select
                    value={choice[item.id] ?? ""}
                    onChange={(e) =>
                      setChoice((c) => ({ ...c, [item.id]: e.target.value }))
                    }
                    className="w-full rounded border border-neutral-300 px-3 py-2 text-sm sm:max-w-md dark:border-neutral-700 dark:bg-neutral-900"
                  >
                    <option value="">Match to a job you continued…</option>
                    {jobs.map((j) => (
                      <option key={j.id} value={j.id}>
                        {j.title ?? "Untitled"}
                        {j.upwork_job_id ? ` (${j.upwork_job_id})` : ""}
                      </option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    <button
                      type="button"
                      disabled={busy !== null || !choice[item.id]}
                      onClick={() => void match(item)}
                      className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                    >
                      {busy === item.id ? "Working…" : "Match"}
                    </button>
                    <button
                      type="button"
                      disabled={busy !== null}
                      onClick={() => void dismiss(item)}
                      className="rounded border border-neutral-300 px-3 py-2 text-xs disabled:opacity-50 dark:border-neutral-700"
                    >
                      Dismiss
                    </button>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
