import { Suspense } from "react";

import { PortfolioExport } from "@/components/portfolio/portfolio-export";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Portfolio — Proposal Forge" };

export default function PortfolioPage() {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <PortfolioExport />
        </RequireUser>
      </Suspense>
    </main>
  );
}
