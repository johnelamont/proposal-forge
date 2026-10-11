"use client";

// The Stage 1 review: shared by the paste flow (right after Parse) and the
// /jobs/[id] page (reopening a job later). Undecided jobs show the
// Continue / Abandon bar; decided jobs show the decision and stay readable.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { ApiError, jobsApi, proposalsApi } from "@/lib/api";
import type { Decision, JobPost } from "@/lib/types/job";
import type { ProposalOut } from "@/lib/types/proposal";

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

  // F3: the proposal for this job. A continued job may already have one
  // (drafted, edited, copied); reopening the job must show that, not a
  // "Draft proposal" button that reads as starting over. undefined = not
  // checked yet, null = none.
  const router = useRouter();
  const [existing, setExisting] = useState<ProposalOut | null | undefined>(
    undefined,
  );
  useEffect(() => {
    if (job.decision !== "continue") return;
    let cancelled = false;
    proposalsApi
      .forJob(job.id)
      .then((p) => {
        if (!cancelled) setExisting(p);
      })
      .catch(() => {
        if (!cancelled) setExisting(null); // the button still works
      });
    return () => {
      cancelled = true;
    };
  }, [job.id, job.decision]);

  const [opening, setOpening] = useState(false);
  const [profileNeeded, setProfileNeeded] = useState(false);
  async function draftProposal() {
    setError(null);
    setProfileNeeded(false);
    setOpening(true);
    try {
      const out = existing ?? (await proposalsApi.create(job.id));
      setExisting(out);
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
    } finally {
      // Also after a successful push: this component may stay mounted
      // behind the new route, and must not come back stuck on "Drafting".
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
            {job.decision !== "continue"
              ? "Recorded for your analytics. Nothing else happens with this job."
              : existing
                ? `Proposal ${existing.proposal.status} · ${existing.versions.length} version${existing.versions.length === 1 ? "" : "s"} · ${existing.approvals.length} cop${existing.approvals.length === 1 ? "y" : "ies"} logged.`
                : "Next: draft the proposal. Claude writes a first version from this review, your profile and your past work; you edit and copy what you approve."}
          </span>
          {job.decision === "continue" && (
            <span className="mt-3 block">
              {existing ? (
                <Link
                  href={`/proposals/${existing.proposal.id}`}
                  className="inline-block rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white dark:bg-neutral-100 dark:text-neutral-900"
                >
                  Open proposal
                </Link>
              ) : (
                <button
                  type="button"
                  disabled={opening || existing === undefined}
                  onClick={() => void draftProposal()}
                  className="rounded bg-neutral-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
                >
                  {opening
                    ? "Drafting… (20–40 s)"
                    : existing === undefined
                      ? "Checking…"
                      : "Draft proposal"}
                </button>
              )}
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
