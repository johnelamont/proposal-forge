"""F3: draft and refine proposal text with Claude, under hard rules.

R5: the prompt carries the job (title, description, skills, questions), F1's
reading, F2's angle and cited projects (allow-listed fields), and the
operator's profile. Never client names, dropped files, client statistics or
other jobs. R8: failures come back as AiFailure; nothing partial is shown as
complete. The greeting and sign-off are applied by code, not trusted to the
model; never-claim phrases are checked and reported, never silently edited.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any

from app.models.advisory import Advisory
from app.models.job import AiFailure, JobAnalysis
from app.models.proposal import (
    AiMeta,
    Answer,
    DraftOutput,
    Profile,
    RefineOutput,
    Sections,
)
from app.services.claude import ClaudeClient, build_client, structured_call

SYSTEM_PROMPT = """\
You write Upwork proposals for an independent consultant, in their voice, to \
be read by the client who posted the job.

Hard rules:
- Work only from the material given. Never invent experience, clients, \
results, certifications or tools. If the job asks for something the \
consultant's past work does not show, say what they have done that is \
closest, honestly.
- The consultant is independent. Never describe them as a partner, member, \
reseller, certified or affiliated with any company or programme. If the job \
requires such status, say plainly that they do not hold it.
- Past projects may be mentioned only as described in COMPARABLE PAST \
PROJECTS, and never by client name.
- Answer every question under QUESTIONS directly, one answer per question, \
in the order given, starting with the substance (not "Great question").
- Write plainly and completely: short paragraphs, specific, no marketing \
language, no exclamation marks, no "I am excited", no bullet lists unless \
the question asks for a list. There is no length limit; say what needs \
saying and stop.
- Do not write a greeting or a sign-off; the consultant's own are added \
afterwards. Begin the cover letter with the first sentence of substance.
- Follow TONE NOTES where given.

Return: cover_letter (the body only), answers (one per question, with the \
question text repeated), and a confidence from 0 to 1 for each part.
"""

REFINE_PROMPT = """\
You revise one section of an Upwork proposal for an independent consultant, \
following an instruction from them. Keep everything true to the original \
material: never add experience, clients, results or affiliations that are \
not in it. The consultant is independent; never describe them as a partner, \
member, reseller or certified. Plain language, no marketing tone, no \
exclamation marks. Do not add a greeting or sign-off. Return the revised \
section only, and a confidence from 0 to 1.
"""

# Fields of a cited work-history entry that may cross the R5 boundary.
ENTRY_FIELDS = (
    "name",
    "summary",
    "tech_stack",
    "vertical",
    "project_type",
    "complexity",
    "outcomes",
)

GREETING_LINE = re.compile(r"^\s*(hi|hello|hey|dear|greetings)\b[^\n]*\n+", re.I)
SIGN_OFF_BLOCK = re.compile(
    r"\n+\s*(kind regards|regards|best regards|warm regards|sincerely|thanks|"
    r"thank you|best|cheers|all the best)[,.!]?\s*(\n+[^\n]{0,80})?\s*$",
    re.I,
)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def frame(body: str, profile: Profile) -> str:
    """Apply the operator's greeting and sign-off, replacing any the model
    produced despite the rules. The frame is the operator's, not Claude's."""
    text = body.strip()
    text = GREETING_LINE.sub("", text, count=1)
    text = SIGN_OFF_BLOCK.sub("", text, count=1).strip()
    greeting = profile.greeting.strip()
    sign_off = profile.sign_off.strip()
    name = profile.signature_name.strip()
    return f"{greeting}\n\n{text}\n\n{sign_off}\n{name}"


def never_claim_warnings(texts: list[str], profile: Profile) -> list[str]:
    found: list[str] = []
    for phrase in profile.never_claim:
        p = phrase.strip()
        if p and any(p.lower() in t.lower() for t in texts):
            found.append(f'Draft mentions "{p}" — check it does not claim it.')
    return found


def questions_for(analysis: JobAnalysis, extra_questions: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for q in [q.text for q in analysis.parsed.questions] + list(extra_questions):
        key = q.strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(q.strip())
    return out


def build_draft_prompt(
    analysis: JobAnalysis,
    advisory: Advisory | None,
    cited: list[dict[str, Any]],
    profile: Profile,
    questions: list[str],
) -> str:
    job = analysis.parsed
    parts = ["CONSULTANT", profile.positioning.strip() or "(no positioning given)"]
    if profile.tone_notes.strip():
        parts += ["", "TONE NOTES", profile.tone_notes.strip()]
    parts += ["", f"JOB: {job.title or '(untitled)'}"]
    if job.skills:
        parts.append("Skills listed: " + ", ".join(job.skills))
    parts += ["", "Description:", job.description.strip()]
    if analysis.ai:
        parts += ["", "What the client wants (summary): " + analysis.ai.one_line]
        if analysis.ai.deliverables:
            parts += ["Deliverables:"] + [f"- {d}" for d in analysis.ai.deliverables]
        if analysis.ai.requirements:
            parts += ["Requirements:"] + [f"- {r}" for r in analysis.ai.requirements]
    if advisory and advisory.reading:
        parts += [
            "",
            "ANGLE (from the consultant's own review): " + advisory.reading.angle,
        ]
        if advisory.reading.gaps:
            parts += ["Known gaps to handle honestly:"]
            parts += [f"- {g}" for g in advisory.reading.gaps]
    parts += ["", "COMPARABLE PAST PROJECTS"]
    if not cited:
        parts.append("(none — do not claim any)")
    for entry in cited:
        parts.append("")
        for field in ENTRY_FIELDS:
            value = entry.get(field)
            if value in (None, "", []):
                continue
            if isinstance(value, list):
                value = ", ".join(str(v) for v in value)
            parts.append(f"{field}: {value}")
    parts += ["", "QUESTIONS"]
    if questions:
        parts += [f"{i + 1}. {q}" for i, q in enumerate(questions)]
    else:
        parts.append("(none)")
    return "\n".join(parts)


class Drafter:
    def __init__(
        self,
        client: ClaudeClient | None,
        model: str,
        timeout_seconds: float = 180.0,
    ) -> None:
        self._client = client
        self._model = model
        self._timeout = timeout_seconds

    def draft(
        self,
        analysis: JobAnalysis,
        advisory: Advisory | None,
        cited: list[dict[str, Any]],
        profile: Profile,
        questions: list[str],
    ) -> tuple[Sections, AiMeta]:
        """A full draft. On failure the sections are empty and the failure is
        in the meta: the caller stores it as a version so the operator sees it."""
        result = structured_call(
            self._client,
            model=self._model,
            system=SYSTEM_PROMPT,
            user_text=build_draft_prompt(analysis, advisory, cited, profile, questions),
            schema=DraftOutput,
            max_tokens=16000,
            timeout_seconds=self._timeout,
        )
        if isinstance(result, AiFailure):
            return (
                Sections(
                    cover_letter=None,
                    answers=[Answer(question=q, answer="") for q in questions],
                ),
                AiMeta(model=self._model, failure=result),
            )

        answers = _align_answers(result.answers, questions)
        cover = frame(result.cover_letter, profile)
        warnings = never_claim_warnings([cover] + [a.answer for a in answers], profile)
        if len(result.answers) != len(questions):
            warnings.append(
                f"Claude returned {len(result.answers)} answer(s) for "
                f"{len(questions)} question(s); unmatched questions are blank."
            )
        return (
            Sections(cover_letter=cover, answers=answers),
            AiMeta(
                model=self._model,
                confidence=result.confidence.model_dump(),
                warnings=warnings,
            ),
        )

    def refine(
        self, current: str, instruction: str, profile: Profile, is_cover: bool
    ) -> tuple[str | None, AiMeta]:
        body = current
        if is_cover:
            body = GREETING_LINE.sub("", body.strip(), count=1)
            body = SIGN_OFF_BLOCK.sub("", body, count=1).strip()
        result = structured_call(
            self._client,
            model=self._model,
            system=REFINE_PROMPT,
            user_text=(
                f"CONSULTANT\n{profile.positioning.strip()}\n\n"
                f"INSTRUCTION\n{instruction.strip()}\n\nSECTION\n{body}"
            ),
            schema=RefineOutput,
            max_tokens=8000,
            timeout_seconds=self._timeout,
        )
        if isinstance(result, AiFailure):
            return None, AiMeta(model=self._model, failure=result)
        text = frame(result.content, profile) if is_cover else result.content.strip()
        return text, AiMeta(
            model=self._model,
            confidence={"refined": result.confidence},
            warnings=never_claim_warnings([text], profile),
        )


def _align_answers(returned: list[Answer], questions: list[str]) -> list[Answer]:
    """Keep the operator's question order and text; take answers by position,
    blank where the model gave none."""
    out: list[Answer] = []
    for i, q in enumerate(questions):
        answer = returned[i].answer.strip() if i < len(returned) else ""
        out.append(Answer(question=q, answer=answer))
    return out


def build_drafter(api_key: str, model: str) -> Drafter:
    return Drafter(client=build_client(api_key), model=model)
