import { Suspense } from "react";

import { AddProject } from "@/components/history/add-project";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Add a project — Proposal Forge" };

export default function NewHistoryPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <AddProject />
        </RequireUser>
      </Suspense>
    </main>
  );
}
