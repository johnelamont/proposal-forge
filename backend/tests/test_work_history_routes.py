"""F5 routes with the database and extractor replaced by fakes."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import app
from app.models.job import AiFailure
from app.models.work_history import Extraction
from app.routes.work_history import get_extractor
from app.services.db import DbError
from tests.test_work_history_extractor import GOOD_EXTRACTION

README = "# Velocity sync\n\nSyncs funded deals from Velocity into Zoho CRM."


class FakeDb:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def insert_work_history(self, row):
        now = datetime.now(UTC).isoformat()
        stored = {"id": str(uuid4()), "created_at": now, "updated_at": now, **row}
        self.rows[stored["id"]] = stored
        return stored

    def list_work_history(self):
        keys = (
            "id",
            "name",
            "vertical",
            "tech_stack",
            "complexity",
            "may_name_client",
            "ended",
            "updated_at",
        )
        return [{k: r[k] for k in keys} for r in self.rows.values()]

    def get_work_history(self, entry_id):
        return self.rows.get(entry_id)

    def update_work_history(self, entry_id, patch):
        if entry_id not in self.rows:
            raise DbError(404, "not found")
        self.rows[entry_id].update(patch)
        return self.rows[entry_id]

    def delete_work_history(self, entry_id):
        return self.rows.pop(entry_id, None) is not None


class FakeExtractor:
    def __init__(self, result):
        self.result = result
        self.received: list[list[str]] = []

    def extract(self, files):
        self.received.append([f.name for f in files])
        return self.result


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def extractor():
    return FakeExtractor(Extraction.model_validate(GOOD_EXTRACTION))


@pytest.fixture
def client(db, extractor):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_extractor] = lambda: extractor
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_extract_returns_draft_without_saving(client, db, extractor):
    res = client.post(
        "/api/work-history/extract",
        json={"files": [{"name": "README.md", "content": README}]},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["extraction"]["name"] == "Velocity to Zoho integration"
    assert body["failure"] is None
    assert [a["name"] for a in body["accepted"]] == ["README.md"]
    assert body["refused"] == []
    assert db.rows == {}  # nothing written
    assert extractor.received == [["README.md"]]


def test_extract_screens_files_before_claude(client, extractor):
    res = client.post(
        "/api/work-history/extract",
        json={
            "files": [
                {"name": "README.md", "content": README},
                {"name": ".env", "content": "KEY=value"},
            ]
        },
    )
    body = res.json()
    assert [r["name"] for r in body["refused"]] == [".env"]
    assert extractor.received == [["README.md"]]  # .env never reached it


def test_extract_with_only_refused_files_skips_claude(client, extractor):
    res = client.post(
        "/api/work-history/extract",
        json={"files": [{"name": "secrets.txt", "content": "x" * 20}]},
    )
    body = res.json()
    assert body["extraction"] is None
    assert body["failure"]["kind"] == "skipped"
    assert extractor.received == []


def test_extract_failure_is_reported_not_raised(client, extractor):
    extractor.result = AiFailure(kind="error", message="Could not reach Claude.")
    res = client.post(
        "/api/work-history/extract",
        json={"files": [{"name": "README.md", "content": README}]},
    )
    assert res.status_code == 200
    assert res.json()["extraction"] is None
    assert res.json()["failure"]["kind"] == "error"


def test_create_list_get_update_delete(client, db):
    created = client.post(
        "/api/work-history",
        json={
            "name": "Velocity sync",
            "summary": "Synced deals.",
            "tech_stack": ["Zoho CRM"],
            "complexity": "medium",
            "client_name": "Northwind Mortgage",
            "ended": "2026-03",
            "source_files": [{"name": "README.md", "content": README}],
            "ai_extraction": GOOD_EXTRACTION,
        },
    )
    assert created.status_code == 201, created.text
    row = created.json()
    assert row["may_name_client"] is False  # default, never from the extraction
    assert row["source_files"][0]["sha256"]
    assert row["source_files"][0]["content"] == README

    listed = client.get("/api/work-history").json()
    assert [e["name"] for e in listed] == ["Velocity sync"]
    assert "source_files" not in listed[0]

    got = client.get(f"/api/work-history/{row['id']}")
    assert got.status_code == 200 and got.json()["name"] == "Velocity sync"

    patched = client.patch(
        f"/api/work-history/{row['id']}",
        json={"may_name_client": True, "clear": ["client_name"]},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["may_name_client"] is True
    assert patched.json()["client_name"] is None

    assert client.delete(f"/api/work-history/{row['id']}").status_code == 204
    assert client.get(f"/api/work-history/{row['id']}").status_code == 404
    assert db.rows == {}


def test_save_rescreens_source_files(client, db):
    res = client.post(
        "/api/work-history",
        json={
            "name": "Leaky",
            "source_files": [
                {"name": "README.md", "content": "sk-ant-api03-abcdefghijklmnopqrstu"}
            ],
        },
    )
    assert res.status_code == 422
    assert "Anthropic API key" in res.json()["detail"]
    assert db.rows == {}


def test_patch_rejects_clearing_non_nullable(client):
    created = client.post("/api/work-history", json={"name": "X"}).json()
    res = client.patch(f"/api/work-history/{created['id']}", json={"clear": ["name"]})
    assert res.status_code == 422


def test_patch_with_nothing_is_422(client):
    created = client.post("/api/work-history", json={"name": "X"}).json()
    assert (
        client.patch(f"/api/work-history/{created['id']}", json={}).status_code == 422
    )


def test_bad_month_format_is_422(client):
    res = client.post("/api/work-history", json={"name": "X", "ended": "March 2026"})
    assert res.status_code == 422


def test_routes_require_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/work-history").status_code == 401
