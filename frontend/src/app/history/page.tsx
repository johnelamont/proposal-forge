import { Suspense } from "react";

import { HistoryList } from "@/components/history/history-list";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Work history — Proposal Forge" };

export default function HistoryPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <HistoryList />
        </RequireUser>
      </Suspense>
    </main>
  );
}
