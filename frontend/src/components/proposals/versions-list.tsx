// The append-only history, made visible: every version with its source,
// and every approval (copy) against the version it approved.

import type { DraftVersion, ProposalApproval } from "@/lib/types/proposal";

const SOURCE_LABEL: Record<DraftVersion["source"], string> = {
  ai: "Claude draft",
  refine: "Refined by Claude",
  edit: "Edited by you",
  manual: "Written by you",
};

function approvalLabel(a: ProposalApproval) {
  if (a.section === "all") return "everything";
  if (a.section === "answer") return `answer ${(a.section_index ?? 0) + 1}`;
  return a.section.replace("_", " ");
}

export function VersionsList({
  versions,
  approvals,
  currentId,
}: {
  versions: DraftVersion[];
  approvals: ProposalApproval[];
  currentId: string | null;
}) {
  return (
    <section className="rounded-lg border border-neutral-200 p-4 dark:border-neutral-800">
      <h3 className="mb-2 text-sm font-semibold tracking-wide text-neutral-500 uppercase">
        Versions and approvals
      </h3>
      <p className="mb-3 text-xs text-neutral-500">
        Every draft, refine and edit is kept. Each Copy is recorded against the
        version it came from — that record is the approval log.
      </p>
      <ol className="space-y-2 text-sm">
        {[...versions].reverse().map((v) => {
          const mine = approvals.filter((a) => a.draft_version_id === v.id);
          return (
            <li
              key={v.id}
              className={`rounded border px-3 py-2 ${
                v.id === currentId
                  ? "border-neutral-900 dark:border-neutral-100"
                  : "border-neutral-200 dark:border-neutral-800"
              }`}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span>
                  <span className="font-medium">v{v.version}</span>{" "}
                  <span className="text-neutral-600 dark:text-neutral-400">
                    {SOURCE_LABEL[v.source]}
                  </span>
                  {v.id === currentId && (
                    <span className="ml-2 text-xs text-neutral-500">
                      current
                    </span>
                  )}
                  {v.ai_meta?.failure && (
                    <span className="ml-2 text-xs text-red-700 dark:text-red-300">
                      Claude failed: {v.ai_meta.failure.message}
                    </span>
                  )}
                </span>
                <span className="shrink-0 text-xs text-neutral-500">
                  {new Date(v.created_at).toLocaleString()}
                </span>
              </div>
              {mine.length > 0 && (
                <ul className="mt-1 space-y-0.5 text-xs text-green-800 dark:text-green-300">
                  {mine.map((a) => (
                    <li key={a.id}>
                      ✓ Copied {approvalLabel(a)} ·{" "}
                      {new Date(a.approved_at).toLocaleString()}
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
