// Mirrors backend/app/models/zoho.py.
import type { AiFailure } from "@/lib/types/job";

export interface ConnectionStatus {
  configured: boolean;
  connected: boolean;
  connected_at: string | null;
  scopes: string[];
  last_used_at: string | null;
}

export interface ConnectStart {
  authorize_url: string;
  state: string;
}

export interface LeadFieldsIn {
  industry: string | null;
  job_type: string | null;
  tools: string | null;
  proposal_link: string | null;
  by_invitation: boolean;
}

export interface LeadFields extends LeadFieldsIn {
  confirmed_at: string | null;
}

export interface Classification {
  industry: string;
  job_type: string;
  tools: string;
  confidence: { industry: number; job_type: number; tools: number };
}

export interface FieldFlag {
  field: "Industry" | "Job_Type" | "Tools";
  reason: string;
  confidence: number | null;
}

export interface ChecklistItem {
  key: string;
  label: string;
  ok: boolean;
}

export interface LeadPreview {
  payload: Record<string, unknown>;
  truncations: string[];
  flags: FieldFlag[];
  checklist: ChecklistItem[];
  ready: boolean;
  classification: Classification | null;
  classification_failure: AiFailure | null;
  lead_fields: LeadFields | null;
  picklists: { Industry: string[]; Job_Type: string[] };
  thresholds: Record<string, number>;
}

export interface LeadAttempt {
  id: string;
  proposal_id: string;
  payload_hash: string;
  response_status: number | null;
  zoho_lead_id: string | null;
  action: string | null;
  error: string | null;
  attempted_by: string;
  attempted_at: string;
}

export interface CreateLeadResult {
  ok: boolean;
  zoho_lead_id: string | null;
  action: string | null;
  error: string | null;
  reconnect: boolean;
  attempt: LeadAttempt;
}
