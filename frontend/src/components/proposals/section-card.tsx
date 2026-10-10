"use client";

// One draft section: the text, Edit (type over it), Refine (an instruction
// for Claude, this section only) and Copy (which is the approval).

import { useState } from "react";

import { LOW_CONFIDENCE } from "@/lib/types/job";

import { CopyButton } from "./copy-button";

export function SectionCard({
  title,
  text,
  confidence,
  warnings,
  proposalId,
  versionId,
  section,
  index,
  busy,
  onEdit,
  onRefine,
  onApproved,
}: {
  title: string;
  text: string;
  confidence?: number;
  warnings?: string[];
  proposalId: string;
  versionId: string;
  section: "cover_letter" | "answer";
  index: number | null;
  busy: boolean;
  onEdit: (content: string) => Promise<void>;
  onRefine: (instruction: string) => Promise<void>;
  onApproved: () => void;
}) {
  const [mode, setMode] = useState<"view" | "edit" | "refine">("view");
  const [draft, setDraft] = useState(text);
  const [instruction, setInstruction] = useState("");

  return (
    <section className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <header className="mb-2 flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold">
          {title}
          {confidence !== undefined && confidence < LOW_CONFIDENCE && (
            <span className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 uppercase dark:bg-amber-900 dark:text-amber-200">
              low confidence
            </span>
          )}
        </h3>
        <CopyButton
          proposalId={proposalId}
          versionId={versionId}
          section={section}
          index={index}
          text={text}
          onApproved={onApproved}
        />
      </header>

      {warnings && warnings.length > 0 && (
        <ul className="mb-2 space-y-1">
          {warnings.map((w) => (
            <li
              key={w}
              role="alert"
              className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100"
            >
              {w}
            </li>
          ))}
        </ul>
      )}

      {mode === "edit" ? (
        <div className="flex flex-col gap-2">
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={Math.max(6, draft.split("\n").length + 1)}
            className="w-full rounded border border-neutral-300 p-3 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy || draft === text}
              onClick={() => void onEdit(draft).then(() => setMode("view"))}
              className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
            >
              {busy ? "Saving…" : "Save as new version"}
            </button>
            <button
              type="button"
              onClick={() => {
                setDraft(text);
                setMode("view");
              }}
              className="text-xs underline"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : text ? (
        <pre className="font-sans text-sm whitespace-pre-wrap">{text}</pre>
      ) : (
        <p className="text-sm text-neutral-400">
          Empty — use Edit to write it, or draft again.
        </p>
      )}

      {mode === "refine" && (
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            void onRefine(instruction).then(() => {
              setInstruction("");
              setMode("view");
            });
          }}
        >
          <input
            autoFocus
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            placeholder="e.g. shorter; lead with the renewal automation"
            className="flex-1 rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
          />
          <button
            type="submit"
            disabled={busy || instruction.trim() === ""}
            className="rounded bg-neutral-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {busy ? "Refining… (10–20 s)" : "Refine"}
          </button>
          <button
            type="button"
            onClick={() => setMode("view")}
            className="text-xs underline"
          >
            Cancel
          </button>
        </form>
      )}

      {mode === "view" && (
        <div className="mt-3 flex gap-3 text-xs">
          <button
            type="button"
            onClick={() => {
              setDraft(text);
              setMode("edit");
            }}
            className="underline"
          >
            Edit
          </button>
          <button
            type="button"
            onClick={() => setMode("refine")}
            disabled={!text}
            className="underline disabled:no-underline disabled:opacity-50"
          >
            Refine with Claude
          </button>
        </div>
      )}
    </section>
  );
}
