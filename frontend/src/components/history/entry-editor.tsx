"use client";

// Edit or delete one work-history entry.

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ApiError, workHistoryApi } from "@/lib/api";
import type {
  WorkHistoryOut,
  WorkHistoryPatch,
} from "@/lib/types/work-history";

import { EntryForm, type FormValues } from "./entry-form";

const NULLABLE = [
  "vertical",
  "project_type",
  "complexity",
  "role",
  "client_name",
  "budget_band",
  "started",
  "ended",
] as const;

function toPatch(before: WorkHistoryOut, after: FormValues): WorkHistoryPatch {
  const patch: WorkHistoryPatch = {};
  const clear: string[] = [];
  if (after.name !== before.name) patch.name = after.name;
  if (after.summary !== before.summary) patch.summary = after.summary;
  if (after.tech_stack.join("\u0000") !== before.tech_stack.join("\u0000")) {
    patch.tech_stack = after.tech_stack;
  }
  if (after.outcomes.join("\u0000") !== before.outcomes.join("\u0000")) {
    patch.outcomes = after.outcomes;
  }
  if (after.may_name_client !== before.may_name_client) {
    patch.may_name_client = after.may_name_client;
  }
  for (const key of NULLABLE) {
    if (after[key] === before[key]) continue;
    if (after[key] === null) clear.push(key);
    else (patch as Record<string, unknown>)[key] = after[key];
  }
  if (clear.length) patch.clear = clear;
  return patch;
}

export function EntryEditor({ id }: { id: string }) {
  const router = useRouter();
  const [entry, setEntry] = useState<WorkHistoryOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    workHistoryApi
      .get(id)
      .then(setEntry)
      .catch((e: unknown) =>
        setError(
          e instanceof ApiError && e.status === 404
            ? "No such entry (or it isn't yours)."
            : e instanceof Error
              ? e.message
              : "Could not load.",
        ),
      );
  }, [id]);

  async function save(values: FormValues) {
    if (!entry) return;
    const patch = toPatch(entry, values);
    setError(null);
    setSaved(false);
    if (Object.keys(patch).length === 0) {
      setSaved(true);
      return;
    }
    setBusy(true);
    try {
      setEntry(await workHistoryApi.update(entry.id, patch));
      setSaved(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (
      !entry ||
      !window.confirm(`Delete "${entry.name}"? This cannot be undone.`)
    ) {
      return;
    }
    setBusy(true);
    try {
      await workHistoryApi.remove(entry.id);
      router.replace("/history");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
      setBusy(false);
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

  if (!entry) {
    return (
      <section className="flex flex-col gap-4">
        {nav}
        {error ? (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            {error}
          </p>
        ) : (
          <p className="text-sm text-neutral-500">Loading…</p>
        )}
      </section>
    );
  }

  return (
    <section className="flex flex-col gap-5 pb-8">
      {nav}
      <header className="flex items-baseline justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{entry.name}</h1>
        {saved && (
          <span className="text-xs text-green-700 dark:text-green-400">
            Saved
          </span>
        )}
      </header>
      {entry.source_files.length > 0 && (
        <p className="text-xs text-neutral-500">
          From: {entry.source_files.map((f) => f.name).join(", ")}
          {entry.ai_extraction &&
            " · extracted by Claude, then confirmed by you"}
        </p>
      )}
      <EntryForm
        key={entry.updated_at}
        initial={entry}
        extraction={null}
        submitLabel="Save changes"
        busy={busy}
        error={error}
        onSubmit={(values) => void save(values)}
        footer={
          <button
            type="button"
            onClick={() => void remove()}
            disabled={busy}
            className="text-sm text-red-700 underline dark:text-red-300"
          >
            Delete
          </button>
        }
      />
    </section>
  );
}
