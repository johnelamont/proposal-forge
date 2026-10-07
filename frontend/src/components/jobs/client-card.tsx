import { money } from "@/lib/format";
import type { Activity, ClientStats } from "@/lib/types/job";

import { Card, Facts } from "./card";

function verified(v: boolean | null) {
  if (v === null) return null;
  return v ? "Verified" : "Not verified";
}

export function ClientCard({
  client: c,
  activity: a,
}: {
  client: ClientStats;
  activity: Activity;
}) {
  return (
    <Card
      title="Client"
      aside={
        <span className="text-xs text-neutral-500">Never sent to Claude</span>
      }
    >
      <Facts
        items={[
          ["Payment method", verified(c.payment_verified)],
          ["Phone", verified(c.phone_verified)],
          [
            "Rating",
            c.rating === null
              ? null
              : `${c.rating} (${c.review_count ?? 0} reviews)`,
          ],
          ["Location", [c.city, c.country].filter(Boolean).join(", ") || null],
          ["Member since", c.member_since],
          ["Jobs posted", c.jobs_posted],
          [
            "Hire rate",
            c.hire_rate_pct === null
              ? null
              : `${c.hire_rate_pct}% · ${c.open_jobs ?? 0} open`,
          ],
          ["Total spent", money(c.total_spent)],
          [
            "Hires",
            c.hires === null
              ? null
              : `${c.hires} (${c.active_hires ?? 0} active)`,
          ],
          [
            "Avg rate paid",
            c.avg_hourly_paid
              ? `${money(c.avg_hourly_paid, { cents: true })}/hr`
              : null,
          ],
          ["Hours billed", c.hours_billed?.toLocaleString() ?? null],
          ["Industry", c.industry],
          ["Company", c.company_size],
          [
            "Bid range",
            a.bid_avg === null
              ? null
              : `${money(a.bid_low, { cents: true })} – ${money(a.bid_high, { cents: true })} (avg ${money(a.bid_avg, { cents: true })})`,
          ],
          ["Interviewing", a.interviewing],
          [
            "Invites",
            a.invites_sent === null
              ? null
              : `${a.invites_sent} sent · ${a.unanswered_invites ?? 0} unanswered`,
          ],
          ["Last viewed", a.last_viewed_raw],
        ]}
      />
    </Card>
  );
}
