// Mirrors backend/app/models/work_history.py.
import type { AiFailure } from "@/lib/types/job";

export type Complexity = "low" | "medium" | "high";

export interface DroppedFile {
  name: string;
  content: string;
}

export interface RefusedFile {
  name: string;
  reason: string;
}

export interface AcceptedFile {
  name: string;
  size: number;
  sha256: string;
}

export interface SourceFile extends AcceptedFile {
  content: string;
}

export interface ExtractionConfidence {
  name: number;
  summary: number;
  tech_stack: number;
  vertical: number;
  project_type: number;
  complexity: number;
  role: number;
  outcomes: number;
  client_name_detected: number;
  duration_hint: number;
}

export interface Extraction {
  name: string;
  summary: string;
  tech_stack: string[];
  vertical: string | null;
  project_type: string | null;
  complexity: Complexity;
  complexity_reason: string;
  role: string | null;
  outcomes: string[];
  client_name_detected: string | null;
  duration_hint: string | null;
  confidence: ExtractionConfidence;
}

export interface ExtractResponse {
  accepted: AcceptedFile[];
  refused: RefusedFile[];
  extraction: Extraction | null;
  failure: AiFailure | null;
}

/** The operator's record as sent on create. */
export interface WorkHistoryIn {
  name: string;
  summary: string;
  tech_stack: string[];
  vertical: string | null;
  project_type: string | null;
  complexity: Complexity | null;
  role: string | null;
  outcomes: string[];
  client_name: string | null;
  may_name_client: boolean;
  budget_band: string | null;
  started: string | null;
  ended: string | null;
  source_files: DroppedFile[];
  ai_extraction: Extraction | null;
}

export interface WorkHistoryPatch {
  name?: string;
  summary?: string;
  tech_stack?: string[];
  vertical?: string;
  project_type?: string;
  complexity?: Complexity;
  role?: string;
  outcomes?: string[];
  client_name?: string;
  may_name_client?: boolean;
  budget_band?: string;
  started?: string;
  ended?: string;
  clear?: string[];
}

export interface WorkHistoryOut extends Omit<WorkHistoryIn, "source_files"> {
  id: string;
  source_files: SourceFile[];
  created_at: string;
  updated_at: string;
}

export interface WorkHistorySummary {
  id: string;
  name: string;
  vertical: string | null;
  tech_stack: string[];
  complexity: Complexity | null;
  may_name_client: boolean;
  ended: string | null;
  updated_at: string;
}
