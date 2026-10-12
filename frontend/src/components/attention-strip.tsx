"use client";

// Home → Attention: what needs the operator. Rendered only when non-empty.
// Leads whose last attempt failed, outcomes held in the review queue, and
// proposals still submitted past the nudge age (Profile → follow-up nudge).

import Link from "next/link";
import { useEffect, useState } from "react";

import { outcomesApi } from "@/lib/api";
import type { Attention } from "@/lib/types/outcomes";

function age(iso: string | null): string {
  if (!iso) return "";
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  return days === 1 ? "1 day" : `${days} days`;
}

export function AttentionStrip() {
  const [data, setData] = useState<Attention | null>(null);

  useEffect(() => {
    outcomesApi
      .attention()
      .then(setData)
      .catch(() => setData(null)); // the strip is advisory; a failure hides it
  }, []);

  if (!data) return null;
  const empty =
    data.lead_failed.length === 0 &&
    data.queued_outcomes === 0 &&
    data.stale_submitted.length === 0;
  if (empty) return null;

  return (
    <section
      aria-label="Needs attention"
      className="w-full max-w-xl rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
    >
      <h2 className="text-xs font-semibold tracking-wide uppercase">
        Needs you
      </h2>
      <ul className="mt-1 space-y-1">
        {data.lead_failed.map((p) => (
          <li key={`f-${p.proposal_id}`}>
            Lead not created for{" "}
            <Link href={`/proposals/${p.proposal_id}`} className="underline">
              {p.job_title ?? "a proposal"}
            </Link>{" "}
            — retry from its Submit panel.
          </li>
        ))}
        {data.queued_outcomes > 0 && (
          <li>
            {data.queued_outcomes === 1
              ? "1 outcome"
              : `${data.queued_outcomes} outcomes`}{" "}
            from Zoho could not be matched to a proposal —{" "}
            <Link href="/settings/review-queue" className="underline">
              review queue
            </Link>
            .
          </li>
        )}
        {data.stale_submitted.map((p) => (
          <li key={`s-${p.proposal_id}`}>
            <Link href={`/proposals/${p.proposal_id}`} className="underline">
              {p.job_title ?? "A proposal"}
            </Link>{" "}
            has been submitted {age(p.since)} with no outcome (nudge after{" "}
            {data.stale_after_days}). Follow up on Upwork?
          </li>
        ))}
      </ul>
    </section>
  );
}
