"use client";

// Seed of the dashboard pipeline: the user's recent pastes and their decisions.
import Link from "next/link";
import { useEffect, useState } from "react";

import { jobsApi } from "@/lib/api";
import type { JobPostSummary } from "@/lib/types/job";

export function RecentJobs() {
  const [jobs, setJobs] = useState<JobPostSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    jobsApi
      .list()
      .then(setJobs)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load jobs."),
      );
  }, []);

  return (
    <section className="w-full max-w-xl">
      <div className="mb-2 flex items-baseline justify-between">
        <h2 className="text-sm font-semibold tracking-wide text-neutral-500 uppercase">
          Recent jobs
        </h2>
        <Link
          href="/jobs/new"
          className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Paste a job
        </Link>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      {jobs === null && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}
      {jobs?.length === 0 && (
        <p className="text-sm text-neutral-500">
          Nothing yet. Paste your first job post.
        </p>
      )}
      {jobs && jobs.length > 0 && (
        <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
          {jobs.map((j) => (
            <li key={j.id}>
              <Link
                href={`/jobs/${j.id}`}
                className="flex items-center justify-between gap-3 px-3 py-2 hover:bg-neutral-50 dark:hover:bg-neutral-900"
              >
                <span className="truncate">{j.title ?? "Untitled"}</span>
                <span className="shrink-0 text-xs text-neutral-500">
                  {j.decision ?? "undecided"}
                  {j.parse_status !== "ok" && ` · ${j.parse_status}`}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
