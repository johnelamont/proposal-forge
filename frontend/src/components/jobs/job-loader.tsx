"use client";

// Loads one job post by id (as the signed-in user) and hands it to the review.
import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError, jobsApi } from "@/lib/api";
import type { JobPost } from "@/lib/types/job";

import { JobReview } from "./job-review";

export function JobLoader({ id }: { id: string }) {
  const [job, setJob] = useState<JobPost | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    jobsApi
      .get(id)
      .then(setJob)
      .catch((e: unknown) =>
        setError(
          e instanceof ApiError && e.status === 404
            ? "No such job (or it isn't yours)."
            : e instanceof Error
              ? e.message
              : "Could not load this job.",
        ),
      );
  }, [id]);

  if (error) {
    return (
      <div className="flex flex-col gap-3">
        <p role="alert" className="text-sm text-red-700 dark:text-red-300">
          {error}
        </p>
        <Link href="/" className="text-sm underline">
          Home
        </Link>
      </div>
    );
  }
  if (!job) {
    return <p className="text-sm text-neutral-500">Loading…</p>;
  }
  return <JobReview initial={job} />;
}
