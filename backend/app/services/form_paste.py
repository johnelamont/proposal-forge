"""Pull the client's questions out of a pasted Upwork apply form.

Deterministic: a question is a line ending in "?" or a line under a
"questions" heading. Numbering and bullets are stripped; duplicates of
questions already known are dropped. Nothing else from the form is kept.
"""

from __future__ import annotations

import re

HEADING = re.compile(r"questions?\s*:?$", re.I)
LEADER = re.compile(r"^\s*(?:\d+[.)]|[-*•])\s*")
NOISE = re.compile(
    r"^(cover letter|attachments?|add attachment|terms|bid|your bid|"
    r"total price|how long will this project take|include a cover letter)",
    re.I,
)


def extract_questions(form_paste: str, known: list[str]) -> list[str]:
    seen = {q.strip().lower() for q in known}
    out: list[str] = []
    in_block = False
    for raw in form_paste.replace("\r\n", "\n").split("\n"):
        line = LEADER.sub("", raw).strip()
        if not line:
            continue
        if HEADING.search(line) and len(line) < 60:
            in_block = True
            continue
        is_question = line.endswith("?") or (in_block and len(line) > 15)
        if NOISE.match(line):
            in_block = False
            continue
        if is_question and line.lower() not in seen:
            seen.add(line.lower())
            out.append(line)
    return out
