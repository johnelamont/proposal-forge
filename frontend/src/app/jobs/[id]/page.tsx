import { Suspense } from "react";

import { JobLoader } from "@/components/jobs/job-loader";
import { RequireUser } from "@/components/require-user";

export const metadata = { title: "Job — Proposal Forge" };

// `params` is request-time data, so it is awaited inside the Suspense
// boundary (cacheComponents), not in the page body.
async function JobFromParams({
  params,
}: {
  params: PageProps<"/jobs/[id]">["params"];
}) {
  const { id } = await params;
  return <JobLoader id={id} />;
}

export default function JobPage({ params }: PageProps<"/jobs/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-6 p-4 sm:p-8">
      <Suspense
        fallback={<p className="text-sm text-neutral-500">Checking session…</p>}
      >
        <RequireUser>
          <JobFromParams params={params} />
        </RequireUser>
      </Suspense>
    </main>
  );
}
