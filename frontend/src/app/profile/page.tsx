import { Suspense } from "react";

import { ProfileForm } from "@/components/profile/profile-form";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Profile — Proposal Forge" };

export default function ProfilePage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <ProfileForm />
        </RequireUser>
      </Suspense>
    </main>
  );
}
