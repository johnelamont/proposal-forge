"""POST /api/jobs/{id}/advisory with fake DB, reader and advisor."""

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import app
from app.models.advisory import AdvisoryReading
from app.models.job import AiReading
from app.routes.advisory import get_advisor
from app.routes.jobs import get_reader
from app.services.advisor import Advisor
from tests.test_advisor import GOOD_ADVISORY
from tests.test_claude_service import GOOD_READING, FakeClient, _response
from tests.test_jobs_routes import FakeDb as JobsFakeDb
from tests.test_jobs_routes import FakeReader
from tests.test_matcher import entry


class FakeDb(JobsFakeDb):
    def __init__(self):
        super().__init__()
        self.history: list[dict] = []

    def list_work_history_for_matching(self):
        return self.history


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def claude():
    return FakeClient(result=_response(AdvisoryReading.model_validate(GOOD_ADVISORY)))


@pytest.fixture
def client(db, claude):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_reader] = lambda: FakeReader(
        AiReading.model_validate(GOOD_READING)
    )
    app.dependency_overrides[get_advisor] = lambda: Advisor(claude, model="m")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _job(client, raw):
    res = client.post("/api/jobs/parse", json={"raw_paste": raw})
    assert res.status_code == 201
    assert res.json()["advisory"] is None
    return res.json()["id"]


def test_advisory_with_no_history_is_stored_without_a_call(
    client, db, claude, desktop_conflict
):
    job_id = _job(client, desktop_conflict)
    res = client.post(f"/api/jobs/{job_id}/advisory")
    assert res.status_code == 200, res.text
    adv = res.json()["advisory"]
    assert adv["match_strength"]["level"] == "none_history"
    assert adv["reading"] is None
    assert claude.calls == []
    assert res.json()["advisory_at"] is not None


def test_advisory_with_comparable_history_calls_claude_and_persists(
    client, db, claude, desktop_conflict
):
    db.history = [entry()]
    job_id = _job(client, desktop_conflict)
    res = client.post(f"/api/jobs/{job_id}/advisory")
    adv = res.json()["advisory"]
    assert adv["match_strength"]["label"] == "Thin evidence: 1 comparable project"
    # Zoho CRM is a listed skill; Deluge matches through the Zoho alias family;
    # vocabulary like "velocity" is a shared term, not tech (list capped at 8).
    assert adv["comparables"][0]["shared_tech"] == ["Deluge", "Zoho CRM"]
    assert "velocity" in adv["comparables"][0]["shared_terms"]
    assert adv["reading"]["fit"] == "strong"
    assert "F8" in adv["outcomes_note"]
    assert len(claude.calls) == 1
    # Reopening the job returns the stored advisory without another call.
    again = client.get(f"/api/jobs/{job_id}").json()
    assert again["advisory"]["reading"]["fit"] == "strong"
    assert len(claude.calls) == 1


def test_refresh_recomputes(client, db, claude, desktop_conflict):
    job_id = _job(client, desktop_conflict)
    first = client.post(f"/api/jobs/{job_id}/advisory").json()["advisory"]
    assert first["match_strength"]["level"] == "none_history"
    db.history = [entry()]
    second = client.post(f"/api/jobs/{job_id}/advisory").json()["advisory"]
    assert second["match_strength"]["level"] == "thin"


def test_unknown_job_is_404(client):
    assert (
        client.post(
            "/api/jobs/00000000-0000-0000-0000-000000000000/advisory"
        ).status_code
        == 404
    )
