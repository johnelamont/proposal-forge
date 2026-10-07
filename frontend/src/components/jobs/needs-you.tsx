"use client";

import { useState } from "react";

import type { JobPost } from "@/lib/types/job";

export function NeedsYou({
  job,
  busy,
  onSetLink,
}: {
  job: JobPost;
  busy: string | null;
  onSetLink: (link: string) => void;
}) {
  const [link, setLink] = useState("");
  const a = job.analysis;
  const missingLink = !job.upwork_job_id;
  const unparsed = a.parsed.unparsed_lines;
  const unrecognised = a.parse_status === "unrecognised";

  if (
    !missingLink &&
    a.conflicts.length === 0 &&
    unparsed.length === 0 &&
    !unrecognised
  ) {
    return null;
  }

  return (
    <section
      className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-sm dark:border-amber-800 dark:bg-amber-950"
      aria-label="Needs you"
    >
      <h2 className="mb-2 text-xs font-semibold tracking-wide text-amber-800 uppercase dark:text-amber-200">
        Needs you
      </h2>
      <div className="flex flex-col gap-3">
        {unrecognised && (
          <p role="alert">
            This doesn&apos;t look like an Upwork job post. Check what you
            pasted, or abandon it below.
          </p>
        )}

        {missingLink && (
          <form
            className="flex flex-col gap-2 sm:flex-row sm:items-end"
            onSubmit={(e) => {
              e.preventDefault();
              onSetLink(link);
            }}
          >
            <label className="flex flex-1 flex-col gap-1">
              <span>
                <strong>Job link missing.</strong> Mobile pastes don&apos;t
                include it; use the Upwork app&apos;s Share button and paste the
                URL. Needed before a Zoho Lead can be created.
              </span>
              <input
                value={link}
                onChange={(e) => setLink(e.target.value)}
                placeholder="https://www.upwork.com/jobs/~…"
                className="rounded border border-amber-300 bg-white px-3 py-2 dark:border-amber-700 dark:bg-neutral-900"
              />
            </label>
            <button
              type="submit"
              disabled={busy !== null || link.trim() === ""}
              className="rounded bg-amber-800 px-4 py-2 font-medium text-white disabled:opacity-50"
            >
              {busy === "link" ? "Saving…" : "Save link"}
            </button>
          </form>
        )}

        {a.conflicts.map((c) => (
          <p key={c.field}>
            <strong>
              Upwork and the client disagree on {c.field.replace("_", " ")}.
            </strong>{" "}
            Upwork says <em>{c.upwork_value ?? "—"}</em>; the description says{" "}
            <em>{c.description_value ?? "—"}</em>. Neither was chosen for you.
          </p>
        ))}

        {unparsed.length > 0 && (
          <details>
            <summary className="cursor-pointer">
              Didn&apos;t understand {unparsed.length}{" "}
              {unparsed.length === 1 ? "line" : "lines"} of the paste
            </summary>
            <pre className="mt-2 font-mono text-xs whitespace-pre-wrap">
              {unparsed.join("\n")}
            </pre>
          </details>
        )}
      </div>
    </section>
  );
}
