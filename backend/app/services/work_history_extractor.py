"""F5: read dropped project files and propose a work-history record.

R5: only files that passed `file_rules.screen` are sent, verbatim, with their
names. R8: failures come back as `AiFailure`; the operator can still fill
the form by hand.
"""

from __future__ import annotations

from app.models.job import AiFailure
from app.models.work_history import DroppedFile, Extraction
from app.services.claude import ClaudeClient, build_client, structured_call

SYSTEM_PROMPT = """\
You read the documentation files of a software project that a freelance \
consultant completed, and summarise the project as an entry in their work \
history. The entry will later help them judge whether a new job is similar \
to past work and write proposals that cite real experience.

Work only from the text given. Do not invent technologies, outcomes or \
clients that are not stated. For each field, report a confidence between 0 \
and 1 reflecting how directly the text supports it.

- name: a short project name (from the title if there is one).
- summary: one paragraph, in plain language, of what was built and why.
- tech_stack: products, languages, frameworks and services actually used.
- vertical: the client's industry or domain (e.g. "mortgage brokerage", \
"immigration law"), or null if unstated.
- project_type: the kind of work (e.g. "CRM integration", "dashboard", \
"data migration", "automation"), or null.
- complexity: low, medium or high, with a one-sentence reason: consider the \
number of systems involved, custom logic, data volume, and risk.
- role: what the consultant did (e.g. "sole developer", "architect"), or null.
- outcomes: concrete results stated in the text (what works now, time saved, \
errors removed). Only what is stated.
- client_name_detected: the client's name if the text names one, else null. \
Report it so the consultant can decide whether it may be used; do not \
assume it may.
- duration_hint: any stated timeframe, verbatim, else null.
"""


def files_to_prompt(files: list[DroppedFile]) -> str:
    """Exactly what crosses the R5 boundary for F5."""
    parts: list[str] = []
    for f in files:
        parts.append(f"=== file: {f.name} ===")
        parts.append(f.content.strip())
        parts.append("")
    return "\n".join(parts).strip()


class WorkHistoryExtractor:
    def __init__(
        self,
        client: ClaudeClient | None,
        model: str,
        timeout_seconds: float = 90.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def extract(self, files: list[DroppedFile]) -> Extraction | AiFailure:
        if not files:
            return AiFailure(kind="skipped", message="No usable files were provided.")
        return structured_call(
            self._client,
            model=self._model,
            system=SYSTEM_PROMPT,
            user_text=files_to_prompt(files),
            schema=Extraction,
            max_tokens=4096,
            timeout_seconds=self._timeout,
        )


def build_extractor(api_key: str, model: str) -> WorkHistoryExtractor:
    return WorkHistoryExtractor(client=build_client(api_key), model=model)
