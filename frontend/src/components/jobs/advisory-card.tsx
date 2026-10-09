import Link from "next/link";

import { LOW_CONFIDENCE, type Advisory, type Fit } from "@/lib/types/job";

import { Bullets, Card } from "./card";

const FIT_LABEL: Record<Fit, string> = {
  strong: "Strong fit",
  partial: "Partial fit",
  weak: "Weak fit",
  none: "Not a fit",
};
const FIT_STYLE: Record<Fit, string> = {
  strong: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  partial: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
  weak: "bg-neutral-200 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200",
  none: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
};

function Low({ value }: { value: number }) {
  if (value >= LOW_CONFIDENCE) return null;
  return (
    <span
      title={`Confidence ${Math.round(value * 100)}% — treat as a hunch`}
      className="ml-2 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] font-medium text-amber-800 uppercase dark:bg-amber-900 dark:text-amber-200"
    >
      low confidence
    </span>
  );
}

function Section({
  name,
  confidence,
  children,
}: {
  name: string;
  confidence?: number;
  children: React.ReactNode;
}) {
  return (
    <div>
      <h3 className="mb-1 text-xs text-neutral-500">
        {name}
        {confidence !== undefined && <Low value={confidence} />}
      </h3>
      {children}
    </div>
  );
}

export function AdvisoryCard({
  advisory,
  computedAt,
  busy,
  onRefresh,
}: {
  advisory: Advisory | null;
  computedAt: string | null;
  busy: boolean;
  onRefresh: () => void;
}) {
  const refresh = (
    <button
      type="button"
      onClick={onRefresh}
      disabled={busy}
      className="rounded border border-neutral-300 px-3 py-1 text-xs disabled:opacity-50 dark:border-neutral-700"
    >
      {busy ? "Working… (10–20 s)" : advisory ? "Refresh" : "Compare"}
    </button>
  );

  if (!advisory) {
    return (
      <Card title="Similar past work" aside={refresh}>
        <p className="text-sm text-neutral-500">
          {busy
            ? "Comparing this job with your work history…"
            : "Not compared yet."}
        </p>
      </Card>
    );
  }

  const { match_strength: ms, comparables, reading, failure } = advisory;

  return (
    <Card title="Similar past work" aside={refresh}>
      <div className="flex flex-col gap-4">
        <p className="text-sm font-medium">
          {ms.label}
          {ms.level === "none_history" && (
            <>
              {" "}
              <Link href="/history/new" className="font-normal underline">
                Add a project
              </Link>
            </>
          )}
          {ms.history_count > 0 && ms.level !== "none_history" && (
            <span className="ml-2 font-normal text-neutral-500">
              of {ms.history_count} in your history
            </span>
          )}
        </p>

        {comparables.length > 0 && (
          <ul className="divide-y divide-neutral-200 rounded border border-neutral-200 text-sm dark:divide-neutral-800 dark:border-neutral-800">
            {comparables.map((c) => (
              <li key={c.entry_id} className="flex flex-col gap-1 px-3 py-2">
                <span className="flex items-baseline justify-between gap-3">
                  <Link href={`/history/${c.entry_id}`} className="underline">
                    {c.name}
                  </Link>
                  <span className="shrink-0 text-xs text-neutral-500">
                    {[c.vertical, c.complexity].filter(Boolean).join(" · ")}
                  </span>
                </span>
                <span className="flex flex-wrap items-center gap-1 text-xs text-neutral-500">
                  {c.shared_tech.map((t) => (
                    <span
                      key={t}
                      className="rounded-full bg-neutral-100 px-2 py-0.5 text-neutral-800 dark:bg-neutral-800 dark:text-neutral-200"
                    >
                      {t}
                    </span>
                  ))}
                  {c.shared_terms.length > 0 && (
                    <span>shares: {c.shared_terms.join(", ")}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        )}

        {failure && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-300">
            No advisory available — {failure.message} The comparable projects
            above are still shown.
          </p>
        )}

        {reading && (
          <>
            <Section name="Verdict" confidence={reading.confidence.fit}>
              <span
                className={`inline-block rounded px-2 py-0.5 text-sm font-medium ${FIT_STYLE[reading.fit]}`}
              >
                {FIT_LABEL[reading.fit]}
              </span>
            </Section>
            <Section name="Why" confidence={reading.confidence.reasons}>
              <Bullets items={reading.reasons} />
            </Section>
            <Section
              name="Gaps — what the job needs that past work doesn't show"
              confidence={reading.confidence.gaps}
            >
              <Bullets items={reading.gaps} />
            </Section>
            {reading.cite.length > 0 && (
              <Section
                name="Worth citing in the proposal"
                confidence={reading.confidence.cite}
              >
                <ul className="space-y-1 text-sm">
                  {reading.cite.map((c) => (
                    <li key={c.entry_id}>
                      <Link
                        href={`/history/${c.entry_id}`}
                        className="font-medium underline"
                      >
                        {c.name}
                      </Link>
                      <span className="text-neutral-600 dark:text-neutral-400">
                        {" "}
                        — {c.why}
                      </span>
                    </li>
                  ))}
                </ul>
              </Section>
            )}
            <Section name="Angle" confidence={reading.confidence.angle}>
              <p className="text-sm">{reading.angle}</p>
            </Section>
          </>
        )}

        <p className="text-xs text-neutral-500">
          {advisory.outcomes_note}
          {computedAt && ` · Compared ${new Date(computedAt).toLocaleString()}`}
        </p>
      </div>
    </Card>
  );
}
