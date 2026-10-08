"""Every refusal rule in the F5 file gate has a test; so does every accept."""

import pytest

from app.models.work_history import DroppedFile
from app.services.file_rules import MAX_BYTES, MAX_FILES, screen


def f(name: str, content: str = "# Project\n\nA readme.") -> DroppedFile:
    return DroppedFile(name=name, content=content)


# --- accepted -----------------------------------------------------------------


@pytest.mark.parametrize(
    "name",
    [
        "README.md",
        "docs/DESIGN.markdown",
        "notes.txt",
        "guide.rst",
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "requirements-dev.txt",
        "Cargo.toml",
        "go.mod",
        "composer.json",
        "Gemfile",
        "App.csproj",
        "pom.xml",
    ],
)
def test_text_and_manifests_are_accepted(name):
    result = screen([f(name)])
    assert result.refused == []
    assert [a.name for a in result.accepted] == [name]
    assert result.accepted[0].sha256
    assert result.accepted[0].size > 0


def test_readme_with_placeholder_secrets_is_accepted():
    content = (
        "## Setup\n\n"
        "ANTHROPIC_API_KEY=your-api-key-here\n"
        "DATABASE_PASSWORD=<your password>\n"
        "export API_TOKEN=${API_TOKEN}\n"
        "SECRET_KEY=changeme\n"
    )
    assert screen([f("README.md", content)]).refused == []


# --- refused by name ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        (".env", "environment file"),
        (".env.local", "environment file"),
        ("server.pem", "key or certificate"),
        ("id_rsa", "SSH key"),
        ("id_ed25519.pub", "SSH key"),
        ("aws-credentials.txt", "looks like a credentials file"),
        ("secrets.md", "looks like a credentials file"),
        ("site.zip", "archive"),
        ("backup.tar.gz", "archive"),
        ("clients.csv", "data file"),
        ("ledger.xlsx", "data file"),
        ("app.db", "data file"),
        ("dump.sql", "data file"),
        ("config.yaml", "config or data file"),
        ("settings.json", "config or data file"),
        ("photo.png", "unsupported type"),
        ("report.pdf", "unsupported type"),
        ("script.py", "unsupported type"),
    ],
)
def test_refused_names(name, reason):
    result = screen([f(name)])
    assert result.accepted == []
    assert result.refused[0].name == name
    assert result.refused[0].reason.startswith(reason)


# --- refused by content ------------------------------------------------------


@pytest.mark.parametrize(
    ("content", "reason"),
    [
        ("-----BEGIN RSA PRIVATE KEY-----\nabc\n", "contains a private key"),
        ("key: sk-ant-api03-abcdefghijklmnopqrstuvwxyz", "Anthropic API key"),
        ("aws AKIAABCDEFGHIJKLMNOP here", "AWS access key"),
        ("token ghp_abcdefghijklmnopqrstuvwxyz1234", "GitHub token"),
        ("slack xoxb-1234567890-abcdef", "Slack token"),
        ("DB_PASSWORD=Tr0ub4dor&3xyz\n", "password, key, or token"),
        ("api_key = 'a1b2c3d4e5f6g7h8'\n", "password, key, or token"),
        ("binary\x00bytes", "binary content"),
    ],
)
def test_refused_content(content, reason):
    result = screen([f("README.md", content)])
    assert result.accepted == []
    assert reason in result.refused[0].reason


# --- size and count ----------------------------------------------------------


def test_empty_file_is_refused():
    assert screen([f("README.md", "")]).refused[0].reason == "empty file"


def test_oversized_file_is_refused():
    result = screen([f("README.md", "x" * (MAX_BYTES + 1))])
    assert "larger than" in result.refused[0].reason


def test_total_size_cap():
    big = "x" * (MAX_BYTES - 10)
    result = screen([f("a.md", big), f("b.md", big), f("c.md", big)])
    assert len(result.accepted) == 2
    assert "total exceeds" in result.refused[0].reason


def test_file_count_cap():
    files = [f(f"doc{i}.md") for i in range(MAX_FILES + 2)]
    result = screen(files)
    assert len(result.accepted) == MAX_FILES
    assert all("more than" in r.reason for r in result.refused)
    assert len(result.refused) == 2


def test_mixed_batch_reports_both_lists():
    result = screen([f("README.md"), f(".env", "X=1"), f("notes.txt")])
    assert [a.name for a in result.accepted] == ["README.md", "notes.txt"]
    assert [r.name for r in result.refused] == [".env"]
    assert [t.name for t in result.texts] == ["README.md", "notes.txt"]
