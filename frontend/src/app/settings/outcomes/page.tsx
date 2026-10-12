import { Suspense } from "react";

import { OutcomeSettings } from "@/components/outcomes/outcome-settings";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Outcome webhook — Proposal Forge" };

export default function OutcomeSettingsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <OutcomeSettings />
        </RequireUser>
      </Suspense>
    </main>
  );
}
