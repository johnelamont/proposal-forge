"""Deterministic matching of a parsed job against work history (F2, layer one).

Transparent by design: every match carries the terms it shares with the job,
and the evidence label is a count, not a judgement. No AI here.
"""

from __future__ import annotations

import re
from typing import Any

from app.models.advisory import (
    Comparable,
    MatchStrength,
    OutcomeEvidence,
    ProposalComparable,
)
from app.models.job import ParsedJob

# A term expands to itself plus its family, so "Zoho CRM" in a job meets
# "Zoho" in history. Deliberately short; extend as real jobs show gaps.
ALIASES: dict[str, set[str]] = {
    "zoho crm": {"zoho", "crm"},
    "zoho creator": {"zoho"},
    "zoho one": {"zoho"},
    "zoho books": {"zoho"},
    "zoho desk": {"zoho"},
    "zoho analytics": {"zoho"},
    "deluge": {"zoho"},
    "hubspot": {"crm"},
    "salesforce": {"crm"},
    "pipedrive": {"crm"},
    "next.js": {"nextjs", "react"},
    "nextjs": {"next.js", "react"},
    "react": {"javascript"},
    "typescript": {"javascript"},
    "node.js": {"node", "javascript"},
    "node": {"node.js", "javascript"},
    "fastapi": {"python"},
    "django": {"python"},
    "flask": {"python"},
    "supabase": {"postgres", "postgresql"},
    "postgresql": {"postgres"},
    "postgres": {"postgresql"},
    "google sheets": {"sheets", "spreadsheet"},
    "excel": {"spreadsheet"},
    "airtable": {"spreadsheet", "no-code"},
    "smartsheet": {"spreadsheet"},
    "zapier": {"automation", "no-code"},
    "make": {"automation", "no-code"},
    "integromat": {"automation", "no-code", "make"},
    "power automate": {"automation"},
    "webhooks": {"webhook", "api", "integration"},
    "webhook": {"webhooks", "api", "integration"},
    "rest api": {"api", "integration"},
    "api integration": {"api", "integration"},
    "claude api": {"ai", "llm"},
    "openai": {"ai", "llm"},
    "llm": {"ai"},
    "dashboard": {"reporting", "analytics"},
    "data analytics framework": {"analytics", "dashboard"},
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "that",
    "this",
    "from",
    "into",
    "your",
    "you",
    "our",
    "are",
    "will",
    "have",
    "has",
    "need",
    "needs",
    "needed",
    "looking",
    "want",
    "wants",
    "who",
    "can",
    "all",
    "any",
    "not",
    "but",
    "use",
    "using",
    "used",
    "work",
    "working",
    "please",
    "job",
    "project",
    "projects",
    "hours",
    "week",
    "hourly",
    "fixed",
    "price",
    "budget",
    "experience",
    "experienced",
    "expert",
    "level",
    "intermediate",
    "skills",
    "skill",
    "ability",
    "strong",
    "proven",
    "must",
    "should",
    "would",
    "also",
    "etc",
    "more",
    "than",
    "like",
    "when",
    "what",
    "which",
    "where",
    "then",
    "them",
    "they",
    "their",
    "there",
    "about",
    "over",
    "under",
    "after",
    "before",
    "each",
    "per",
    "via",
    "well",
    "very",
    "just",
    "only",
    "most",
    "some",
    "such",
    "these",
    "those",
    "within",
    "across",
    "between",
    "through",
    "while",
    "being",
    "been",
    "were",
    "was",
    "its",
    "his",
    "her",
    "him",
    "she",
    "one",
    "two",
    "three",
    "new",
    "build",
    "built",
    "building",
    "help",
    "simple",
    "quick",
    "small",
    "large",
    "good",
    "great",
    "best",
    "time",
    "part",
    "full",
    "long",
    "short",
    "term",
    "someone",
    "people",
    "team",
    "company",
    "business",
    "client",
    "clients",
    "freelancer",
    "freelancers",
    "contractor",
    "developer",
    "consultant",
    "specialist",
    "apply",
    "application",
    "proposal",
    "attach",
    "attachment",
    "include",
    "describe",
    "recent",
    "similar",
    "related",
    "require",
    "required",
    "requirements",
    "based",
    "ongoing",
    "month",
    "months",
    "year",
    "years",
    "day",
    "days",
    "set",
    "setup",
    "make",
    "makes",
    "making",
    "get",
    "give",
    "automatically",
    "automatic",
    "created",
    "create",
    "creates",
    "creating",
    "connected",
    "connect",
    "connects",
    "code",
    "daily",
    "weekly",
    "monthly",
    "system",
    "systems",
    "data",
    "details",
    "detail",
    "status",
    "record",
    "records",
    "existing",
    "provide",
    "provided",
    "provides",
    "properly",
    "specific",
    "specifically",
    "things",
    "thing",
    "every",
    "multiple",
    "update",
    "updates",
    "updated",
    "change",
    "changes",
    "changed",
    "send",
    "sends",
    "sent",
    "done",
    "first",
    "second",
    "next",
    "last",
    "later",
    "current",
    "currently",
    "already",
    "still",
    "again",
    "another",
    "other",
    "others",
    "same",
    "different",
    "various",
    "several",
    "many",
    "much",
    "high",
    "low",
    "quality",
    "levels",
    "able",
    "easy",
    "easily",
    "e.g",
    "i.e",
    "hand",
    "hands",
    "video",
    "notes",
    "note",
    "few",
    "lot",
    "lots",
}
KEEP_SHORT = {"ai", "ui", "ux", "go", "c#", "c++", "r", "bi"}

MAX_COMPARABLES = 5
MIN_TECH_OVERLAP = 1
MIN_KEYWORD_OVERLAP = 3
# F8: fewer recorded outcomes than this and the evidence is shown as counts
# only — too small a sample to read anything into (ADR-003).
MIN_OUTCOMES_FOR_VERDICT = 3


def normalise(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())


def expand(term: str) -> set[str]:
    base = normalise(term)
    return {base} | ALIASES.get(base, set())


def tech_terms(items: list[str]) -> set[str]:
    out: set[str] = set()
    for item in items:
        out |= expand(item)
    return out


def tokens(text: str | None) -> set[str]:
    if not text:
        return set()
    words = re.findall(r"[a-z0-9][a-z0-9+#.\-]*", text.lower())
    return {
        w.strip(".-")
        for w in words
        if (len(w) >= 4 or w in KEEP_SHORT) and w not in STOPWORDS
    }


def _job_terms(job: ParsedJob, one_line: str | None) -> tuple[set[str], set[str]]:
    skills = tech_terms(job.skills)
    text = " ".join(filter(None, [job.title, job.description, one_line]))
    keywords = tokens(text) | tokens(job.client.industry)
    return skills, keywords


def score_entry(
    job: ParsedJob, one_line: str | None, entry: dict[str, Any]
) -> Comparable | None:
    """Return a Comparable if the entry resembles the job, else None."""
    job_skills, job_keywords = _job_terms(job, one_line)
    entry_stack: list[str] = entry.get("tech_stack") or []
    entry_tech = tech_terms(entry_stack)
    entry_text = " ".join(
        filter(
            None,
            [
                entry.get("name"),
                entry.get("summary"),
                entry.get("vertical"),
                entry.get("project_type"),
                " ".join(entry.get("outcomes") or []),
            ],
        )
    )
    entry_keywords = tokens(entry_text) | tech_terms(entry_stack)

    shared_tech_norm = job_skills & entry_tech
    # Report shared tech in the history entry's own spelling.
    shared_tech = sorted(
        {s for s in entry_stack if expand(s) & shared_tech_norm}, key=str.lower
    )
    # Also count job skills that only matched via the entry's text.
    shared_tech_norm |= job_skills & entry_keywords

    shared_terms = sorted((job_keywords & entry_keywords) - shared_tech_norm)
    tech_overlap = len(shared_tech_norm)
    keyword_overlap = len(shared_terms)

    if tech_overlap < MIN_TECH_OVERLAP and keyword_overlap < MIN_KEYWORD_OVERLAP:
        return None

    vertical_bonus = 1.0 if tokens(entry.get("vertical")) & job_keywords else 0.0
    score = 2.0 * tech_overlap + 0.5 * min(keyword_overlap, 10) + vertical_bonus
    return Comparable(
        entry_id=entry["id"],
        name=entry["name"],
        score=round(score, 2),
        shared_tech=shared_tech,
        shared_terms=shared_terms[:8],
        vertical=entry.get("vertical"),
        project_type=entry.get("project_type"),
        complexity=entry.get("complexity"),
    )


def find_comparables(
    job: ParsedJob, one_line: str | None, history: list[dict[str, Any]]
) -> list[Comparable]:
    matches = [c for e in history if (c := score_entry(job, one_line, e))]
    matches.sort(key=lambda c: (-c.score, c.name.lower()))
    return matches[:MAX_COMPARABLES]


# --- F8: the operator's own past proposals with outcomes -----------------------


def _split_tools(tools: str | None) -> list[str]:
    return [t.strip() for t in (tools or "").split(",") if t.strip()]


def score_proposal(
    job: ParsedJob, one_line: str | None, row: dict[str, Any]
) -> ProposalComparable | None:
    """Same shape as score_entry, over a rag_index row: the job's skills meet
    the past job's skills and the Lead's Tools; prose meets title, industry,
    job type and the operator's own copied text."""
    job_skills, job_keywords = _job_terms(job, one_line)
    stack: list[str] = list(row.get("skills") or []) + _split_tools(row.get("tools"))
    row_tech = tech_terms(stack)
    row_text = " ".join(
        filter(
            None,
            [
                row.get("job_title"),
                row.get("industry"),
                row.get("job_type"),
                row.get("proposal_excerpt"),
            ],
        )
    )
    row_keywords = tokens(row_text) | row_tech

    shared_tech_norm = job_skills & row_tech
    shared_tech = sorted(
        {s for s in stack if expand(s) & shared_tech_norm}, key=str.lower
    )
    shared_tech_norm |= job_skills & row_keywords
    shared_terms = sorted((job_keywords & row_keywords) - shared_tech_norm)
    if (
        len(shared_tech_norm) < MIN_TECH_OVERLAP
        and len(shared_terms) < MIN_KEYWORD_OVERLAP
    ):
        return None

    industry_bonus = 1.0 if tokens(row.get("industry")) & job_keywords else 0.0
    score = 2.0 * len(shared_tech_norm) + 0.5 * min(len(shared_terms), 10)
    return ProposalComparable(
        proposal_id=row["proposal_id"],
        job_title=row.get("job_title"),
        outcome=row["outcome"],
        lost_reason=row.get("lost_reason"),
        industry=row.get("industry"),
        job_type=row.get("job_type"),
        score=round(score + industry_bonus, 2),
        shared_tech=shared_tech,
        shared_terms=shared_terms[:8],
        decided_at=row.get("decided_at"),
    )


def find_proposal_comparables(
    job: ParsedJob, one_line: str | None, rows: list[dict[str, Any]]
) -> list[ProposalComparable]:
    matches = [c for r in rows if (c := score_proposal(job, one_line, r))]
    matches.sort(key=lambda c: (-c.score, (c.job_title or "").lower()))
    return matches[:MAX_COMPARABLES]


def outcome_evidence(
    comparables: list[ProposalComparable], indexed_count: int
) -> OutcomeEvidence:
    won = sum(1 for c in comparables if c.outcome == "won")
    withdrawn = sum(1 for c in comparables if c.outcome == "withdrawn")
    lost_bid = sum(
        1
        for c in comparables
        if c.outcome == "lost" and c.lost_reason in ("hired_other", "job_closed")
    )
    lost_not_worth = sum(
        1
        for c in comparables
        if c.outcome == "lost" and c.lost_reason in ("junk_lead", "not_qualified")
    )
    n = len(comparables)
    if indexed_count == 0:
        label = "No proposal outcomes recorded yet"
    elif n == 0:
        label = f"No comparable past proposals (of {indexed_count} with an outcome)"
    else:
        parts = []
        if won:
            parts.append(f"{won} won")
        if lost_bid:
            parts.append(f"{lost_bid} lost")
        if lost_not_worth:
            parts.append(f"{lost_not_worth} judged not worth bidding")
        if withdrawn:
            parts.append(f"{withdrawn} withdrawn")
        label = f"{n} comparable past proposal{'s' if n != 1 else ''}: " + ", ".join(
            parts
        )
        if indexed_count < MIN_OUTCOMES_FOR_VERDICT:
            label += " (too few outcomes yet to read anything into)"
    return OutcomeEvidence(
        indexed=indexed_count,
        comparable=n,
        won=won,
        lost_bid=lost_bid,
        lost_not_worth=lost_not_worth,
        withdrawn=withdrawn,
        label=label,
        verdict_allowed=indexed_count >= MIN_OUTCOMES_FOR_VERDICT,
    )


def match_strength(comparables: list[Comparable], history_count: int) -> MatchStrength:
    n = len(comparables)
    if history_count == 0:
        level, label = "none_history", "No work history yet — add projects to compare"
    elif n == 0:
        level, label = "none_comparable", "No comparable work history"
    elif n == 1:
        level, label = "thin", "Thin evidence: 1 comparable project"
    elif n <= 3:
        level, label = "some", f"{n} comparable projects"
    else:
        level, label = "strong", f"{n} comparable projects"
    return MatchStrength(
        level=level, comparable_count=n, history_count=history_count, label=label
    )
