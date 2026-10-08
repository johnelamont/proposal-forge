import { Suspense } from "react";

import { EntryEditor } from "@/components/history/entry-editor";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Project — Proposal Forge" };

// `params` and `searchParams` are request-time data: awaited inside the
// Suspense boundary.
async function EditorFromParams({
  params,
  searchParams,
}: {
  params: PageProps<"/history/[id]">["params"];
  searchParams: PageProps<"/history/[id]">["searchParams"];
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  return <EntryEditor id={id} justSaved={query.saved === "1"} />;
}

export default function HistoryEntryPage({
  params,
  searchParams,
}: PageProps<"/history/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <EditorFromParams params={params} searchParams={searchParams} />
        </RequireUser>
      </Suspense>
    </main>
  );
}
