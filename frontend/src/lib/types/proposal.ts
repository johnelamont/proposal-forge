// Mirrors backend/app/models/proposal.py.
import type { AiFailure } from "@/lib/types/job";

export interface ProfileIn {
  signature_name: string;
  positioning: string;
  greeting: string;
  sign_off: string;
  tone_notes: string;
  never_claim: string[];
  default_hourly_rate: string | null;
  fixed_price_range: string | null;
}

export interface Profile extends ProfileIn {
  user_id: string;
  created_at: string;
  updated_at: string;
}

export const EMPTY_PROFILE: ProfileIn = {
  signature_name: "",
  positioning: "",
  greeting: "Hi,",
  sign_off: "Kind Regards,",
  tone_notes: "",
  never_claim: [],
  default_hourly_rate: null,
  fixed_price_range: null,
};

export interface Answer {
  question: string;
  answer: string;
}

export interface QuoteEvidence {
  source: "job" | "profile" | "history" | string;
  detail: string;
}

export interface Quote {
  model: "hourly" | "fixed" | null;
  amount: string | null;
  rationale: string;
  evidence: QuoteEvidence[];
}

export interface Sections {
  cover_letter: string | null;
  answers: Answer[];
  quote: Quote | null;
}

export type Source = "ai" | "refine" | "edit" | "manual";
export type SectionName = "cover_letter" | "answer" | "quote" | "all";

export interface AiMeta {
  model: string | null;
  confidence: Record<string, number>;
  warnings: string[];
  failure: AiFailure | null;
}

export interface DraftVersion {
  id: string;
  proposal_id: string;
  version: number;
  source: Source;
  sections: Sections;
  ai_meta: AiMeta | null;
  created_at: string;
}

export interface ProposalApproval {
  id: string;
  proposal_id: string;
  draft_version_id: string;
  section: SectionName;
  section_index: number | null;
  content_hash: string;
  approved_by: string;
  approved_at: string;
}

export interface Proposal {
  id: string;
  job_post_id: string;
  status: "draft" | "submitted" | "won" | "lost" | "withdrawn";
  extra_questions: string[];
  current_version_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ProposalOut {
  proposal: Proposal;
  versions: DraftVersion[];
  approvals: ProposalApproval[];
  job_title: string | null;
}

export interface CopyText {
  text: string;
  content_hash: string;
}
