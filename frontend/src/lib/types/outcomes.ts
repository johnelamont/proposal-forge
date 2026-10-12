// F8: outcomes pushed from Zoho, the review queue, the learning index, the
// integration secret, and the home screen's Attention strip. Mirrors
// backend/app/models/outcomes.py.

export type Outcome = "won" | "lost" | "withdrawn";
export type LostReason =
  "hired_other" | "job_closed" | "junk_lead" | "not_qualified";

export const LOST_REASON_LABEL: Record<LostReason, string> = {
  hired_other: "client hired someone else",
  job_closed: "job closed",
  junk_lead: "junk lead",
  not_qualified: "not qualified",
};

export interface OutcomeRecord {
  id: string;
  proposal_id: string;
  outcome: Outcome;
  lost_reason: LostReason | null;
  decided_at: string | null;
  zoho_lead_id: string | null;
  lead: Record<string, unknown>;
  source: "zoho" | "manual_match";
  received_at: string;
}

export interface RagIndexRow {
  proposal_id: string;
  outcome: Outcome;
  lost_reason: LostReason | null;
  industry: string | null;
  job_type: string | null;
  tools: string | null;
  rate_type: string | null;
  hourly_rate: string | null;
  fixed_price: string | null;
  budget: string | null;
  budget_band: string | null;
  quote_model: string | null;
  quote_amount: string | null;
  job_title: string | null;
  skills: string[];
  proposal_excerpt: string | null;
  decided_at: string | null;
  archived: boolean;
  indexed_at: string;
}

export interface ProposalOutcomes {
  status: string;
  history: OutcomeRecord[];
  index: RagIndexRow | null;
  zoho_lead_id: string | null;
  lead_url: string | null;
  submitted_at: string | null;
  stale_after_days: number;
  stale: boolean;
}

export interface QueuedOutcome {
  id: string;
  upwork_job_id: string;
  zoho_lead_id: string | null;
  payload: Record<string, unknown>;
  received_at: string;
  resolved_at: string | null;
  resolved_proposal_id: string | null;
  dismissed_at: string | null;
}

export interface OutcomeResult {
  code: 200 | 202;
  message: string;
  proposal_id: string | null;
  outcome: Outcome | null;
  indexed: boolean;
  queued: boolean;
  duplicate: boolean;
}

export interface SecretStatus {
  exists: boolean;
  created_at: string | null;
  last_used_at: string | null;
  endpoint_url: string;
}

export interface SecretCreated extends SecretStatus {
  secret: string;
}

export interface AttentionItem {
  proposal_id: string;
  job_title: string | null;
  since: string | null;
}

export interface Attention {
  lead_failed: AttentionItem[];
  queued_outcomes: number;
  stale_submitted: AttentionItem[];
  stale_after_days: number;
}
