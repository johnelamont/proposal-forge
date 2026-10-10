// Browser-side client for the FastAPI backend. Every call carries the user's
// Supabase access token; the backend verifies it and runs the request as that
// user, so Row Level Security applies.
import { createClient } from "@/lib/supabase/client";
import type { Decision, JobPost, JobPostSummary } from "@/lib/types/job";
import type {
  CopyText,
  Profile,
  ProfileIn,
  ProposalOut,
  SectionName,
} from "@/lib/types/proposal";
import type {
  DroppedFile,
  ExtractResponse,
  WorkHistoryIn,
  WorkHistoryOut,
  WorkHistoryPatch,
  WorkHistorySummary,
} from "@/lib/types/work-history";

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
  /** Compute (or refresh) the wheelhouse advisory. Stored on the job. */
  advisory: (id: string) =>
    apiFetch<JobPost>(`/api/jobs/${id}/advisory`, { method: "POST" }),
};

export const profileApi = {
  get: () => apiFetch<Profile | null>("/api/profile"),
  put: (profile: ProfileIn) =>
    apiFetch<Profile>("/api/profile", {
      method: "PUT",
      body: JSON.stringify(profile),
    }),
};

export const proposalsApi = {
  /** Creates the proposal for a job (or returns the existing one) with draft v1. */
  create: (job_post_id: string, form_paste?: string) =>
    apiFetch<ProposalOut>("/api/proposals", {
      method: "POST",
      body: JSON.stringify({ job_post_id, form_paste: form_paste ?? null }),
    }),
  get: (id: string) => apiFetch<ProposalOut>(`/api/proposals/${id}`),
  forJob: (jobId: string) =>
    apiFetch<ProposalOut | null>(`/api/proposals/by-job/${jobId}`),
  redraft: (id: string) =>
    apiFetch<ProposalOut>(`/api/proposals/${id}/draft`, { method: "POST" }),
  addQuestions: (id: string, form_paste: string) =>
    apiFetch<ProposalOut>(`/api/proposals/${id}/questions`, {
      method: "POST",
      body: JSON.stringify({ form_paste }),
    }),
  refine: (
    id: string,
    section: "cover_letter" | "answer",
    index: number | null,
    instruction: string,
  ) =>
    apiFetch<ProposalOut>(`/api/proposals/${id}/refine`, {
      method: "POST",
      body: JSON.stringify({ section, index, instruction }),
    }),
  edit: (
    id: string,
    section: "cover_letter" | "answer" | "quote",
    index: number | null,
    content: string,
    quote_amount?: string | null,
  ) =>
    apiFetch<ProposalOut>(`/api/proposals/${id}/edit`, {
      method: "POST",
      body: JSON.stringify({ section, index, content, quote_amount }),
    }),
  /** The exact text (and its hash) for a section of a version. */
  copyText: (
    id: string,
    versionId: string,
    section: SectionName,
    index: number | null,
  ) => {
    const q = new URLSearchParams({ section, version_id: versionId });
    if (index !== null) q.set("index", String(index));
    return apiFetch<CopyText>(`/api/proposals/${id}/copy-text?${q}`);
  },
  /** Records a copy as approval; the server checks the hash. */
  approve: (
    id: string,
    versionId: string,
    section: SectionName,
    index: number | null,
    content_hash: string,
  ) =>
    apiFetch<unknown>(`/api/proposals/${id}/approvals`, {
      method: "POST",
      body: JSON.stringify({
        draft_version_id: versionId,
        section,
        section_index: index,
        content_hash,
      }),
    }),
};

export const workHistoryApi = {
  /** Screens the files and asks Claude for a draft. Writes nothing. */
  extract: (files: DroppedFile[]) =>
    apiFetch<ExtractResponse>("/api/work-history/extract", {
      method: "POST",
      body: JSON.stringify({ files }),
    }),
  list: () => apiFetch<WorkHistorySummary[]>("/api/work-history"),
  get: (id: string) => apiFetch<WorkHistoryOut>(`/api/work-history/${id}`),
  create: (entry: WorkHistoryIn) =>
    apiFetch<WorkHistoryOut>("/api/work-history", {
      method: "POST",
      body: JSON.stringify(entry),
    }),
  update: (id: string, patch: WorkHistoryPatch) =>
    apiFetch<WorkHistoryOut>(`/api/work-history/${id}`, {
      method: "PATCH",
      body: JSON.stringify(patch),
    }),
  remove: (id: string) =>
    apiFetch<void>(`/api/work-history/${id}`, { method: "DELETE" }),
};
