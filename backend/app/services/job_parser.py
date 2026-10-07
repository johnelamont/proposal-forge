"""Deterministic parser for an Upwork job-post paste (F1, layer one).

Reads every labelled field with regular expressions and splits off the prose
(the *Summary* body) for the Claude layer. No AI here. Sections are optional
and may appear in any order; desktop and mobile layouts differ. See
docs/F1_JOB_PARSING.md and the fixtures under tests/fixtures/.
"""

from __future__ import annotations

import re
from decimal import Decimal

from app.models.job import (
    Activity,
    Client,
    Connects,
    Duration,
    Engagement,
    ExperienceLevel,
    HoursPerWeek,
    ParsedJob,
    PaymentType,
    Question,
)

# --- Section headings -------------------------------------------------------

HEADINGS: dict[str, str] = {
    "Summary": "summary",
    "Skills and Expertise": "skills",
    "Preferred qualifications": "preferred",
    "Activity on this job": "activity",
    "About the client": "client",
    "Job link": "link",
    "You will be asked to answer the following questions when submitting a proposal:": (
        "questions"
    ),
}
RE_HISTORY = re.compile(r"^Client['’]s recent history \((\d+)\)$")
RE_OTHER_JOBS = re.compile(r"^Other open jobs by this Client \((\d+)\)$")

# --- Header -----------------------------------------------------------------

RE_POSTED = re.compile(r"^Posted .+ ago$")
RE_LOCATION = re.compile(r"^(Worldwide|Only freelancers located in .+ may apply\.)$")
RE_CONNECTS_REQUIRED = re.compile(r"^Send a proposal for: (\d+) Connects$")
RE_CONNECTS_AVAILABLE = re.compile(r"^Available Connects: (\d+)$")

# --- Engagement block -------------------------------------------------------

RE_HOURS = re.compile(r"^(More|Less) than (\d+) hrs/week$")
RE_MONEY = re.compile(r"^\$([\d,]+\.\d{2})$")
RE_PROJECT_TYPE = re.compile(r"^Project Type: (.+)$")
DURATIONS: dict[str, Duration] = {
    "Less than 1 month": Duration.LT1M,
    "1 to 3 months": Duration.M1_3,
    "3 to 6 months": Duration.M3_6,
    "More than 6 months": Duration.GT6M,
    "6+ months": Duration.GT6M,
}
EXPERIENCE: dict[str, ExperienceLevel] = {
    "Entry level": ExperienceLevel.ENTRY,
    "Entry Level": ExperienceLevel.ENTRY,
    "Intermediate": ExperienceLevel.INTERMEDIATE,
    "Expert": ExperienceLevel.EXPERT,
}
PAYMENT: dict[str, PaymentType] = {
    "Hourly": PaymentType.HOURLY,
    "Fixed-price": PaymentType.FIXED,
    "Fixed price": PaymentType.FIXED,
}
# Explanatory lines Upwork prints under the structured fields. Dropped.
ENGAGEMENT_BOILERPLATE = {
    "Duration",
    "Experience Level",
    "Contract-to-hire opportunity",
    "This lets talent know that this job could become full time.",
    "Learn more",
    "-",
}
RE_EXPERIENCE_BLURB = re.compile(r"^I am (looking|willing) .+")

# --- Activity ---------------------------------------------------------------

RE_PROPOSALS_RANGE = re.compile(r"^(\d+) to (\d+)$")
RE_PROPOSALS_PLUS = re.compile(r"^(\d+)\+$")
RE_PROPOSALS_LT = re.compile(r"^Less than (\d+)$")
RE_BID_RANGE = re.compile(
    r"^Bid range - High \$([\d,.]+) Avg \$([\d,.]+) Low \$([\d,.]+)$"
)
ACTIVITY_INT_LABELS = {
    "Interviewing:": "interviewing",
    "Invites sent:": "invites_sent",
    "Unanswered invites:": "unanswered_invites",
}

# --- About the client -------------------------------------------------------

RE_RATING = re.compile(r"^Rating is ([\d.]+) out of 5\.$")
RE_BARE_RATING = re.compile(r"^[\d.]+$")
RE_REVIEWS = re.compile(r"^[\d.]+ of (\d+) reviews?$")
RE_LOCAL_TIME = re.compile(r"^(.*?)\s*(\d{1,2}:\d{2} [AP]M)$")
RE_JOBS_POSTED = re.compile(r"^(\d+) jobs? posted$")
RE_HIRE_RATE = re.compile(r"^(\d+)% hire rate, (\d+) open jobs?$")
RE_TOTAL_SPENT = re.compile(r"^\$([\d,.]+)([KM])? total spent$")
RE_HIRES = re.compile(r"^(\d+) hires?, (\d+) active$")
RE_AVG_HOURLY = re.compile(r"^\$([\d,.]+) /hr avg hourly rate paid$")
RE_HOURS_BILLED = re.compile(r"^([\d,]+) hours$")
RE_COMPANY_SIZE = re.compile(r"^.+ company \(.+\)$|^Individual client$")
RE_MEMBER_SINCE = re.compile(r"^Member since (.+)$")

# --- Job link ---------------------------------------------------------------

RE_JOB_URL = re.compile(r"https?://www\.upwork\.com/jobs/(~[0-9A-Za-z]+)")


def _dec(text: str) -> Decimal:
    return Decimal(text.replace(",", ""))


def _split_sections(lines: list[str]) -> tuple[dict[str, list[str]], Client]:
    """Group lines under their section heading. Lines before `Summary` are
    the header. The two history sections are counted and otherwise dropped."""
    sections: dict[str, list[str]] = {"header": []}
    current = "header"
    client = Client()
    for line in lines:
        if line in HEADINGS:
            current = HEADINGS[line]
            sections.setdefault(current, [])
            continue
        if m := RE_HISTORY.match(line):
            client.recent_history_count = int(m.group(1))
            current = "history"
            continue
        if RE_OTHER_JOBS.match(line):
            current = "other_jobs"
            continue
        sections.setdefault(current, []).append(line)
    return sections, client


def _is_engagement_line(line: str) -> bool:
    return bool(
        RE_HOURS.match(line)
        or line in PAYMENT
        or line in DURATIONS
        or line in EXPERIENCE
        or RE_MONEY.match(line)
        or RE_PROJECT_TYPE.match(line)
        or line in ENGAGEMENT_BOILERPLATE
        or RE_EXPERIENCE_BLURB.match(line)
    )


def _parse_header(lines: list[str], job: ParsedJob, unparsed: list[str]) -> None:
    for line in lines:
        if not line:
            continue
        if _parse_connects(line, job.connects):
            continue
        if job.title is None:
            job.title = line
        elif RE_POSTED.match(line):
            job.posted_ago_raw = line
        elif RE_LOCATION.match(line):
            job.location_restriction = line
        else:
            unparsed.append(line)


def _parse_connects(line: str, connects: Connects) -> bool:
    if m := RE_CONNECTS_REQUIRED.match(line):
        connects.required = int(m.group(1))
        return True
    if m := RE_CONNECTS_AVAILABLE.match(line):
        connects.available = int(m.group(1))
        return True
    return False


def _split_summary(lines: list[str]) -> tuple[list[str], list[str]]:
    """The Summary section holds the prose followed by the unlabelled
    engagement block. The prose ends at the first recognised engagement line."""
    for i, line in enumerate(lines):
        if line and _is_engagement_line(line):
            return lines[:i], lines[i:]
    return lines, []


def _parse_engagement(lines: list[str], eng: Engagement, unparsed: list[str]) -> None:
    amounts: list[Decimal] = []
    for line in lines:
        if not line:
            continue
        if m := RE_HOURS.match(line):
            eng.hours_per_week_raw = line
            more = m.group(1) == "More"
            eng.hours_per_week = HoursPerWeek.GT30 if more else HoursPerWeek.LT30
        elif line in PAYMENT:
            if eng.payment_type is None:
                eng.payment_type = PAYMENT[line]
        elif line in DURATIONS:
            eng.duration_raw = line
            eng.duration = DURATIONS[line]
        elif line in EXPERIENCE:
            eng.experience_level = EXPERIENCE[line]
        elif m := RE_MONEY.match(line):
            amounts.append(_dec(m.group(1)))
        elif m := RE_PROJECT_TYPE.match(line):
            value = m.group(1).lower()
            if "ongoing" in value:
                eng.project_type = "ongoing"
            elif "one" in value:
                eng.project_type = "one_time"
            else:
                unparsed.append(line)
        elif line == "Contract-to-hire opportunity":
            eng.contract_to_hire = True
        elif line in ENGAGEMENT_BOILERPLATE or RE_EXPERIENCE_BLURB.match(line):
            continue
        else:
            unparsed.append(line)

    if eng.payment_type == PaymentType.FIXED and amounts:
        eng.fixed_budget = amounts[0]
    elif amounts:
        eng.hourly_rate_min = amounts[0]
        eng.hourly_rate_max = amounts[1] if len(amounts) > 1 else amounts[0]


def _parse_preferred(lines: list[str], out: dict[str, str], unparsed: list[str]):
    label: str | None = None
    for line in lines:
        if not line:
            continue
        if line.endswith(":"):
            label = line[:-1]
        elif label is not None:
            out[label] = line
            label = None
        else:
            unparsed.append(line)


def _parse_activity(
    lines: list[str], act: Activity, connects: Connects, unparsed: list[str]
) -> None:
    label: str | None = None
    for line in lines:
        if not line:
            continue
        if _parse_connects(line, connects):
            continue
        if m := RE_BID_RANGE.match(line):
            act.bid_high, act.bid_avg, act.bid_low = (_dec(g) for g in m.groups())
            continue
        if line.endswith(":"):
            label = line
            continue
        if label == "Proposals:":
            if m := RE_PROPOSALS_RANGE.match(line):
                act.proposals_min, act.proposals_max = int(m[1]), int(m[2])
            elif m := RE_PROPOSALS_PLUS.match(line):
                act.proposals_min, act.proposals_max = int(m[1]), None
            elif m := RE_PROPOSALS_LT.match(line):
                act.proposals_min, act.proposals_max = 0, int(m[1])
            elif line.isdigit():
                act.proposals_min = act.proposals_max = int(line)
            else:
                unparsed.append(line)
        elif label == "Last viewed by client:":
            act.last_viewed_raw = line
        elif label in ACTIVITY_INT_LABELS and line.isdigit():
            setattr(act, ACTIVITY_INT_LABELS[label], int(line))
        else:
            unparsed.append(line)
        label = None


def _parse_client(lines: list[str], client: Client, unparsed: list[str]) -> None:
    for line in lines:
        if not line:
            continue
        if line == "Payment method verified":
            client.payment_verified = True
        elif line == "Payment method not verified":
            client.payment_verified = False
        elif line == "Phone number verified":
            client.phone_verified = True
        elif m := RE_RATING.match(line):
            client.rating = _dec(m.group(1))
        elif m := RE_REVIEWS.match(line):
            client.review_count = int(m.group(1))
        elif RE_BARE_RATING.match(line):
            continue  # the rating repeated on its own line
        elif m := RE_LOCAL_TIME.match(line):
            client.city = m.group(1) or None
        elif m := RE_JOBS_POSTED.match(line):
            client.jobs_posted = int(m.group(1))
        elif m := RE_HIRE_RATE.match(line):
            client.hire_rate_pct, client.open_jobs = int(m[1]), int(m[2])
        elif m := RE_TOTAL_SPENT.match(line):
            scale = {"K": 1_000, "M": 1_000_000, None: 1}[m.group(2)]
            client.total_spent = _dec(m.group(1)) * scale
        elif m := RE_HIRES.match(line):
            client.hires, client.active_hires = int(m[1]), int(m[2])
        elif m := RE_AVG_HOURLY.match(line):
            client.avg_hourly_paid = _dec(m.group(1))
        elif m := RE_HOURS_BILLED.match(line):
            client.hours_billed = int(m.group(1).replace(",", ""))
        elif RE_COMPANY_SIZE.match(line):
            client.company_size = line
        elif m := RE_MEMBER_SINCE.match(line):
            client.member_since = m.group(1)
        elif client.country is None:
            client.country = line  # first free-text line: the country
        elif client.industry is None:
            client.industry = line  # second free-text line: the industry
        else:
            unparsed.append(line)


def _source_format(job: ParsedJob, sections: dict[str, list[str]]) -> str:
    history_entries = any(line for line in sections.get("history", []))
    if job.upwork_job_id or history_entries:
        return "desktop"
    header_has_connects = any(
        RE_CONNECTS_REQUIRED.match(line) for line in sections.get("header", [])
    )
    if header_has_connects:
        return "mobile"
    return "unknown"


def parse_job_post(raw: str) -> ParsedJob:
    """Parse a paste into structured fields plus the prose for Claude."""
    lines = [line.rstrip() for line in raw.replace("\r\n", "\n").split("\n")]
    sections, client = _split_sections(lines)

    job = ParsedJob(client=client)
    unparsed: list[str] = []

    _parse_header(sections.get("header", []), job, unparsed)

    prose, engagement = _split_summary(sections.get("summary", []))
    job.description = "\n".join(prose).strip()
    _parse_engagement(engagement, job.engagement, unparsed)

    job.skills = [line for line in sections.get("skills", []) if line]
    _parse_preferred(
        sections.get("preferred", []), job.preferred_qualifications, unparsed
    )
    _parse_activity(sections.get("activity", []), job.activity, job.connects, unparsed)
    _parse_client(sections.get("client", []), job.client, unparsed)

    job.questions = [
        Question(text=line, source="upwork")
        for line in sections.get("questions", [])
        if line
    ]

    for line in sections.get("link", []):
        if m := RE_JOB_URL.search(line):
            job.upwork_job_id = m.group(1)
        elif line and line != "Copy link":
            unparsed.append(line)
    if job.upwork_job_id is None and (m := RE_JOB_URL.search(raw)):
        job.upwork_job_id = m.group(1)

    job.unparsed_lines = unparsed
    job.source_format = _source_format(job, sections)  # type: ignore[assignment]
    return job
