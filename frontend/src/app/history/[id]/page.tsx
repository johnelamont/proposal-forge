import { Suspense } from "react";

import { EntryEditor } from "@/components/history/entry-editor";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Project — Proposal Forge" };

// `params` is request-time data: awaited inside the Suspense boundary.
async function EditorFromParams({
  params,
}: {
  params: PageProps<"/history/[id]">["params"];
}) {
  const { id } = await params;
  return <EntryEditor id={id} />;
}

export default function HistoryEntryPage({
  params,
}: PageProps<"/history/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <EditorFromParams params={params} />
        </RequireUser>
      </Suspense>
    </main>
  );
}
