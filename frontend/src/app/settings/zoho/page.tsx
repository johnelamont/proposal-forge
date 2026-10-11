import { Suspense } from "react";

import { RequireUser } from "@/components/require-user";
import { ZohoSettings } from "@/components/zoho/zoho-settings";

export const metadata = { title: "Zoho — Proposal Forge" };

export default function ZohoSettingsPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <ZohoSettings />
        </RequireUser>
      </Suspense>
    </main>
  );
}
