"""F1 routes with the database and Claude layer replaced by fakes."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import AiFailure, AiReading
from app.routes.jobs import get_db, get_reader
from app.services.db import DbError
from tests.test_claude_service import GOOD_READING


class FakeDb:
    def __init__(self):
        self.rows: dict[str, dict] = {}

    def insert_job_post(self, row):
        if row.get("upwork_job_id") and any(
            r["upwork_job_id"] == row["upwork_job_id"] for r in self.rows.values()
        ):
            raise DbError(409, "duplicate key")
        stored = {
            "id": str(uuid4()),
            "created_at": datetime.now(UTC).isoformat(),
            "decision": None,
            "decided_at": None,
            **row,
        }
        self.rows[stored["id"]] = stored
        return stored

    def get_job_post(self, job_id):
        return self.rows.get(job_id)

    def update_job_post(self, job_id, patch):
        if job_id not in self.rows:
            raise DbError(404, "not found")
        if patch.get("decided_at") == "now()":
            patch["decided_at"] = datetime.now(UTC).isoformat()
        self.rows[job_id].update(patch)
        return self.rows[job_id]

    def list_job_posts(self):
        return [
            {"id": r["id"], "title": r["analysis"]["parsed"]["title"]}
            for r in self.rows.values()
        ]


class FakeReader:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def read_description(self, inp):
        self.calls += 1
        return self.result


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def reader():
    return FakeReader(AiReading.model_validate(GOOD_READING))


@pytest.fixture
def client(db, reader):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_reader] = lambda: reader
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_parse_creates_a_row_and_returns_both_layers(client, desktop_hourly, db):
    res = client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["decision"] is None
    assert body["upwork_job_id"] == "~021000000000000000001"
    assert body["analysis"]["parse_status"] == "ok"
    assert body["analysis"]["parsed"]["title"] == "Zoho Consulting"
    assert body["analysis"]["ai"]["one_line"].startswith("Set up drip")
    assert len(db.rows) == 1
    assert db.rows[body["id"]]["raw_paste"] == desktop_hourly


def test_parse_with_ai_failure_still_succeeds(client, reader, desktop_hourly):
    reader.result = AiFailure(kind="error", message="Could not reach the Claude API.")
    res = client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly})
    assert res.status_code == 201
    body = res.json()["analysis"]
    assert body["parse_status"] == "ai_failed"
    assert body["ai"] is None
    assert body["ai_failure"]["kind"] == "error"
    assert body["parsed"]["client"]["total_spent"] == "11000"


def test_duplicate_job_id_is_a_409(client, desktop_hourly):
    assert (
        client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly}).status_code
        == 201
    )
    res = client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly})
    assert res.status_code == 409


def test_reread_retries_only_the_ai_layer(client, reader, desktop_hourly):
    reader.result = AiFailure(kind="error", message="down")
    job_id = client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly}).json()[
        "id"
    ]
    assert reader.calls == 1

    reader.result = AiReading.model_validate(GOOD_READING)
    res = client.post(f"/api/jobs/{job_id}/reread")
    assert res.status_code == 200
    assert reader.calls == 2
    assert res.json()["analysis"]["parse_status"] == "ok"
    assert res.json()["analysis"]["parsed"]["title"] == "Zoho Consulting"


def test_mobile_paste_then_supply_link(client, mobile_relayed):
    created = client.post("/api/jobs/parse", json={"raw_paste": mobile_relayed}).json()
    assert created["upwork_job_id"] is None

    bad = client.patch(f"/api/jobs/{created['id']}/link", json={"job_link": "nope"})
    assert bad.status_code == 422

    good = client.patch(
        f"/api/jobs/{created['id']}/link",
        json={"job_link": "https://www.upwork.com/jobs/~021000000000000000009?x=1"},
    )
    assert good.status_code == 200, good.text
    assert good.json()["upwork_job_id"] == "~021000000000000000009"
    assert (
        good.json()["analysis"]["parsed"]["upwork_job_id"] == "~021000000000000000009"
    )


def test_decision_is_recorded_once(client, desktop_hourly):
    job_id = client.post("/api/jobs/parse", json={"raw_paste": desktop_hourly}).json()[
        "id"
    ]

    res = client.post(f"/api/jobs/{job_id}/decision", json={"decision": "abandon"})
    assert res.status_code == 200
    assert res.json()["decision"] == "abandon"
    assert res.json()["decided_at"] is not None

    again = client.post(f"/api/jobs/{job_id}/decision", json={"decision": "continue"})
    assert again.status_code == 409


def test_unknown_job_is_404(client):
    assert client.get(f"/api/jobs/{uuid4()}").status_code == 404


def test_routes_require_auth_without_overrides():
    app.dependency_overrides.clear()
    res = TestClient(app).get("/api/jobs")
    assert res.status_code == 401


def test_parse_request_validation(client):
    assert client.post("/api/jobs/parse", json={"raw_paste": ""}).status_code == 422
