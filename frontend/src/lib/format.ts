import type {
  Duration,
  Engagement,
  ExperienceLevel,
  HoursPerWeek,
} from "@/lib/types/job";

export function money(value: string | null, opts: { cents?: boolean } = {}) {
  if (value === null) return null;
  const n = Number(value);
  if (Number.isNaN(n)) return value;
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: opts.cents ? 2 : 0,
    maximumFractionDigits: opts.cents ? 2 : 0,
  });
}

export function rateRange(e: Engagement): string | null {
  if (e.payment_type === "fixed") return money(e.fixed_budget, { cents: true });
  if (e.hourly_rate_min === null) return null;
  const lo = money(e.hourly_rate_min, { cents: true });
  const hi = money(e.hourly_rate_max, { cents: true });
  return lo === hi ? `${lo}/hr` : `${lo} – ${hi}/hr`;
}

const HOURS: Record<HoursPerWeek, string> = {
  lt30: "< 30 hrs/week",
  gt30: "30+ hrs/week",
};
const DURATION: Record<Duration, string> = {
  lt1m: "< 1 month",
  "1to3m": "1–3 months",
  "3to6m": "3–6 months",
  gt6m: "6+ months",
};
const LEVEL: Record<ExperienceLevel, string> = {
  entry: "Entry level",
  intermediate: "Intermediate",
  expert: "Expert",
};

export const label = {
  hours: (v: HoursPerWeek | null) => (v ? HOURS[v] : null),
  duration: (v: Duration | null) => (v ? DURATION[v] : null),
  level: (v: ExperienceLevel | null) => (v ? LEVEL[v] : null),
  payment: (v: "hourly" | "fixed" | null) =>
    v === null ? null : v === "hourly" ? "Hourly" : "Fixed price",
  projectType: (v: "ongoing" | "one_time" | null) =>
    v === null ? null : v === "ongoing" ? "Ongoing" : "One-time",
};

export function proposals(min: number | null, max: number | null) {
  if (min === null) return null;
  if (max === null) return `${min}+`;
  if (min === max) return `${min}`;
  if (min === 0) return `< ${max}`;
  return `${min}–${max}`;
}

/** Placeholder for a value that was not in the paste. Never "0". */
export const DASH = "—";
