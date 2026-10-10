import { Suspense } from "react";

import { ProposalWorkspace } from "@/components/proposals/proposal-workspace";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Proposal — Proposal Forge" };

async function WorkspaceFromParams({
  params,
}: {
  params: PageProps<"/proposals/[id]">["params"];
}) {
  const { id } = await params;
  return <ProposalWorkspace id={id} />;
}

export default function ProposalPage({ params }: PageProps<"/proposals/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <WorkspaceFromParams params={params} />
        </RequireUser>
      </Suspense>
    </main>
  );
}
