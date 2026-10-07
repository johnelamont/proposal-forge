import { label, proposals, rateRange } from "@/lib/format";
import type { ParsedJob } from "@/lib/types/job";

import { Card, Facts } from "./card";

export function JobCard({ parsed }: { parsed: ParsedJob }) {
  const e = parsed.engagement;
  return (
    <Card title="Job">
      <Facts
        items={[
          ["Payment", label.payment(e.payment_type)],
          ["Rate / budget", rateRange(e)],
          ["Hours", label.hours(e.hours_per_week)],
          ["Duration", label.duration(e.duration) ?? e.duration_raw],
          ["Level", label.level(e.experience_level)],
          ["Project type", label.projectType(e.project_type)],
          ["Contract-to-hire", e.contract_to_hire ? "Yes" : "No"],
          ["Location", parsed.location_restriction],
          ["Posted", parsed.posted_ago_raw],
          [
            "Connects",
            parsed.connects.required === null
              ? null
              : `${parsed.connects.required} (you have ${parsed.connects.available ?? "?"})`,
          ],
          [
            "Proposals",
            proposals(
              parsed.activity.proposals_min,
              parsed.activity.proposals_max,
            ),
          ],
        ]}
      />
      {parsed.skills.length > 0 && (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {parsed.skills.map((s) => (
            <li
              key={s}
              className="rounded-full bg-neutral-100 px-2.5 py-0.5 text-xs dark:bg-neutral-800"
            >
              {s}
            </li>
          ))}
        </ul>
      )}
      {Object.keys(parsed.preferred_qualifications).length > 0 && (
        <p className="mt-3 text-xs text-neutral-500">
          Preferred:{" "}
          {Object.entries(parsed.preferred_qualifications)
            .map(([k, v]) => `${k} ${v}`)
            .join(" · ")}
        </p>
      )}
      {parsed.questions.length > 0 && (
        <div className="mt-3">
          <p className="text-xs text-neutral-500">
            Screening questions ({parsed.questions.length})
          </p>
          <ol className="mt-1 list-decimal space-y-1 pl-5 text-sm">
            {parsed.questions.map((q, i) => (
              <li key={i}>
                {q.text}
                {q.source === "description" && (
                  <span className="ml-1 text-xs text-neutral-500">
                    (from the description)
                  </span>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
      <details className="mt-3">
        <summary className="cursor-pointer text-xs text-neutral-500">
          Description as pasted
        </summary>
        <pre className="mt-2 font-sans text-sm whitespace-pre-wrap">
          {parsed.description}
        </pre>
      </details>
    </Card>
  );
}
