// Suggested values for pick-or-type fields. Industry and job type come from
// picklists.json, the single vocabulary shared with Zoho's Lead picklists
// (docs/ZOHO_INTEGRATION.md); roles are local to Work history.

import picklists from "@/lib/picklists.json";

// Industry and job type are the shared vocabulary (see picklists.json):
// the same lists Zoho's Lead picklists use, so a work-history vertical, an
// advisory match and a Lead speak one language.
export const VERTICALS: readonly string[] = picklists.industry;

export const PROJECT_TYPES: readonly string[] = picklists.job_type;

export const ROLES = [
  "Sole consultant and developer",
  "Consultant",
  "Developer",
  "Architect",
  "Project lead",
  "Team member",
  "Advisor / reviewer",
];
