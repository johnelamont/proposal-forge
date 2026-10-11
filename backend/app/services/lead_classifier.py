"""F6: map a job to Zoho's Industry and Job_Type picklists, plus Tools.

The output schema is built from picklists.json so Claude can only return
values Zoho accepts; the confidence per field drives the Rule 3 flags.
R5: the prompt carries the job title, description, skills and F1's reading —
nothing about the client's statistics, the operator, or past work.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, create_model

from app.config.picklists import INDUSTRY, JOB_TYPE
from app.models.job import AiFailure, JobAnalysis
from app.models.zoho import Classification, ClassificationConfidence
from app.services.claude import ClaudeClient, build_client, structured_call

SYSTEM_PROMPT = """\
You categorise an Upwork job post for a consultant's CRM. Choose exactly one \
Industry (the client's sector) and one Job_Type (the kind of engagement) from \
the allowed values, and list the tools, products and technologies the job \
involves as a short comma-separated string (under 255 characters).

Work only from the text given. If no value fits well, choose "Other" and \
give it a low confidence rather than forcing a poor match. Report a \
confidence from 0 to 1 for each field reflecting how clearly the text \
supports it.
"""

IndustryLiteral = Literal.__getitem__(tuple(INDUSTRY))  # type: ignore[valid-type]
JobTypeLiteral = Literal.__getitem__(tuple(JOB_TYPE))  # type: ignore[valid-type]

ClassificationOut = create_model(
    "ClassificationOut",
    industry=(IndustryLiteral, ...),
    job_type=(JobTypeLiteral, ...),
    tools=(str, Field(max_length=255)),
    confidence=(ClassificationConfidence, ...),
)


def classification_prompt(analysis: JobAnalysis) -> str:
    job = analysis.parsed
    parts = [f"JOB: {job.title or '(untitled)'}"]
    if job.skills:
        parts.append("Skills listed: " + ", ".join(job.skills))
    if job.client.industry:
        parts.append(f"Upwork's industry tag for the client: {job.client.industry}")
    parts += ["", "Description:", job.description.strip()]
    if analysis.ai:
        parts += ["", "Summary: " + analysis.ai.one_line]
        if analysis.ai.deliverables:
            parts += ["Deliverables:"] + [f"- {d}" for d in analysis.ai.deliverables]
    parts += [
        "",
        "Allowed Industry values: " + "; ".join(INDUSTRY),
        "Allowed Job_Type values: " + "; ".join(JOB_TYPE),
    ]
    return "\n".join(parts)


class LeadClassifier:
    def __init__(
        self, client: ClaudeClient | None, model: str, timeout_seconds: float = 60.0
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def classify(self, analysis: JobAnalysis) -> Classification | AiFailure:
        result = structured_call(
            self._client,
            model=self._model,
            system=SYSTEM_PROMPT,
            user_text=classification_prompt(analysis),
            schema=ClassificationOut,
            max_tokens=1024,
            timeout_seconds=self._timeout,
        )
        if isinstance(result, AiFailure):
            return result
        return Classification.model_validate(result.model_dump())


def build_classifier(api_key: str, model: str) -> LeadClassifier:
    return LeadClassifier(client=build_client(api_key), model=model)
