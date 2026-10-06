import { Suspense } from "react";

import { AuthStatus } from "@/components/auth-status";

export default function Home() {
  return (
    <main className="flex flex-1 flex-col items-center justify-center gap-8 p-8">
      <header className="text-center">
        <h1 className="text-3xl font-semibold tracking-tight">
          Proposal Forge
        </h1>
        <p className="mt-2 text-neutral-600 dark:text-neutral-400">
          Upwork proposal assistant. Nothing here yet beyond sign-in.
        </p>
      </header>

      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <AuthStatus />
      </Suspense>
    </main>
  );
}
