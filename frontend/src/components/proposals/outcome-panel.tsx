"use client";

// The Outcome section of the proposal workspace (F8): current status, the
// append-only outcome history as it arrived from Zoho, the link to the Lead,
// the follow-up nudge, and what was indexed for learning. No outcome-entry
// controls: outcomes are recorded in Zoho, never here.

import Link from "next/link";
import { useEffect, useState } from "react";

import { outcomesApi } from "@/lib/api";
import {
  LOST_REASON_LABEL,
  type OutcomeRecord,
  type ProposalOutcomes,
} from "@/lib/types/outcomes";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "—";
}

function describe(o: OutcomeRecord): string {
  if (o.outcome === "lost" && o.lost_reason) {
    return `lost — ${LOST_REASON_LABEL[o.lost_reason]}`;
  }
  return o.outcome;
}

export function OutcomePanel({
  proposalId,
  status,
  onChanged,
}: {
  proposalId: string;
  status: string;
  onChanged?: () => void;
}) {
  const [data, setData] = useState<ProposalOutcomes | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    outcomesApi
      .forProposal(proposalId)
      .then(setData)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load outcomes."),
      );
  }, [proposalId, status]);

  async function toggleArchive() {
    if (!data?.index) return;
    setBusy(true);
    setError(null);
    try {
      const row = await outcomesApi.setArchived(
        proposalId,
        !data.index.archived,
      );
      setData({ ...data, index: row });
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not update.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-neutral-200 p-4 text-sm dark:border-neutral-800">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-medium">Outcome</h2>
        {data && (
          <span className="text-xs text-neutral-500">
            status: <span className="font-medium">{data.status}</span>
          </span>
        )}
      </header>

      {error && (
        <p role="alert" className="text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      {!data && !error && <p className="text-neutral-500">Loading…</p>}

      {data && (
        <>
          <p className="text-xs text-neutral-500">
            Outcomes are recorded in Zoho, on the Lead: the <b>Won</b> button,
            or Lead Status for lost and withdrawn. Zoho posts them here; nothing
            is entered in this app.{" "}
            {data.lead_url ? (
              <a
                href={data.lead_url}
                target="_blank"
                rel="noreferrer"
                className="underline"
              >
                Open the Lead in Zoho
              </a>
            ) : (
              <span>
                No Lead in Zoho yet — create it from the Submit panel first.
              </span>
            )}
          </p>

          {data.stale && (
            <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
              Submitted {when(data.submitted_at)} with no outcome after{" "}
              {data.stale_after_days} days. Follow up on Upwork? Then record
              what you find on the Lead in Zoho.
            </p>
          )}

          {data.history.length === 0 ? (
            <p className="text-neutral-500">No outcome received yet.</p>
          ) : (
            <ol className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
              {data.history.map((o, i) => (
                <li
                  key={o.id}
                  className="flex flex-wrap items-baseline justify-between gap-2 px-3 py-2"
                >
                  <span>
                    <span
                      className={
                        o.outcome === "won"
                          ? "font-medium text-green-700 dark:text-green-400"
                          : "font-medium"
                      }
                    >
                      {describe(o)}
                    </span>
                    {i === 0 && data.history.length > 1 && (
                      <span className="ml-2 text-xs text-neutral-500">
                        latest
                      </span>
                    )}
                  </span>
                  <span className="text-xs text-neutral-500">
                    decided {when(o.decided_at)} · received{" "}
                    {when(o.received_at)} · via{" "}
                    {o.source === "zoho" ? "Zoho" : "manual match"}
                  </span>
                </li>
              ))}
            </ol>
          )}

          {data.index && (
            <details className="rounded border border-neutral-200 p-3 dark:border-neutral-800">
              <summary className="cursor-pointer text-xs font-medium">
                What was indexed for learning
                {data.index.archived && (
                  <span className="ml-2 font-normal text-neutral-500">
                    (archived — not used by retrieval)
                  </span>
                )}
              </summary>
              <dl className="mt-2 grid grid-cols-1 gap-2 text-xs sm:grid-cols-3">
                {(
                  [
                    ["Outcome", describe(data.index as never)],
                    ["Industry", data.index.industry],
                    ["Job type", data.index.job_type],
                    ["Tools", data.index.tools],
                    ["Rate type", data.index.rate_type],
                    ["Budget band", data.index.budget_band],
                    [
                      "Quote",
                      data.index.quote_amount
                        ? `${data.index.quote_amount} (${data.index.quote_model})`
                        : null,
                    ],
                    ["Job title", data.index.job_title],
                    ["Skills", data.index.skills.join(", ") || null],
                  ] as [string, string | null][]
                ).map(([k, v]) => (
                  <div key={k}>
                    <dt className="text-neutral-500">{k}</dt>
                    <dd>{v ?? "—"}</dd>
                  </div>
                ))}
              </dl>
              {data.index.proposal_excerpt && (
                <div className="mt-2 text-xs">
                  <p className="text-neutral-500">
                    Excerpt of the copied cover letter (your words only)
                  </p>
                  <p className="mt-1 max-h-40 overflow-auto rounded bg-neutral-50 p-2 whitespace-pre-wrap dark:bg-neutral-900">
                    {data.index.proposal_excerpt}
                  </p>
                </div>
              )}
              <div className="mt-3 flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => void toggleArchive()}
                  disabled={busy}
                  className="rounded border border-neutral-300 px-3 py-1.5 text-xs disabled:opacity-50 dark:border-neutral-700"
                >
                  {data.index.archived
                    ? "Unarchive (use for learning again)"
                    : "Archive (exclude from learning)"}
                </button>
                <span className="text-xs text-neutral-500">
                  The outcome history above is never changed by this.
                </span>
              </div>
            </details>
          )}

          <p className="text-xs text-neutral-500">
            Outcomes that arrive for a job the app does not know are held in the{" "}
            <Link href="/settings/review-queue" className="underline">
              review queue
            </Link>
            .
          </p>
        </>
      )}
    </section>
  );
}
