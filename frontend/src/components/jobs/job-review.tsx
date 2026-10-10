"use client";

// The Stage 1 review: shared by the paste flow (right after Parse) and the
// /jobs/[id] page (reopening a job later). Undecided jobs show the
// Continue / Abandon bar; decided jobs show the decision and stay readable.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, jobsApi, proposalsApi } from "@/lib/api";
import type { Decision, JobPost } from "@/lib/types/job";

import { AdvisoryCard } from "./advisory-card";
import { ClientCard } from "./client-card";
import { DecideBar } from "./decide-bar";
import { JobCard } from "./job-card";
import { NeedsYou } from "./needs-you";
import { ReadingCard } from "./reading-card";

export function JobReview({ initial }: { initial: JobPost }) {
  const [job, setJob] = useState<JobPost>(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const a = job.analysis;
  const decided = job.decision !== null;

  async function run(action: string, call: () => Promise<JobPost>) {
    setError(null);
    setBusy(action);
    try {
      setJob(await call());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(null);
    }
  }

  const decide = (d: Decision) => void run(d, () => jobsApi.decide(job.id, d));

  // F3: open (or create, drafting version 1) the proposal for this job.
  const router = useRouter();
  const [opening, setOpening] = useState(false);
  const [profileNeeded, setProfileNeeded] = useState(false);
  async function openProposal() {
    setError(null);
    setProfileNeeded(false);
    setOpening(true);
    try {
      const existing = await proposalsApi.forJob(job.id);
      const out = existing ?? (await proposalsApi.create(job.id));
      router.push(`/proposals/${out.proposal.id}`);
    } catch (e) {
      if (
        e instanceof ApiError &&
        e.status === 409 &&
        /profile/i.test(e.message)
      ) {
        setProfileNeeded(true);
      } else {
        setError(e instanceof Error ? e.message : "Something went wrong.");
      }
      setOpening(false);
    }
  }

  // F2: the advisory has its own busy flag so Continue / Abandon are never
  // blocked by it (advisory to the operator only). It runs once automatically
  // the first time a job is reviewed; the backend makes no Claude call when
  // there is no work history, so that first run is free in that case.
  const [comparing, setComparing] = useState(false);
  async function compare() {
    setComparing(true);
    try {
      setJob(await jobsApi.advisory(job.id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setComparing(false);
    }
  }
  const comparedOnce = useRef(false);
  useEffect(() => {
    if (job.advisory === null && !comparedOnce.current) {
      comparedOnce.current = true;
      void compare();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [job.id]);

  return (
    <section className={`flex flex-col gap-5 ${decided ? "" : "pb-24"}`}>
      <nav className="flex gap-4 text-sm">
        <Link href="/" className="underline">
          Home
        </Link>
        <Link href="/jobs/new" className="underline">
          Paste another
        </Link>
      </nav>

      <header>
        <p className="text-xs tracking-wide text-neutral-500 uppercase">
          {decided ? "Reviewed" : "Review"} · {a.parsed.source_format} paste
        </p>
        <h1 className="text-2xl font-semibold tracking-tight">
          {a.parsed.title ?? "Untitled job"}
        </h1>
      </header>

      {decided && (
        <p className="rounded-lg border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm dark:border-neutral-800 dark:bg-neutral-900">
          <strong>
            {job.decision === "continue" ? "Continuing" : "Abandoned"}
          </strong>
          {job.decided_at && (
            <span className="text-neutral-500">
              {" "}
              · {new Date(job.decided_at).toLocaleString()}
            </span>
          )}
          <br />
          <span className="text-neutral-600 dark:text-neutral-400">
            {job.decision === "continue"
              ? "Next: draft the proposal. Claude writes a first version from this review, your profile and your past work; you edit and copy what you approve."
              : "Recorded for your analytics. Nothing else happens with this job."}
          </span>
          {job.decision === "continue" && (
            <span className="mt-3 block">
              <button
                type="button"
                disabled={opening}
                onClick={() => void openProposal()}
                className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
              >
                {opening ? "Drafting… (20–40 s)" : "Draft proposal"}
              </button>
            </span>
          )}
        </p>
      )}

      {profileNeeded && (
        <p
          role="alert"
          className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
        >
          Drafting needs your profile first (your name and a positioning
          paragraph).{" "}
          <Link href="/profile" className="underline">
            Set up your profile
          </Link>
          , then come back here.
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}

      <NeedsYou
        job={job}
        busy={busy}
        onSetLink={(link) =>
          void run("link", () => jobsApi.setLink(job.id, link))
        }
      />

      <JobCard parsed={a.parsed} />

      <ReadingCard
        analysis={a}
        busy={busy === "reread"}
        onRetry={() => void run("reread", () => jobsApi.reread(job.id))}
      />

      <AdvisoryCard
        advisory={job.advisory}
        computedAt={job.advisory_at}
        busy={comparing}
        onRefresh={() => void compare()}
      />

      <ClientCard client={a.parsed.client} activity={a.parsed.activity} />

      {!decided && (
        <DecideBar
          busy={busy}
          onContinue={() => decide("continue")}
          onAbandon={() => decide("abandon")}
        />
      )}
    </section>
  );
}
