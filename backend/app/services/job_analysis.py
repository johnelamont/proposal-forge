"""F1 orchestration: run both parser layers and merge them.

Conflicts between Upwork's structured fields and the client's prose are
listed, never resolved (R8). The deterministic result is always kept, even
when the Claude layer fails.
"""

from __future__ import annotations

from app.models.job import (
    AiFailure,
    AiReading,
    Conflict,
    JobAnalysis,
    ParsedJob,
    PaymentType,
    Question,
)
from app.services.claude import ClaudeReader, ReadingInput
from app.services.job_parser import parse_job_post


def reading_input(parsed: ParsedJob) -> ReadingInput:
    """The R5 boundary: build exactly what Claude is allowed to see."""
    return ReadingInput(
        title=parsed.title,
        description=parsed.description,
        skills=parsed.skills,
        upwork_questions=[q.text for q in parsed.questions if q.source == "upwork"],
    )


def find_conflicts(parsed: ParsedJob, ai: AiReading | None) -> list[Conflict]:
    conflicts: list[Conflict] = []
    if ai is None or ai.budget_statement is None:
        return conflicts
    stated = ai.budget_statement.model
    upwork = parsed.engagement.payment_type
    if stated != "unstated" and upwork is not None and stated != upwork.value:
        upwork_label = upwork.value
        if upwork == PaymentType.HOURLY and parsed.engagement.hourly_rate_max:
            upwork_label += (
                f" ${parsed.engagement.hourly_rate_min}"
                f"-${parsed.engagement.hourly_rate_max}/hr"
            )
        elif upwork == PaymentType.FIXED and parsed.engagement.fixed_budget:
            upwork_label += f" ${parsed.engagement.fixed_budget}"
        conflicts.append(
            Conflict(
                field="payment_type",
                upwork_value=upwork_label,
                description_value=stated
                + (
                    f" ({ai.budget_statement.amount_raw})"
                    if ai.budget_statement.amount_raw
                    else ""
                ),
                evidence=ai.budget_statement.amount_raw,
            )
        )
    return conflicts


def merge(parsed: ParsedJob, ai_result: AiReading | AiFailure | None) -> JobAnalysis:
    ai = ai_result if isinstance(ai_result, AiReading) else None
    failure = ai_result if isinstance(ai_result, AiFailure) else None

    if ai is not None:
        existing = {q.text.strip().lower() for q in parsed.questions}
        for text in ai.questions_in_description:
            if text.strip().lower() not in existing:
                parsed.questions.append(Question(text=text, source="description"))

    if not parsed.recognised:
        status = "unrecognised"
    elif ai is None:
        status = "ai_failed"
    else:
        status = "ok"

    return JobAnalysis(
        parsed=parsed,
        ai=ai,
        ai_failure=failure,
        conflicts=find_conflicts(parsed, ai),
        parse_status=status,
    )


def analyse_job_post(raw: str, reader: ClaudeReader) -> JobAnalysis:
    parsed = parse_job_post(raw)
    if not parsed.recognised:
        return merge(
            parsed,
            AiFailure(
                kind="skipped",
                message="This doesn't look like an Upwork job post.",
            ),
        )
    return merge(parsed, reader.read_description(reading_input(parsed)))


def reread(parsed: ParsedJob, reader: ClaudeReader) -> JobAnalysis:
    """Retry only the Claude layer on an already-parsed job."""
    parsed.questions = [q for q in parsed.questions if q.source == "upwork"]
    return merge(parsed, reader.read_description(reading_input(parsed)))
