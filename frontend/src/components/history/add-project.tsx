"use client";

// F5 add flow: choose source → drop files → Extract → edit → Save.
// Extract returns a draft and writes nothing; Save is the explicit step.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { workHistoryApi } from "@/lib/api";
import type { AiFailure } from "@/lib/types/job";
import type {
  AcceptedFile,
  Extraction,
  RefusedFile,
} from "@/lib/types/work-history";

import {
  EMPTY,
  EntryForm,
  fromExtraction,
  type FormValues,
} from "./entry-form";
import { FileDrop, type Screened } from "./file-drop";

type Phase =
  | { kind: "choose" }
  | { kind: "files" }
  | { kind: "extracting" }
  | {
      kind: "form";
      extraction: Extraction | null;
      failure: AiFailure | null;
      accepted: AcceptedFile[];
      refused: RefusedFile[];
    };

export function AddProject() {
  const router = useRouter();
  const [phase, setPhase] = useState<Phase>({ kind: "choose" });
  const [files, setFiles] = useState<Screened>({ accepted: [], refused: [] });
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function extract() {
    setError(null);
    setPhase({ kind: "extracting" });
    try {
      const res = await workHistoryApi.extract(files.accepted);
      setPhase({
        kind: "form",
        extraction: res.extraction,
        failure: res.failure,
        accepted: res.accepted,
        refused: res.refused,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setPhase({ kind: "files" });
    }
  }

  async function save(values: FormValues, withFiles: boolean) {
    setError(null);
    setSaving(true);
    try {
      const extraction = phase.kind === "form" ? phase.extraction : null;
      const accepted = phase.kind === "form" ? phase.accepted : [];
      const entry = await workHistoryApi.create({
        ...values,
        // Only files the server accepted are stored with the record.
        source_files: withFiles
          ? files.accepted.filter((f) =>
              accepted.some((a) => a.name === f.name),
            )
          : [],
        ai_extraction: extraction,
      });
      // The router keeps this page mounted (hidden) after navigating away, so
      // reset it now or the next "Add a project" would show this form again.
      setPhase({ kind: "choose" });
      setFiles({ accepted: [], refused: [] });
      setSaving(false);
      router.replace(`/history/${entry.id}?saved=1`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setSaving(false);
    }
  }

  const nav = (
    <nav className="flex gap-4 text-sm">
      <Link href="/history" className="underline">
        Work history
      </Link>
      <Link href="/" className="underline">
        Home
      </Link>
    </nav>
  );

  if (phase.kind === "choose") {
    return (
      <section className="flex flex-col gap-5">
        {nav}
        <h1 className="text-2xl font-semibold tracking-tight">Add a project</h1>
        <div className="grid gap-3 sm:grid-cols-2">
          <button
            type="button"
            onClick={() => setPhase({ kind: "files" })}
            className="rounded-lg border border-neutral-300 p-5 text-left hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            <span className="block font-medium">Drop files</span>
            <span className="block text-sm text-neutral-500">
              Usually the README. Claude drafts the entry; you confirm it.
            </span>
          </button>
          <button
            type="button"
            onClick={() =>
              setPhase({
                kind: "form",
                extraction: null,
                failure: null,
                accepted: [],
                refused: [],
              })
            }
            className="rounded-lg border border-neutral-300 p-5 text-left hover:bg-neutral-50 dark:border-neutral-700 dark:hover:bg-neutral-900"
          >
            <span className="block font-medium">Enter manually</span>
            <span className="block text-sm text-neutral-500">
              A blank form. No AI involved.
            </span>
          </button>
        </div>
      </section>
    );
  }

  if (phase.kind === "files" || phase.kind === "extracting") {
    const extracting = phase.kind === "extracting";
    return (
      <section className="flex flex-col gap-5">
        {nav}
        <h1 className="text-2xl font-semibold tracking-tight">Add a project</h1>
        <FileDrop value={files} onChange={setFiles} disabled={extracting} />
        {error && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        )}
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => setPhase({ kind: "choose" })}
            className="text-sm underline"
          >
            Back
          </button>
          <button
            type="button"
            onClick={() => void extract()}
            disabled={extracting || files.accepted.length === 0}
            className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {extracting
              ? "Extracting… (10–20 s)"
              : `Extract from ${files.accepted.length} file${files.accepted.length === 1 ? "" : "s"}`}
          </button>
        </div>
      </section>
    );
  }

  const { extraction, failure, accepted, refused } = phase;
  const manual = accepted.length === 0 && failure === null;

  return (
    <section className="flex flex-col gap-5 pb-8">
      {nav}
      <h1 className="text-2xl font-semibold tracking-tight">
        {manual ? "New project" : "Confirm the entry"}
      </h1>

      {failure && (
        <div className="flex flex-col gap-2 rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between dark:border-red-800 dark:bg-red-950 dark:text-red-300">
          <p role="alert">
            Not extracted — {failure.message} The form is blank; fill it in by
            hand or retry.
          </p>
          {failure.kind !== "skipped" && (
            <button
              type="button"
              onClick={() => setPhase({ kind: "files" })}
              className="rounded border border-red-300 px-3 py-1.5 dark:border-red-700"
            >
              Back to files
            </button>
          )}
        </div>
      )}

      {(accepted.length > 0 || refused.length > 0) && (
        <p className="text-xs text-neutral-500">
          Sent to Claude: {accepted.map((a) => a.name).join(", ") || "nothing"}
          {refused.length > 0 &&
            ` · refused: ${refused.map((r) => `${r.name} (${r.reason})`).join(", ")}`}
        </p>
      )}

      <EntryForm
        initial={extraction ? fromExtraction(extraction) : EMPTY}
        extraction={extraction}
        submitLabel="Save to work history"
        busy={saving}
        error={error}
        onSubmit={(values) => void save(values, accepted.length > 0)}
        footer={
          <button
            type="button"
            onClick={() => setPhase({ kind: "choose" })}
            className="text-sm underline"
          >
            Start over
          </button>
        }
      />
    </section>
  );
}
