"use client";

// F4: the quote with the evidence it rests on. The operator can overwrite the
// amount (a new version, marked as entered by them). Copy is the approval.

import { useState } from "react";

import type { Quote } from "@/lib/types/proposal";

import { CopyButton } from "./copy-button";

export function QuoteCard({
  quote,
  proposalId,
  versionId,
  busy,
  onEdit,
  onApproved,
}: {
  quote: Quote | null;
  proposalId: string;
  versionId: string;
  busy: boolean;
  onEdit: (amount: string | null, note: string) => Promise<void>;
  onApproved: () => void;
}) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(quote?.amount ?? "");
  const [note, setNote] = useState("");
  const unit = quote?.model === "hourly" ? "/hr" : "";

  return (
    <section className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <header className="mb-2 flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold">
          Quote
          {quote?.model && (
            <span className="ml-2 text-xs font-normal text-neutral-500">
              {quote.model === "hourly" ? "hourly" : "fixed price"}
            </span>
          )}
        </h3>
        <CopyButton
          proposalId={proposalId}
          versionId={versionId}
          section="quote"
          index={null}
          text={quote?.amount ?? ""}
          onApproved={onApproved}
        />
      </header>

      {quote?.amount ? (
        <p className="text-2xl font-semibold">
          ${quote.amount}
          <span className="text-base font-normal text-neutral-500">{unit}</span>
        </p>
      ) : (
        <p className="text-sm text-neutral-500">
          No amount proposed — enter it yourself.
        </p>
      )}
      {quote && (
        <p className="mt-1 text-sm text-neutral-700 dark:text-neutral-300">
          {quote.rationale}
        </p>
      )}
      {quote && quote.evidence.length > 0 && (
        <div className="mt-2">
          <p className="text-xs text-neutral-500">Based on</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-xs text-neutral-600 dark:text-neutral-400">
            {quote.evidence.map((e, i) => (
              <li key={i}>{e.detail}</li>
            ))}
          </ul>
        </div>
      )}

      {editing ? (
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end"
          onSubmit={(e) => {
            e.preventDefault();
            void onEdit(amount.trim() === "" ? null : amount.trim(), note).then(
              () => setEditing(false),
            );
          }}
        >
          <label className="flex flex-col gap-1 text-xs text-neutral-500">
            Amount (number only)
            <input
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
              className="rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
          </label>
          <label className="flex flex-1 flex-col gap-1 text-xs text-neutral-500">
            Why (optional)
            <input
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. agreed scope on a call"
              className="rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900"
            />
          </label>
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-neutral-900 px-3 py-2 text-xs font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
          >
            {busy ? "Saving…" : "Save as new version"}
          </button>
          <button
            type="button"
            onClick={() => setEditing(false)}
            className="text-xs underline"
          >
            Cancel
          </button>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => {
            setAmount(quote?.amount ?? "");
            setEditing(true);
          }}
          className="mt-3 text-xs underline"
        >
          Edit amount
        </button>
      )}
    </section>
  );
}
