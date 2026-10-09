"""Claude layer: structured extraction with every failure made explicit.

`structured_call` is the one place the Anthropic SDK is invoked. It returns
either a validated Pydantic model or an `AiFailure` (R8: error, empty,
malformed, refusal, skipped). Features build small wrappers on it that define
exactly what text crosses the R5 boundary.

F1's `ClaudeReader` lives here; F5's extractor is in
`work_history_extractor.py`.
"""

from __future__ import annotations

import logging
from typing import Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from app.models.job import AiFailure, AiReading

log = logging.getLogger(__name__)


class _ParseCapable(Protocol):
    """The slice of the Anthropic client we use; lets tests substitute a fake."""

    class messages:  # noqa: N801 - mirrors the SDK attribute name
        @staticmethod
        def parse(**kwargs): ...


ClaudeClient = anthropic.Anthropic | _ParseCapable


def build_client(api_key: str) -> anthropic.Anthropic | None:
    """None when no key is configured: callers report `skipped`, not a crash."""
    return anthropic.Anthropic(api_key=api_key, max_retries=2) if api_key else None


def structured_call[T: BaseModel](
    client: ClaudeClient | None,
    *,
    model: str,
    system: str,
    user_text: str,
    schema: type[T],
    max_tokens: int = 4096,
    timeout_seconds: float = 60.0,
) -> T | AiFailure:
    """One Claude request that must return JSON matching `schema`."""
    if client is None:
        return AiFailure(
            kind="skipped",
            message="ANTHROPIC_API_KEY is not configured on the server.",
        )
    try:
        response = client.messages.parse(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_text}],
            output_format=schema,
            timeout=timeout_seconds,
        )
    except anthropic.RateLimitError:
        return AiFailure(kind="error", message="Claude rate limit; try again.")
    except anthropic.APIStatusError as e:
        # The API's own explanation is not sensitive and is the only way to
        # tell a bad request from a billing or model problem. Keep it short.
        detail = (e.message or "").strip().replace("\n", " ")[:300]
        log.warning("claude status error %s: %s", e.status_code, detail)
        return AiFailure(
            kind="error",
            message=f"Claude API error ({e.status_code}): {detail or 'no detail'}",
        )
    except anthropic.APIConnectionError:
        return AiFailure(kind="error", message="Could not reach the Claude API.")
    except (ValidationError, ValueError) as e:
        # The SDK raises when the model's output is not valid JSON for the
        # schema. Log the class, not the content.
        log.warning("claude malformed output: %s", type(e).__name__)
        return AiFailure(kind="malformed", message="Claude returned malformed data.")

    stop_reason = getattr(response, "stop_reason", None)
    if stop_reason == "refusal":
        return AiFailure(kind="refusal", message="Claude declined this request.")
    if stop_reason == "max_tokens":
        return AiFailure(kind="malformed", message="Claude's response was cut off.")

    parsed = getattr(response, "parsed_output", None)
    if parsed is None:
        return AiFailure(kind="empty", message="Claude returned no data.")
    if isinstance(parsed, schema):
        return parsed
    try:
        return schema.model_validate(parsed)
    except ValidationError:
        return AiFailure(kind="malformed", message="Claude returned malformed data.")


# ---------------------------------------------------------------------------
# F1: read a job description
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You read public Upwork job advertisements that a freelancer has pasted in, \
and extract what the client is asking for so the freelancer can decide \
whether to bid and what to write.

Work only from the text given. Do not invent requirements, budgets, or \
timelines that are not stated. Quote the client's own words where a field \
asks for a statement. For each field, report a confidence between 0 and 1 \
reflecting how directly the text supports your answer; use low values when \
you are inferring.

- one_line: what the client actually wants, in one sentence.
- deliverables: concrete things to be built or delivered.
- requirements: must-haves the client states about the freelancer (tools, \
experience, timezone overlap, NDA, examples to share).
- questions_in_description: questions the client asks applicants to answer \
inside the description (for example under "When you apply, please tell us"). \
Do not repeat the Upwork screening questions you are given separately.
- budget_statement: only if the description itself states a payment model \
or amount. model is "hourly", "fixed", or "unstated"; list milestones if given.
- timeline_statement: only if the description states a deadline or duration.
- red_flags: things a careful freelancer would want to notice, such as a \
very low budget for the described scope, vague or contradictory scope, \
requests for unpaid work, or signs the client is not ready to start.
- sensitive_data_domain: flag true if the work would handle regulated or \
special-category personal data (health, immigration or legal status, \
financial records, children), with a short reason.
"""


class ReadingInput:
    """Exactly what crosses the R5 boundary for F1. Nothing else is sent."""

    def __init__(
        self,
        title: str | None,
        description: str,
        skills: list[str],
        upwork_questions: list[str],
    ) -> None:
        self.title = title
        self.description = description
        self.skills = skills
        self.upwork_questions = upwork_questions

    def to_prompt(self) -> str:
        parts = [
            f"Title: {self.title or '(none)'}",
            "",
            "Description:",
            self.description,
        ]
        if self.skills:
            parts += ["", "Skills listed: " + ", ".join(self.skills)]
        if self.upwork_questions:
            parts += ["", "Upwork screening questions (already captured):"]
            parts += [f"- {q}" for q in self.upwork_questions]
        return "\n".join(parts)


class ClaudeReader:
    def __init__(
        self,
        client: ClaudeClient | None,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def read_description(self, inp: ReadingInput) -> AiReading | AiFailure:
        if not inp.description.strip():
            return AiFailure(kind="skipped", message="The paste has no description.")
        return structured_call(
            self._client,
            model=self._model,
            system=SYSTEM_PROMPT,
            user_text=inp.to_prompt(),
            schema=AiReading,
            timeout_seconds=self._timeout,
        )


def build_reader(api_key: str, model: str) -> ClaudeReader:
    return ClaudeReader(client=build_client(api_key), model=model)
