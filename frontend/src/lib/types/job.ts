// Mirrors backend/app/models/job.py. Decimals arrive as strings.

export type HoursPerWeek = "lt30" | "gt30";
export type PaymentType = "hourly" | "fixed";
export type Duration = "lt1m" | "1to3m" | "3to6m" | "gt6m";
export type ExperienceLevel = "entry" | "intermediate" | "expert";

export interface Engagement {
  hours_per_week: HoursPerWeek | null;
  hours_per_week_raw: string | null;
  payment_type: PaymentType | null;
  duration: Duration | null;
  duration_raw: string | null;
  experience_level: ExperienceLevel | null;
  hourly_rate_min: string | null;
  hourly_rate_max: string | null;
  fixed_budget: string | null;
  project_type: "ongoing" | "one_time" | null;
  contract_to_hire: boolean;
}

export interface Activity {
  proposals_min: number | null;
  proposals_max: number | null;
  last_viewed_raw: string | null;
  interviewing: number | null;
  invites_sent: number | null;
  unanswered_invites: number | null;
  bid_high: string | null;
  bid_avg: string | null;
  bid_low: string | null;
}

export interface Connects {
  required: number | null;
  available: number | null;
}

export interface ClientStats {
  payment_verified: boolean | null;
  phone_verified: boolean | null;
  rating: string | null;
  review_count: number | null;
  country: string | null;
  city: string | null;
  jobs_posted: number | null;
  hire_rate_pct: number | null;
  open_jobs: number | null;
  total_spent: string | null;
  hires: number | null;
  active_hires: number | null;
  avg_hourly_paid: string | null;
  hours_billed: number | null;
  industry: string | null;
  company_size: string | null;
  member_since: string | null;
  recent_history_count: number | null;
}

export interface Question {
  text: string;
  source: "upwork" | "description";
}

export interface ParsedJob {
  source_format: "desktop" | "mobile" | "unknown";
  title: string | null;
  posted_ago_raw: string | null;
  location_restriction: string | null;
  upwork_job_id: string | null;
  description: string;
  engagement: Engagement;
  skills: string[];
  preferred_qualifications: Record<string, string>;
  activity: Activity;
  connects: Connects;
  client: ClientStats;
  questions: Question[];
  unparsed_lines: string[];
}

export interface BudgetStatement {
  model: "hourly" | "fixed" | "unstated";
  amount_raw: string | null;
  milestones: string[];
}

export interface Confidence {
  one_line: number;
  deliverables: number;
  requirements: number;
  questions_in_description: number;
  budget_statement: number;
  timeline_statement: number;
  red_flags: number;
  sensitive_data_domain: number;
}

export interface AiReading {
  one_line: string;
  deliverables: string[];
  requirements: string[];
  questions_in_description: string[];
  budget_statement: BudgetStatement | null;
  timeline_statement: string | null;
  red_flags: string[];
  sensitive_data_domain: { flag: boolean; reason: string | null };
  confidence: Confidence;
}

export interface AiFailure {
  kind: "error" | "empty" | "malformed" | "refusal" | "skipped";
  message: string;
}

export interface Conflict {
  field: string;
  upwork_value: string | null;
  description_value: string | null;
  evidence: string | null;
}

export type ParseStatus = "ok" | "ai_failed" | "unrecognised";

export interface JobAnalysis {
  parsed: ParsedJob;
  ai: AiReading | null;
  ai_failure: AiFailure | null;
  conflicts: Conflict[];
  parse_status: ParseStatus;
}

export type Decision = "continue" | "abandon";

// --- F2 advisory (mirrors backend/app/models/advisory.py) --------------------

export type EvidenceLevel =
  "none_history" | "none_comparable" | "thin" | "some" | "strong";
export type Fit = "strong" | "partial" | "weak" | "none";

export interface Comparable {
  entry_id: string;
  name: string;
  score: number;
  shared_tech: string[];
  shared_terms: string[];
  vertical: string | null;
  project_type: string | null;
  complexity: "low" | "medium" | "high" | null;
}

export interface MatchStrength {
  level: EvidenceLevel;
  comparable_count: number;
  history_count: number;
  label: string;
}

export interface Citation {
  entry_id: string;
  name: string;
  why: string;
}

export interface AdvisoryReading {
  fit: Fit;
  reasons: string[];
  gaps: string[];
  cite: Citation[];
  angle: string;
  confidence: {
    fit: number;
    reasons: number;
    gaps: number;
    cite: number;
    angle: number;
  };
}

export interface Advisory {
  comparables: Comparable[];
  match_strength: MatchStrength;
  reading: AdvisoryReading | null;
  failure: AiFailure | null;
  outcomes_note: string;
}

export interface JobPost {
  id: string;
  analysis: JobAnalysis;
  upwork_job_id: string | null;
  decision: Decision | null;
  decided_at: string | null;
  created_at: string;
  advisory: Advisory | null;
  advisory_at: string | null;
}

export interface JobPostSummary {
  id: string;
  title: string | null;
  parse_status: ParseStatus;
  upwork_job_id: string | null;
  decision: Decision | null;
  created_at: string;
}

/** Below this, a Claude-extracted field is shown with a low-confidence marker. */
export const LOW_CONFIDENCE = 0.6;
