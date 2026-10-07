import { LOW_CONFIDENCE, type JobAnalysis } from "@/lib/types/job";

import { Bullets, Card } from "./card";

function Low({ value }: { value: number }) {
  if (value >= LOW_CONFIDENCE) return null;
  return (
    <span
      title={`Confidence ${Math.round(value * 100)}% — check this against the description`}
      className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 uppercase dark:bg-amber-900 dark:text-amber-200"
    >
      low confidence
    </span>
  );
}

function Field({
  name,
  confidence,
  children,
}: {
  name: string;
  confidence: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="mb-1 text-xs text-neutral-500">
        {name}
        <Low value={confidence} />
      </h3>
      {children}
    </div>
  );
}

export function ReadingCard({
  analysis,
  busy,
  onRetry,
}: {
  analysis: JobAnalysis;
  busy: boolean;
  onRetry: () => void;
}) {
  const { ai, ai_failure } = analysis;

  if (!ai) {
    return (
      <Card title="Reading (Claude)">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            Not extracted — {ai_failure?.message ?? "no result"}.
            {ai_failure?.kind === "skipped"
              ? " The structured fields above are still usable."
              : " Everything else on this page is still usable."}
          </p>
          {ai_failure?.kind !== "skipped" && (
            <button
              type="button"
              onClick={onRetry}
              disabled={busy}
              className="rounded border border-neutral-300 px-3 py-1.5 text-sm disabled:opacity-50 dark:border-neutral-700"
            >
              {busy ? "Retrying…" : "Retry"}
            </button>
          )}
        </div>
      </Card>
    );
  }

  const c = ai.confidence;
  return (
    <Card
      title="Reading (Claude)"
      aside={
        <span className="text-xs text-neutral-500">
          From the description only
        </span>
      }
    >
      <div className="flex flex-col gap-4">
        <Field name="In one line" confidence={c.one_line}>
          <p className="text-sm font-medium">{ai.one_line}</p>
        </Field>

        {ai.sensitive_data_domain.flag && (
          <p className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-100">
            <strong>Sensitive-data domain.</strong>{" "}
            {ai.sensitive_data_domain.reason} Your own engagement checkpoint
            applies before taking this job.
            <Low value={c.sensitive_data_domain} />
          </p>
        )}

        <Field name="Deliverables" confidence={c.deliverables}>
          <Bullets items={ai.deliverables} />
        </Field>
        <Field name="Requirements" confidence={c.requirements}>
          <Bullets items={ai.requirements} />
        </Field>
        <Field name="Red flags" confidence={c.red_flags}>
          <Bullets items={ai.red_flags} />
        </Field>

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            name="Budget, in the client's words"
            confidence={c.budget_statement}
          >
            {ai.budget_statement ? (
              <div className="text-sm">
                <p>
                  {ai.budget_statement.model}
                  {ai.budget_statement.amount_raw &&
                    ` — ${ai.budget_statement.amount_raw}`}
                </p>
                {ai.budget_statement.milestones.length > 0 && (
                  <ol className="mt-1 list-decimal pl-5 text-neutral-600 dark:text-neutral-400">
                    {ai.budget_statement.milestones.map((m, i) => (
                      <li key={i}>{m}</li>
                    ))}
                  </ol>
                )}
              </div>
            ) : (
              <p className="text-sm text-neutral-400">Not stated</p>
            )}
          </Field>
          <Field
            name="Timeline, in the client's words"
            confidence={c.timeline_statement}
          >
            <p className="text-sm">
              {ai.timeline_statement ?? (
                <span className="text-neutral-400">Not stated</span>
              )}
            </p>
          </Field>
        </div>
      </div>
    </Card>
  );
}
