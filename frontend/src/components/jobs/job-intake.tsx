"use client";

// Stage 1 (F1): paste → parse → review → Continue / Abandon.
// Nothing is treated as a parsed job until the operator decides; the row is
// created on Parse with decision = null so a Retry or a link fix can update it.

import Link from "next/link";
import { useState } from "react";

import { ApiError, jobsApi } from "@/lib/api";
import type { Decision, JobPost } from "@/lib/types/job";

import { ClientCard } from "./client-card";
import { DecideBar } from "./decide-bar";
import { JobCard } from "./job-card";
import { NeedsYou } from "./needs-you";
import { ReadingCard } from "./reading-card";

type Phase =
  | { kind: "paste" }
  | { kind: "parsing" }
  | { kind: "review"; job: JobPost }
  | { kind: "decided"; job: JobPost };

export function JobIntake() {
  const [raw, setRaw] = useState("");
  const [phase, setPhase] = useState<Phase>({ kind: "paste" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  function fail(e: unknown) {
    setError(e instanceof Error ? e.message : "Something went wrong.");
  }

  async function parse() {
    setError(null);
    setPhase({ kind: "parsing" });
    try {
      const job = await jobsApi.parse(raw);
      setPhase({ kind: "review", job });
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setError(e.message);
      } else {
        fail(e);
      }
      setPhase({ kind: "paste" });
    }
  }

  async function update(action: string, run: () => Promise<JobPost>) {
    setError(null);
    setBusy(action);
    try {
      const job = await run();
      setPhase({ kind: "review", job });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }

  async function decide(job: JobPost, decision: Decision) {
    setError(null);
    setBusy(decision);
    try {
      const updated = await jobsApi.decide(job.id, decision);
      setPhase({ kind: "decided", job: updated });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  }

  if (phase.kind === "paste" || phase.kind === "parsing") {
    const parsing = phase.kind === "parsing";
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
        {error && <ErrorLine>{error}</ErrorLine>}
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

  const { job } = phase;
  const a = job.analysis;

  if (phase.kind === "decided") {
    return (
      <section className="flex flex-col gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">
          {job.decision === "continue" ? "Continuing" : "Abandoned"}
        </h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          {job.decision === "continue"
            ? "Recorded. Drafting (Stage 2) is the next feature; this job is saved and will be waiting there."
            : "Recorded for your analytics. Nothing else happens with this job."}
        </p>
        <p className="text-sm">
          <span className="font-medium">
            {a.parsed.title ?? "Untitled job"}
          </span>
          {job.upwork_job_id && (
            <span className="text-neutral-500"> · {job.upwork_job_id}</span>
          )}
        </p>
        <div className="flex gap-3">
          <Link href="/jobs/new" className="text-sm underline">
            Paste another
          </Link>
          <Link href="/" className="text-sm underline">
            Home
          </Link>
        </div>
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-5 pb-24">
      <header>
        <p className="text-xs tracking-wide text-neutral-500 uppercase">
          Review · {a.parsed.source_format} paste
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {a.parsed.title ?? "Untitled job"}
        </h1>
      </header>

      {error && <ErrorLine>{error}</ErrorLine>}

      <NeedsYou
        job={job}
        busy={busy}
        onSetLink={(link) =>
          void update("link", () => jobsApi.setLink(job.id, link))
        }
      />

      <JobCard parsed={a.parsed} />

      <ReadingCard
        analysis={a}
        busy={busy === "reread"}
        onRetry={() => void update("reread", () => jobsApi.reread(job.id))}
      />

      <ClientCard client={a.parsed.client} activity={a.parsed.activity} />

      <DecideBar
        busy={busy}
        onContinue={() => void decide(job, "continue")}
        onAbandon={() => void decide(job, "abandon")}
      />
    </section>
  );
}

function ErrorLine({ children }: { children: React.ReactNode }) {
  return (
    <p
      role="alert"
      className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
    >
      {children}
    </p>
  );
}
