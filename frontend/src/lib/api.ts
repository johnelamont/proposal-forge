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
import type {
  Attention,
  OutcomeResult,
  ProposalOutcomes,
  QueuedOutcome,
  RagIndexRow,
  SecretCreated,
  SecretStatus,
} from "@/lib/types/outcomes";
import type {
  ExportRecord,
  PortfolioEntryOption,
  PreviewOut,
  Selection,
} from "@/lib/types/portfolio";
import type {
  ConnectionStatus,
  ConnectStart,
  CreateLeadResult,
  LeadAttempt,
  LeadFieldsIn,
  LeadPreview,
} from "@/lib/types/zoho";

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

export const zohoApi = {
  status: () => apiFetch<ConnectionStatus>("/api/integrations/zoho/status"),
  connect: () => apiFetch<ConnectStart>("/api/integrations/zoho/connect"),
  complete: (code: string, state: string) =>
    apiFetch<ConnectionStatus>("/api/integrations/zoho/complete", {
      method: "POST",
      body: JSON.stringify({ code, state }),
    }),
  disconnect: () =>
    apiFetch<void>("/api/integrations/zoho/connection", { method: "DELETE" }),
  leadPreview: (proposalId: string, reclassify = false) =>
    apiFetch<LeadPreview>(
      `/api/proposals/${proposalId}/lead-preview${reclassify ? "?reclassify=true" : ""}`,
    ),
  setLeadFields: (proposalId: string, fields: LeadFieldsIn) =>
    apiFetch<LeadPreview>(`/api/proposals/${proposalId}/lead-fields`, {
      method: "PUT",
      body: JSON.stringify(fields),
    }),
  createLead: (proposalId: string) =>
    apiFetch<CreateLeadResult>(`/api/proposals/${proposalId}/create-lead`, {
      method: "POST",
    }),
  leadAttempts: (proposalId: string) =>
    apiFetch<LeadAttempt[]>(`/api/proposals/${proposalId}/lead-attempts`),
};

export const outcomesApi = {
  /** A proposal's outcome history, index row, Zoho Lead link and nudge state. */
  forProposal: (proposalId: string) =>
    apiFetch<ProposalOutcomes>(`/api/proposals/${proposalId}/outcomes`),
  setArchived: (proposalId: string, archived: boolean) =>
    apiFetch<RagIndexRow>(`/api/proposals/${proposalId}/rag-archived`, {
      method: "PUT",
      body: JSON.stringify({ archived }),
    }),
  secretStatus: () =>
    apiFetch<SecretStatus>("/api/integrations/outcome-secret"),
  /** Generate or rotate; the plaintext comes back exactly once. */
  generateSecret: () =>
    apiFetch<SecretCreated>("/api/integrations/outcome-secret", {
      method: "POST",
    }),
  revokeSecret: () =>
    apiFetch<void>("/api/integrations/outcome-secret", { method: "DELETE" }),
  queue: () => apiFetch<QueuedOutcome[]>("/api/outcomes/queue"),
  match: (queueId: string, proposal_id: string) =>
    apiFetch<OutcomeResult>(`/api/outcomes/queue/${queueId}/match`, {
      method: "POST",
      body: JSON.stringify({ proposal_id }),
    }),
  dismiss: (queueId: string) =>
    apiFetch<void>(`/api/outcomes/queue/${queueId}/dismiss`, {
      method: "POST",
    }),
  attention: () => apiFetch<Attention>("/api/attention"),
  rebuildIndex: () =>
    apiFetch<{ rebuilt: number }>("/api/outcomes/rebuild-index", {
      method: "POST",
    }),
};

export const portfolioApi = {
  entries: () => apiFetch<PortfolioEntryOption[]>("/api/portfolio/entries"),
  preview: (selection: Selection) =>
    apiFetch<PreviewOut>("/api/portfolio/preview", {
      method: "POST",
      body: JSON.stringify(selection),
    }),
  /** The approval. The server re-renders, checks the hash, logs, then
   * returns the PDF; a 409 means the document changed since the preview. */
  export: async (selection: Selection, content_hash: string) => {
    const token = await accessToken();
    let response: Response;
    try {
      response = await fetch(API_URL + "/api/portfolio/exports", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ selection, content_hash }),
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
    const disposition = response.headers.get("content-disposition") ?? "";
    const match = /filename="([^"]+)"/.exec(disposition);
    return {
      blob: await response.blob(),
      filename: match?.[1] ?? "portfolio.pdf",
      contentHash: response.headers.get("x-content-hash"),
    };
  },
  exports: () => apiFetch<ExportRecord[]>("/api/portfolio/exports"),
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
