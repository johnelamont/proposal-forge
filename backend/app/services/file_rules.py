"""R5 gate for F5: which dropped files may be sent to Claude.

Everything here is deliberately conservative. A refused file is reported
back with its reason; nothing is silently dropped. Applied on `extract` and
again on save (defence in depth, since the browser applies the same rules).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from app.models.work_history import AcceptedFile, DroppedFile, RefusedFile

MAX_FILES = 5
MAX_BYTES = 200_000  # per file
MAX_TOTAL_BYTES = 400_000

TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".rst", ".adoc"}
MANIFEST_NAMES = {
    "package.json",
    "pyproject.toml",
    "cargo.toml",
    "go.mod",
    "composer.json",
    "gemfile",
    "setup.py",
    "setup.cfg",
    "pom.xml",
    "build.gradle",
}
MANIFEST_PATTERNS = [
    re.compile(r"^requirements[^/\\]*\.txt$"),
    re.compile(r"\.csproj$"),
]

# (pattern on the lower-cased file name, reason)
REFUSED_NAMES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"^\.env($|\.)"), "environment file"),
    (
        re.compile(r"\.(pem|p12|pfx|key|crt|cer|der|jks|kdbx|ppk)$"),
        "key or certificate",
    ),
    (re.compile(r"^id_(rsa|dsa|ecdsa|ed25519)"), "SSH key"),
    (
        re.compile(r"(^|[._-])(secret|secrets|credential|credentials|token)([._-]|$)"),
        "looks like a credentials file",
    ),
    (re.compile(r"\.(zip|tar|gz|tgz|bz2|7z|rar|xz)$"), "archive"),
    (
        re.compile(r"\.(csv|tsv|xlsx|xls|db|sqlite|sqlite3|parquet|sql|bak|dump)$"),
        "data file",
    ),
    (re.compile(r"\.(json|ya?ml|toml|ini|cfg|conf|xml)$"), "config or data file"),
]

# Content that must never reach a prompt, whatever the file is called.
SECRET_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "contains a private key"),
    (re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}"), "contains an Anthropic API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "contains an AWS access key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"), "contains a GitHub token"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "contains a Slack token"),
]
ASSIGNMENT = re.compile(
    r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|PASSWD|SECRET|API[_-]?KEY|TOKEN)"
    r"[A-Z0-9_]*\s*[:=]\s*['\"]?([^\s'\"#]{8,})"
)
PLACEHOLDER = re.compile(
    r"(?i)^(<.*>|your[-_ ]|xxx|\.\.\.|example|changeme|change-me|placeholder|"
    r"redacted|\$\{|\$[A-Z_]|\*\*\*|todo|tbd|none|null|dummy|sample|test)"
)


@dataclass
class Screened:
    accepted: list[AcceptedFile] = field(default_factory=list)
    refused: list[RefusedFile] = field(default_factory=list)
    texts: list[DroppedFile] = field(default_factory=list)

    @property
    def total_bytes(self) -> int:
        return sum(a.size for a in self.accepted)


def _name_reason(name: str) -> str | None:
    lower = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
    for pattern, reason in REFUSED_NAMES:
        if pattern.search(lower):
            # Manifests are allow-listed before the json/toml/xml refusal.
            if lower in MANIFEST_NAMES or any(
                p.search(lower) for p in MANIFEST_PATTERNS
            ):
                return None
            return reason
    ext = "." + lower.rsplit(".", 1)[-1] if "." in lower else ""
    if ext in TEXT_EXTENSIONS:
        return None
    if lower in MANIFEST_NAMES or any(p.search(lower) for p in MANIFEST_PATTERNS):
        return None
    return "unsupported type (text, Markdown, or a dependency manifest only)"


def _content_reason(content: str) -> str | None:
    if "\x00" in content:
        return "binary content"
    for pattern, reason in SECRET_PATTERNS:
        if pattern.search(content):
            return reason
    for m in ASSIGNMENT.finditer(content):
        value = m.group(1)
        if not PLACEHOLDER.match(value):
            return "contains what looks like a password, key, or token"
    return None


def screen(files: list[DroppedFile]) -> Screened:
    out = Screened()
    for f in files[:MAX_FILES]:
        reason = _name_reason(f.name)
        size = len(f.content.encode("utf-8"))
        if reason is None and size == 0:
            reason = "empty file"
        if reason is None and size > MAX_BYTES:
            reason = f"larger than {MAX_BYTES // 1000} KB"
        if reason is None and out.total_bytes + size > MAX_TOTAL_BYTES:
            reason = f"total exceeds {MAX_TOTAL_BYTES // 1000} KB"
        if reason is None:
            reason = _content_reason(f.content)
        if reason is not None:
            out.refused.append(RefusedFile(name=f.name, reason=reason))
            continue
        digest = hashlib.sha256(f.content.encode("utf-8")).hexdigest()
        out.accepted.append(AcceptedFile(name=f.name, size=size, sha256=digest))
        out.texts.append(f)
    for f in files[MAX_FILES:]:
        out.refused.append(
            RefusedFile(name=f.name, reason=f"more than {MAX_FILES} files")
        )
    return out
