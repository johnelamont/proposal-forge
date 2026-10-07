import { Suspense } from "react";

import { JobIntake } from "@/components/jobs/job-intake";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Paste a job — Proposal Forge" };

export default function NewJobPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <JobIntake />
        </RequireUser>
      </Suspense>
    </main>
  );
}
