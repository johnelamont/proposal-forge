// Browser-side client for the FastAPI backend. Every call carries the user's
// Supabase access token; the backend verifies it and runs the request as that
// user, so Row Level Security applies.
import { createClient } from "@/lib/supabase/client";
import type { Decision, JobPost, JobPostSummary } from "@/lib/types/job";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function accessToken(): Promise<string> {
  const {
    data: { session },
  } = await createClient().auth.getSession();
  if (!session) {
    throw new ApiError(401, "You are signed out. Sign in and try again.");
  }
  return session.access_token;
}

async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  if (!API_URL) {
    throw new ApiError(
      0,
      "NEXT_PUBLIC_API_URL is not set. Copy frontend/.env.example to frontend/.env.local.",
    );
  }
  const token = await accessToken();
  let response: Response;
  try {
    response = await fetch(API_URL + path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, "Could not reach the backend. Is it running?");
  }
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // keep statusText
    }
    throw new ApiError(response.status, detail);
  }
  return (await response.json()) as T;
}

export const jobsApi = {
  parse: (raw_paste: string) =>
    apiFetch<JobPost>("/api/jobs/parse", {
      method: "POST",
      body: JSON.stringify({ raw_paste }),
    }),
  list: () => apiFetch<JobPostSummary[]>("/api/jobs"),
  get: (id: string) => apiFetch<JobPost>(`/api/jobs/${id}`),
  reread: (id: string) =>
    apiFetch<JobPost>(`/api/jobs/${id}/reread`, { method: "POST" }),
  setLink: (id: string, job_link: string) =>
    apiFetch<JobPost>(`/api/jobs/${id}/link`, {
      method: "PATCH",
      body: JSON.stringify({ job_link }),
    }),
  decide: (id: string, decision: Decision) =>
    apiFetch<JobPost>(`/api/jobs/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    }),
};
