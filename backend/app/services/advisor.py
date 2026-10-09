"""F2 orchestration: comparables → Claude's fit reading → Advisory.

R5: Claude sees the job text and the comparable entries' summaries only —
never client names, source files, or entries that did not match.
R8: no comparables → no call; any Claude failure is carried in the Advisory.
"""

from __future__ import annotations

from typing import Any

from app.models.advisory import Advisory, AdvisoryReading, Comparable
from app.models.job import AiFailure, JobAnalysis
from app.services.claude import ClaudeClient, build_client, structured_call
from app.services.matcher import find_comparables, match_strength

SYSTEM_PROMPT = """\
You advise a freelance consultant on whether a job they are considering is \
in their wheelhouse, using only two things: the job post, and summaries of \
the consultant's past projects that a matching step found comparable.

Work only from the text given. Do not invent past work, skills, or results. \
There is no win/loss history yet; judge fit on the work itself.

- fit: strong (they have done this kind of work with these tools), partial \
(real overlap but notable gaps), weak (only loose similarity), none.
- reasons: the specific overlaps between the job and the past projects.
- gaps: what the job needs that the past projects do not show. Be concrete; \
these help the consultant decide and write honestly.
- cite: which past projects are worth mentioning in a proposal for this job, \
by entry_id and name, with one sentence each on why. Only genuinely relevant \
ones; an empty list is fine.
- angle: one sentence on how the consultant could position themselves, \
given the overlaps and gaps. No marketing language.
- confidence: 0 to 1 per field, lower when inferring.
"""

# Work-history fields that may cross the R5 boundary. client_name,
# source_files, ai_extraction and dates are deliberately absent.
ENTRY_FIELDS = (
    "name",
    "summary",
    "tech_stack",
    "vertical",
    "project_type",
    "complexity",
    "outcomes",
    "budget_band",
)


def build_prompt(
    analysis: JobAnalysis,
    comparables: list[Comparable],
    history: list[dict[str, Any]],
) -> str:
    job = analysis.parsed
    parts = [f"JOB: {job.title or '(untitled)'}", ""]
    if analysis.ai:
        parts += [f"In one line: {analysis.ai.one_line}", ""]
        if analysis.ai.deliverables:
            parts += ["Deliverables:"] + [f"- {d}" for d in analysis.ai.deliverables]
            parts.append("")
    if job.skills:
        parts += ["Skills listed: " + ", ".join(job.skills), ""]
    parts += ["Description:", job.description.strip(), "", "COMPARABLE PAST PROJECTS:"]

    by_id = {e["id"]: e for e in history}
    for c in comparables:
        e = by_id[c.entry_id]
        parts += ["", f"--- entry_id: {c.entry_id} ---"]
        for field in ENTRY_FIELDS:
            value = e.get(field)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            parts.append(f"{field}: {value}")
        if c.shared_tech or c.shared_terms:
            parts.append("matched on: " + ", ".join(c.shared_tech + c.shared_terms[:5]))
    return "\n".join(parts)


class Advisor:
    def __init__(
        self,
        client: ClaudeClient | None,
        model: str,
        timeout_seconds: float = 90.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def advise(self, analysis: JobAnalysis, history: list[dict[str, Any]]) -> Advisory:
        one_line = analysis.ai.one_line if analysis.ai else None
        comparables = find_comparables(analysis.parsed, one_line, history)
        strength = match_strength(comparables, len(history))

        if not comparables:
            return Advisory(
                comparables=[], match_strength=strength, reading=None, failure=None
            )

        result = structured_call(
            self._client,
            model=self._model,
            system=SYSTEM_PROMPT,
            user_text=build_prompt(analysis, comparables, history),
            schema=AdvisoryReading,
            timeout_seconds=self._timeout,
        )
        reading = result if isinstance(result, AdvisoryReading) else None
        failure = result if isinstance(result, AiFailure) else None
        if reading is not None:
            # Claude may only cite entries it was shown.
            allowed = {c.entry_id for c in comparables}
            reading.cite = [c for c in reading.cite if c.entry_id in allowed]
        return Advisory(
            comparables=comparables,
            match_strength=strength,
            reading=reading,
            failure=failure,
        )


def build_advisor(api_key: str, model: str) -> Advisor:
    return Advisor(client=build_client(api_key), model=model)
