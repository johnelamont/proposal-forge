// F7: portfolio export. Mirrors backend/app/models/portfolio.py.

export const MAX_ENTRIES = 40;

export interface Selection {
  entry_ids: string[];
  title: string | null;
  from: string | null;
  to: string | null;
  include_results: boolean;
  include_tech: boolean;
}

export interface PortfolioEntryOption {
  id: string;
  name: string;
  vertical: string | null;
  started: string | null;
  ended: string | null;
  may_name_client: boolean;
  has_client_name: boolean;
}

export interface ManifestEntry {
  id: string;
  name: string;
  period: string | null;
  role: string | null;
  vertical: string | null;
  client_line: string | null;
  summary: string;
  tech_stack: string[];
  outcomes: string[];
}

export interface Manifest {
  title: string;
  operator: string;
  positioning: string;
  generated_on: string;
  entries: ManifestEntry[];
  tech: { name: string; count: number }[];
  results: {
    won: number;
    lost: number;
    withdrawn: number;
    industries_won: string[];
  } | null;
  footer: string;
}

export interface PreviewOut {
  manifest: Manifest;
  content_hash: string;
  pdf_base64: string;
  page_count: number;
  warnings: string[];
}

export interface ExportRecord {
  id: string;
  content_hash: string;
  pdf_hash: string;
  selection: Selection;
  entry_count: number;
  page_count: number;
  exported_by: string;
  exported_at: string;
}
