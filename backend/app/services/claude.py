"""Claude layer for F1: read the job description and return structured JSON.

R5: the only text sent is the title, the description, the skills list and any
Upwork-native screening questions. Client statistics and history never pass
through here. R8: every failure is returned as an `AiFailure`, never raised
past this module and never turned into a guess.
"""

from __future__ import annotations

import logging
from typing import Protocol

import anthropic
from pydantic import ValidationError

from app.models.job import AiFailure, AiReading

log = logging.getLogger(__name__)

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
    """Exactly what crosses the R5 boundary. Nothing else is sent."""

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


class _ParseCapable(Protocol):
    """The slice of the Anthropic client we use; lets tests substitute a fake."""

    class messages:  # noqa: N801 - mirrors the SDK attribute name
        @staticmethod
        def parse(**kwargs): ...


class ClaudeReader:
    def __init__(
        self,
        client: anthropic.Anthropic | _ParseCapable | None,
        model: str,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def read_description(self, inp: ReadingInput) -> AiReading | AiFailure:
        if self._client is None:
            return AiFailure(
                kind="skipped",
                message="ANTHROPIC_API_KEY is not configured on the server.",
            )
        if not inp.description.strip():
            return AiFailure(kind="skipped", message="The paste has no description.")

        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=4096,
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": inp.to_prompt()}],
                output_format=AiReading,
                timeout=self._timeout,
            )
        except anthropic.RateLimitError:
            return AiFailure(kind="error", message="Claude rate limit; try again.")
        except anthropic.APIStatusError as e:
            log.warning("claude status error %s", e.status_code)
            return AiFailure(
                kind="error", message=f"Claude API error ({e.status_code})."
            )
        except anthropic.APIConnectionError:
            return AiFailure(kind="error", message="Could not reach the Claude API.")
        except (ValidationError, ValueError) as e:
            # The SDK raises when the model's output is not valid JSON for the
            # schema. Log the class, not the content.
            log.warning("claude malformed output: %s", type(e).__name__)
            return AiFailure(
                kind="malformed", message="Claude returned malformed data."
            )

        if getattr(response, "stop_reason", None) == "refusal":
            return AiFailure(kind="refusal", message="Claude declined this request.")
        if getattr(response, "stop_reason", None) == "max_tokens":
            return AiFailure(kind="malformed", message="Claude's response was cut off.")

        parsed = getattr(response, "parsed_output", None)
        if parsed is None:
            return AiFailure(kind="empty", message="Claude returned no data.")
        if not isinstance(parsed, AiReading):
            try:
                parsed = AiReading.model_validate(parsed)
            except ValidationError:
                return AiFailure(
                    kind="malformed", message="Claude returned malformed data."
                )
        return parsed


def build_reader(api_key: str, model: str) -> ClaudeReader:
    client = anthropic.Anthropic(api_key=api_key, max_retries=2) if api_key else None
    return ClaudeReader(client=client, model=model)
