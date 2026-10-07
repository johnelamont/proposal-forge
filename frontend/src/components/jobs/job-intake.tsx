"use client";

// Stage 1 (F1): paste → parse → review. The row is created on Parse with
// decision = null; the review (JobReview) handles Retry, the job link, and
// Continue / Abandon, and the same review reopens later at /jobs/[id].

import Link from "next/link";
import { useState } from "react";

import { jobsApi } from "@/lib/api";
import type { JobPost } from "@/lib/types/job";

import { JobReview } from "./job-review";

export function JobIntake() {
  const [raw, setRaw] = useState("");
  const [parsing, setParsing] = useState(false);
  const [job, setJob] = useState<JobPost | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function parse() {
    setError(null);
    setParsing(true);
    try {
      setJob(await jobsApi.parse(raw));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setParsing(false);
    }
  }

  if (job) {
    return <JobReview initial={job} />;
  }

  return (
    <section className="flex flex-1 flex-col gap-4">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Paste a job</h1>
        <p className="mt-1 text-sm text-neutral-600 dark:text-neutral-400">
          On the Upwork job page, select all, copy, and paste here. Works from
          the mobile app or a desktop browser.
        </p>
      </header>
      <textarea
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        disabled={parsing}
        autoFocus
        placeholder="Paste the whole job page…"
        className="min-h-[40vh] flex-1 rounded border border-neutral-300 p-3 font-mono text-sm dark:border-neutral-700 dark:bg-neutral-900"
      />
      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}
      <div className="bg-background sticky bottom-0 flex items-center justify-between gap-3 py-3">
        <Link href="/" className="text-sm underline">
          Back
        </Link>
        <button
          type="button"
          onClick={() => void parse()}
          disabled={parsing || raw.trim().length < 20}
          className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {parsing ? "Parsing… (10–20 s)" : "Parse"}
        </button>
      </div>
    </section>
  );
}
