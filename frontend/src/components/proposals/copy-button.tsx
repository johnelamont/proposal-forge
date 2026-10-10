"use client";

// The Copy control that is also the approval (F3, R1/R2). The clipboard
// write happens first, inside the click; the approval is posted in the same
// handler. If logging fails the user is told and it keeps retrying — the
// copy already happened, so the record must catch up, never be dropped.

import { useState } from "react";

import { proposalsApi } from "@/lib/api";
import { APPROVAL_STATEMENT, sha256Hex } from "@/lib/copy";
import type { SectionName } from "@/lib/types/proposal";

export function CopyButton({
  proposalId,
  versionId,
  section,
  index,
  text,
  label = "Copy",
  onApproved,
}: {
  proposalId: string;
  versionId: string;
  section: SectionName;
  index: number | null;
  text: string;
  label?: string;
  onApproved: () => void;
}) {
  const [state, setState] = useState<
    "idle" | "copied" | "logging" | "unlogged"
  >("idle");
  const [attempt, setAttempt] = useState(0);

  async function log(hash: string, tries: number) {
    setState("logging");
    try {
      await proposalsApi.approve(proposalId, versionId, section, index, hash);
      setState("copied");
      onApproved();
      setTimeout(() => setState("idle"), 2500);
    } catch {
      setState("unlogged");
      setAttempt(tries);
      if (tries < 5) setTimeout(() => void log(hash, tries + 1), 1500 * tries);
    }
  }

  async function copy() {
    if (!text.trim()) return;
    await navigator.clipboard.writeText(text);
    const hash = await sha256Hex(text);
    void log(hash, 1);
  }

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={() => void copy()}
        disabled={!text.trim() || state === "logging"}
        className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        aria-label={`${label} — ${APPROVAL_STATEMENT}`}
      >
        {state === "copied"
          ? "Copied ✓"
          : state === "logging"
            ? "Logging…"
            : label}
      </button>
      <span className="max-w-[14rem] text-right text-[11px] leading-tight text-neutral-500">
        {APPROVAL_STATEMENT}
      </span>
      {state === "unlogged" && (
        <span
          role="alert"
          className="max-w-[14rem] rounded border border-red-300 bg-red-50 px-2 py-1 text-right text-[11px] text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          Copied, but the approval was not logged
          {attempt < 5 ? " — retrying…" : "."}{" "}
          {attempt >= 5 && (
            <button
              type="button"
              className="underline"
              onClick={() => void sha256Hex(text).then((h) => log(h, 1))}
            >
              Retry
            </button>
          )}
        </span>
      )}
    </div>
  );
}
