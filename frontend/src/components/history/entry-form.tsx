"use client";

// The editable work-history record. Prefilled from an extraction (with
// low-confidence markers) or empty for manual entry. Submitting is the
// operator's affirmative step; nothing is saved before it.

import { useState } from "react";

import { PROJECT_TYPES, ROLES, VERTICALS } from "@/lib/options";
import { LOW_CONFIDENCE } from "@/lib/types/job";
import type {
  Complexity,
  Extraction,
  WorkHistoryIn,
} from "@/lib/types/work-history";

export type FormValues = Omit<WorkHistoryIn, "source_files" | "ai_extraction">;

export const EMPTY: FormValues = {
  name: "",
  summary: "",
  tech_stack: [],
  vertical: null,
  project_type: null,
  complexity: null,
  role: null,
  outcomes: [],
  client_name: null,
  may_name_client: false,
  budget_band: null,
  started: null,
  ended: null,
};

export function fromExtraction(e: Extraction): FormValues {
  return {
    ...EMPTY,
    name: e.name,
    summary: e.summary,
    tech_stack: e.tech_stack,
    vertical: e.vertical,
    project_type: e.project_type,
    complexity: e.complexity,
    role: e.role,
    outcomes: e.outcomes,
    client_name: e.client_name_detected,
    // may_name_client stays false: detection is information, not permission.
  };
}

const INPUT =
  "w-full rounded border border-neutral-300 px-3 py-2 text-sm dark:border-neutral-700 dark:bg-neutral-900";

function Low({ value }: { value: number | undefined }) {
  if (value === undefined || value >= LOW_CONFIDENCE) return null;
  return (
    <span
      title={`Confidence ${Math.round(value * 100)}% — check against the files`}
      className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 uppercase dark:bg-amber-900 dark:text-amber-200"
    >
      low confidence
    </span>
  );
}

function Field({
  label,
  confidence,
  hint,
  children,
}: {
  label: string;
  confidence?: number;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs text-neutral-500">
        {label}
        <Low value={confidence} />
      </span>
      {children}
      {hint && <span className="text-xs text-neutral-500">{hint}</span>}
    </label>
  );
}

const orNull = (s: string) => (s.trim() === "" ? null : s.trim());

export function EntryForm({
  initial,
  extraction,
  submitLabel,
  busy,
  error,
  notice,
  onSubmit,
  footer,
}: {
  initial: FormValues;
  extraction?: Extraction | null;
  submitLabel: string;
  busy: boolean;
  error: string | null;
  /** Result of the last submit, shown beside the button where the eye is. */
  notice?: string | null;
  onSubmit: (values: FormValues) => void;
  footer?: React.ReactNode;
}) {
  const [v, setV] = useState<FormValues>(initial);
  const [techText, setTechText] = useState(initial.tech_stack.join(", "));
  const [outcomesText, setOutcomesText] = useState(initial.outcomes.join("\n"));
  const c = extraction?.confidence;
  const set = <K extends keyof FormValues>(k: K, val: FormValues[K]) =>
    setV((prev) => ({ ...prev, [k]: val }));

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        // Text is kept verbatim while typing (trimming on each keystroke
        // made spaces impossible); normalise once, here.
        onSubmit({
          ...v,
          name: v.name.trim(),
          vertical: orNull(v.vertical ?? ""),
          project_type: orNull(v.project_type ?? ""),
          role: orNull(v.role ?? ""),
          budget_band: orNull(v.budget_band ?? ""),
          client_name: orNull(v.client_name ?? ""),
          tech_stack: techText
            .split(/[,\n]/)
            .map((s) => s.trim())
            .filter(Boolean),
          outcomes: outcomesText
            .split("\n")
            .map((s) => s.trim())
            .filter(Boolean),
        });
      }}
    >
      <Field label="Project name" confidence={c?.name}>
        <input
          required
          maxLength={200}
          value={v.name}
          onChange={(e) => set("name", e.target.value)}
          className={INPUT}
        />
      </Field>

      <Field label="Summary" confidence={c?.summary}>
        <textarea
          rows={5}
          maxLength={4000}
          value={v.summary}
          onChange={(e) => set("summary", e.target.value)}
          className={INPUT}
        />
      </Field>

      <Field
        label="Tech stack"
        confidence={c?.tech_stack}
        hint="Comma-separated."
      >
        <input
          value={techText}
          onChange={(e) => setTechText(e.target.value)}
          className={INPUT}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="Vertical / industry"
          confidence={c?.vertical}
          hint="Pick one or type your own."
        >
          <input
            list="vertical-options"
            value={v.vertical ?? ""}
            onChange={(e) => set("vertical", e.target.value)}
            className={INPUT}
          />
          <datalist id="vertical-options">
            {VERTICALS.map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
        </Field>
        <Field
          label="Project type"
          confidence={c?.project_type}
          hint="Pick one or type your own."
        >
          <input
            list="project-type-options"
            value={v.project_type ?? ""}
            onChange={(e) => set("project_type", e.target.value)}
            className={INPUT}
          />
          <datalist id="project-type-options">
            {PROJECT_TYPES.map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
        </Field>
        <Field
          label="Complexity"
          confidence={c?.complexity}
          hint={extraction?.complexity_reason}
        >
          <select
            value={v.complexity ?? ""}
            onChange={(e) =>
              set("complexity", (e.target.value || null) as Complexity | null)
            }
            className={INPUT}
          >
            <option value="">—</option>
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
          </select>
        </Field>
        <Field
          label="Your role"
          confidence={c?.role}
          hint="Pick one or type your own, e.g. “Consultant, developer”."
        >
          <input
            list="role-options"
            value={v.role ?? ""}
            onChange={(e) => set("role", e.target.value)}
            className={INPUT}
          />
          <datalist id="role-options">
            {ROLES.map((o) => (
              <option key={o} value={o} />
            ))}
          </datalist>
        </Field>
      </div>

      <Field
        label="Outcomes"
        confidence={c?.outcomes}
        hint="One per line. Only what actually happened."
      >
        <textarea
          rows={4}
          value={outcomesText}
          onChange={(e) => setOutcomesText(e.target.value)}
          className={INPUT}
        />
      </Field>

      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Budget band" hint="e.g. $1–5K, $5–10K">
          <input
            value={v.budget_band ?? ""}
            onChange={(e) => set("budget_band", e.target.value)}
            className={INPUT}
          />
        </Field>
        <Field label="Started">
          <input
            type="month"
            value={v.started ?? ""}
            onChange={(e) => set("started", orNull(e.target.value))}
            className={INPUT}
          />
        </Field>
        <Field
          label="Ended"
          hint={extraction?.duration_hint ?? undefined}
          confidence={extraction?.duration_hint ? c?.duration_hint : undefined}
        >
          <input
            type="month"
            value={v.ended ?? ""}
            onChange={(e) => set("ended", orNull(e.target.value))}
            className={INPUT}
          />
        </Field>
      </div>

      <fieldset className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
        <legend className="px-1 text-xs text-neutral-500">Client</legend>
        <div className="flex flex-col gap-3">
          <Field
            label="Client name"
            confidence={
              extraction?.client_name_detected
                ? c?.client_name_detected
                : undefined
            }
            hint={
              extraction?.client_name_detected
                ? `Found in the files: "${extraction.client_name_detected}". Kept private unless you allow naming below.`
                : "Kept private unless you allow naming below."
            }
          >
            <input
              value={v.client_name ?? ""}
              onChange={(e) => set("client_name", e.target.value)}
              className={INPUT}
            />
          </Field>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={v.may_name_client}
              onChange={(e) => set("may_name_client", e.target.checked)}
              className="mt-1"
            />
            <span>
              This client may be named in the portfolio export.
              <span className="block text-xs text-neutral-500">
                Off by default. The name is never sent to Claude when drafting
                proposals.
              </span>
            </span>
          </label>
        </div>
      </fieldset>

      {error && (
        <p
          role="alert"
          className="rounded border border-red-300 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300"
        >
          {error}
        </p>
      )}
      {notice && !error && (
        <p
          role="status"
          className="rounded border border-green-300 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-800 dark:bg-green-950 dark:text-green-200"
        >
          {notice}
        </p>
      )}

      <div className="flex items-center justify-between gap-3">
        <div>{footer}</div>
        <button
          type="submit"
          disabled={busy || v.name.trim() === ""}
          className="rounded bg-neutral-900 px-5 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-neutral-100 dark:text-neutral-900"
        >
          {busy ? "Saving…" : submitLabel}
        </button>
      </div>
    </form>
  );
}
