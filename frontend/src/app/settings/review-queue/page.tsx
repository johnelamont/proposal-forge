import { Suspense } from "react";

import { ReviewQueue } from "@/components/outcomes/review-queue";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Review queue — Proposal Forge" };

export default function ReviewQueuePage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <ReviewQueue />
        </RequireUser>
      </Suspense>
    </main>
  );
}
