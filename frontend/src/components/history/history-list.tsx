"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { workHistoryApi } from "@/lib/api";
import type { WorkHistorySummary } from "@/lib/types/work-history";

export function HistoryList() {
  const [entries, setEntries] = useState<WorkHistorySummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    workHistoryApi
      .list()
      .then(setEntries)
      .catch((e: unknown) =>
        setError(e instanceof Error ? e.message : "Could not load."),
      );
  }, []);

  return (
    <section className="flex flex-col gap-4">
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
      </nav>
      <div className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">Work history</h1>
        <Link
          href="/history/new"
          className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
        >
          Add a project
        </Link>
      </div>
      <p className="text-sm text-neutral-600 dark:text-neutral-400">
        Past projects, used to judge whether a new job is in your wheelhouse and
        to give proposals real examples. Client names stay private unless you
        say otherwise.
      </p>

      {error && (
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
      )}
      {entries === null && !error && (
        <p className="text-sm text-neutral-500">Loading…</p>
      )}
      {entries?.length === 0 && (
        <p className="text-sm text-neutral-500">
          Nothing yet. Add your first project — drop its README.
        </p>
      )}
      {entries && entries.length > 0 && (
        <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 dark:divide-neutral-800 dark:border-neutral-800">
          {entries.map((e) => (
            <li key={e.id}>
              <Link
                href={`/history/${e.id}`}
                className="flex flex-col gap-1 px-3 py-3 hover:bg-neutral-50 dark:hover:bg-neutral-900"
              >
                <span className="flex items-baseline justify-between gap-3">
                  <span className="truncate font-medium">{e.name}</span>
                  <span className="shrink-0 text-xs text-neutral-500">
                    {e.ended ?? "—"}
                  </span>
                </span>
                <span className="flex flex-wrap items-center gap-1.5 text-xs text-neutral-500">
                  {e.vertical && <span>{e.vertical}</span>}
                  {e.complexity && <span>· {e.complexity}</span>}
                  {e.may_name_client && (
                    <span className="rounded bg-neutral-100 px-1.5 py-0.5 dark:bg-neutral-800">
                      client may be named
                    </span>
                  )}
                  {e.tech_stack.slice(0, 5).map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-neutral-100 px-2 py-0.5 dark:bg-neutral-800"
                    >
                      {t}
                    </span>
                  ))}
                  {e.tech_stack.length > 5 && (
                    <span>+{e.tech_stack.length - 5}</span>
                  )}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
