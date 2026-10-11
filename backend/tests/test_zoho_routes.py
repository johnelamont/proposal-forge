"""F6 routes with a fake database and a fake Zoho gateway."""

import base64
import secrets
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, current_user
from app.core.config import Settings, get_settings
from app.core.deps import get_db
from app.main import app
from app.models.job import AiFailure, AiReading
from app.models.zoho import Classification
from app.routes.jobs import get_reader
from app.routes.proposals import get_drafter
from app.routes.zoho import get_classifier, get_zoho
from app.services.zoho_client import TokenGrant, UpsertResult, ZohoError
from tests.test_claude_service import GOOD_READING
from tests.test_jobs_routes import FakeReader
from tests.test_proposals_routes import (
    PROFILE_IN,
    FakeDrafter,
)
from tests.test_proposals_routes import (
    FakeDb as ProposalsFakeDb,
)

KEY = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
SETTINGS = Settings(
    zoho_client_id="1000.abc",
    zoho_client_secret="shh",
    token_encryption_key=KEY,
    frontend_url="http://localhost:3000",
    _env_file=None,
)
GOOD = {
    "industry": "Mortgage / Lending",
    "job_type": "CRM integration",
    "tools": "Zoho CRM, Deluge",
    "confidence": {"industry": 0.9, "job_type": 0.85, "tools": 0.8},
}


class FakeDb(ProposalsFakeDb):
    def __init__(self):
        super().__init__()
        self.connection = None
        self.states: dict[str, dict] = {}
        self.attempts: list[dict] = []

    def get_zoho_connection(self):
        return self.connection

    def upsert_zoho_connection(self, row):
        self.connection = {"user_id": "u", "last_used_at": None, **row}
        return self.connection

    def touch_zoho_connection(self):
        if self.connection:
            self.connection["last_used_at"] = datetime.now(UTC).isoformat()

    def delete_zoho_connection(self):
        self.connection = None

    def insert_oauth_state(self, nonce):
        self.states[nonce] = {
            "nonce": nonce,
            "user_id": "u",
            "expires_at": (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
        }

    def get_oauth_state(self, nonce):
        return self.states.get(nonce)

    def delete_oauth_state(self, nonce):
        self.states.pop(nonce, None)

    def insert_lead_attempt(self, row):
        a = {
            "id": str(uuid4()),
            "attempted_by": "u",
            "attempted_at": datetime.now(UTC).isoformat(),
            "response_status": None,
            "zoho_lead_id": None,
            "action": None,
            "error": None,
            **row,
        }
        self.attempts.append(a)
        return a

    def list_lead_attempts(self, pid):
        return [a for a in self.attempts if a["proposal_id"] == pid]


class FakeZoho:
    def __init__(self):
        self.upserts: list[dict] = []
        self.fail: ZohoError | None = None
        self.revoked: list[str] = []
        self.lead_id = "5550001"

    def authorize_url(self, state):
        return f"https://accounts.zoho.com/oauth/v2/auth?state={state}"

    def exchange_code(self, code):
        if code == "bad":
            raise ZohoError("Zoho token error: invalid_code", 400, reconnect=True)
        return TokenGrant("rt-" + code, "at", "https://www.zohoapis.com", 3600)

    def access_token(self, refresh_token):
        if self.fail and self.fail.reconnect:
            raise self.fail
        return "at", "https://www.zohoapis.com"

    def revoke(self, refresh_token):
        self.revoked.append(refresh_token)

    def upsert_lead(self, access_token, api_domain, payload):
        self.upserts.append(payload)
        if self.fail:
            raise self.fail
        action = "update" if len(self.upserts) > 1 else "insert"
        return UpsertResult(self.lead_id, action, 200)


class FakeClassifier:
    def __init__(self):
        self.result = Classification.model_validate(GOOD)
        self.calls = 0

    def classify(self, analysis):
        self.calls += 1
        return self.result


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def zoho():
    return FakeZoho()


@pytest.fixture
def classifier():
    return FakeClassifier()


@pytest.fixture
def client(db, zoho, classifier):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[current_user] = lambda: CurrentUser(id="u", token="t")
    app.dependency_overrides[get_reader] = lambda: FakeReader(
        AiReading.model_validate(GOOD_READING)
    )
    app.dependency_overrides[get_drafter] = lambda: FakeDrafter()
    app.dependency_overrides[get_zoho] = lambda: zoho
    app.dependency_overrides[get_classifier] = lambda: classifier
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def connect(client):
    start = client.get("/api/integrations/zoho/connect").json()
    assert start["authorize_url"].endswith(start["state"])
    done = client.post(
        "/api/integrations/zoho/complete",
        json={"code": "code-1", "state": start["state"]},
    )
    assert done.status_code == 200, done.text
    return done.json()


def proposal_with_approval(client, raw):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = client.post("/api/jobs/parse", json={"raw_paste": raw}).json()["id"]
    out = client.post("/api/proposals", json={"job_post_id": job_id}).json()
    pid, vid = out["proposal"]["id"], out["versions"][0]["id"]
    ct = client.get(
        f"/api/proposals/{pid}/copy-text", params={"section": "all", "version_id": vid}
    ).json()
    assert (
        client.post(
            f"/api/proposals/{pid}/approvals",
            json={
                "draft_version_id": vid,
                "section": "all",
                "content_hash": ct["content_hash"],
            },
        ).status_code
        == 201
    )
    return pid


# --- connection ---------------------------------------------------------------


def test_connect_complete_status_disconnect(client, db, zoho):
    assert client.get("/api/integrations/zoho/status").json()["connected"] is False
    status = connect(client)
    assert status["connected"] is True and status["scopes"][0].startswith("ZohoCRM")
    assert db.connection["refresh_token_enc"] != "rt-code-1"  # encrypted at rest
    assert db.states == {}  # state consumed
    assert client.delete("/api/integrations/zoho/connection").status_code == 204
    assert zoho.revoked == ["rt-code-1"]
    assert client.get("/api/integrations/zoho/status").json()["connected"] is False


def test_state_is_single_use_and_must_belong_to_the_user(client, db):
    start = client.get("/api/integrations/zoho/connect").json()
    db.states[start["state"]]["expires_at"] = (
        datetime.now(UTC) - timedelta(seconds=1)
    ).isoformat()
    res = client.post(
        "/api/integrations/zoho/complete", json={"code": "c", "state": start["state"]}
    )
    assert res.status_code == 409 and "expired" in res.json()["detail"]
    again = client.post(
        "/api/integrations/zoho/complete", json={"code": "c", "state": start["state"]}
    )
    assert again.status_code == 409  # consumed even though it failed


def test_bad_code_is_reported(client):
    start = client.get("/api/integrations/zoho/connect").json()
    res = client.post(
        "/api/integrations/zoho/complete", json={"code": "bad", "state": start["state"]}
    )
    assert res.status_code == 502 and "invalid_code" in res.json()["detail"]


def test_callback_only_redirects_to_the_frontend(client):
    res = client.get(
        "/api/integrations/zoho/callback",
        params={"code": "c", "state": "s"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert (
        res.headers["location"] == "http://localhost:3000/settings/zoho?code=c&state=s"
    )


# --- preview and fields ------------------------------------------------------


def test_preview_classifies_once_and_caches(client, classifier, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    p1 = client.get(f"/api/proposals/{pid}/lead-preview").json()
    p2 = client.get(f"/api/proposals/{pid}/lead-preview").json()
    assert classifier.calls == 1
    assert p1["payload"]["Industry"] == "Mortgage / Lending"
    assert p1["flags"] == [] and p1["payload"]["Proposal"].startswith("Hi,")
    assert not p2["ready"]  # not connected yet
    client.get(f"/api/proposals/{pid}/lead-preview", params={"reclassify": "true"})
    assert classifier.calls == 2


def test_low_confidence_is_flagged_until_confirmed(
    client, classifier, desktop_conflict
):
    classifier.result = Classification.model_validate(
        {**GOOD, "confidence": {"industry": 0.4, "job_type": 0.9, "tools": 0.9}}
    )
    pid = proposal_with_approval(client, desktop_conflict)
    connect(client)
    preview = client.get(f"/api/proposals/{pid}/lead-preview").json()
    assert [f["field"] for f in preview["flags"]] == ["Industry"]
    assert not preview["ready"]
    blocked = client.post(f"/api/proposals/{pid}/create-lead")
    assert blocked.status_code == 409 and "Flagged" in blocked.json()["detail"]

    bad = client.put(f"/api/proposals/{pid}/lead-fields", json={"industry": "Banking"})
    assert bad.status_code == 422

    ok = client.put(
        f"/api/proposals/{pid}/lead-fields",
        json={
            "industry": "Finance & Accounting",
            "job_type": "CRM integration",
            "tools": "Zoho CRM",
            "proposal_link": "https://www.upwork.com/ab/proposals/9",
            "by_invitation": True,
        },
    ).json()
    assert ok["flags"] == [] and ok["ready"]
    assert ok["payload"]["Industry"] == "Finance & Accounting"
    assert ok["payload"]["By_Invitation"] is True


def test_classifier_failure_leaves_fields_for_the_operator(
    client, classifier, desktop_conflict
):
    classifier.result = AiFailure(kind="error", message="down")
    pid = proposal_with_approval(client, desktop_conflict)
    preview = client.get(f"/api/proposals/{pid}/lead-preview").json()
    assert preview["classification"] is None
    assert preview["classification_failure"]["kind"] == "error"
    assert len(preview["flags"]) == 3 and "Industry" not in preview["payload"]


# --- create lead ---------------------------------------------------------------


def test_create_lead_success_logs_and_marks_submitted(
    client, db, zoho, desktop_conflict
):
    pid = proposal_with_approval(client, desktop_conflict)
    connect(client)
    res = client.post(f"/api/proposals/{pid}/create-lead")
    assert res.status_code == 200, res.text
    body = res.json()
    assert (
        body["ok"] and body["zoho_lead_id"] == "5550001" and body["action"] == "insert"
    )
    sent = zoho.upserts[0]
    assert sent["Upwork_Job_ID"] == "~021000000000000000002"
    assert sent["Proposal"].startswith("Hi,") and sent["Hourly_Rate"] == 60.0
    p = db.proposals[pid]
    assert p["status"] == "submitted" and p["lead_sync_state"] == "created"
    assert p["zoho_lead_id"] == "5550001" and p["submitted_at"]
    assert db.connection["last_used_at"] is not None
    attempts = client.get(f"/api/proposals/{pid}/lead-attempts").json()
    assert len(attempts) == 1 and attempts[0]["zoho_lead_id"] == "5550001"

    # Pressing again upserts the same Lead; a new attempt row, same ID.
    again = client.post(f"/api/proposals/{pid}/create-lead").json()
    assert (
        again["ok"]
        and again["action"] == "update"
        and again["zoho_lead_id"] == "5550001"
    )
    assert len(db.attempts) == 2


def test_create_lead_failure_is_logged_and_visible(client, db, zoho, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    connect(client)
    zoho.fail = ZohoError("Zoho refused the Lead: INVALID_DATA (field Industry)", 400)
    res = client.post(f"/api/proposals/{pid}/create-lead").json()
    assert res["ok"] is False and "field Industry" in res["error"]
    assert db.proposals[pid]["lead_sync_state"] == "failed"
    assert db.proposals[pid]["status"] == "draft"
    assert (
        db.attempts[0]["error"].startswith("Zoho refused")
        and db.attempts[0]["response_status"] == 400
    )

    zoho.fail = ZohoError("Zoho token error: invalid_grant", 400, reconnect=True)
    res = client.post(f"/api/proposals/{pid}/create-lead").json()
    assert res["ok"] is False and res["reconnect"] is True


def test_create_lead_needs_connection_and_approval(client, desktop_conflict):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = client.post(
        "/api/jobs/parse", json={"raw_paste": desktop_conflict}
    ).json()["id"]
    pid = client.post("/api/proposals", json={"job_post_id": job_id}).json()[
        "proposal"
    ]["id"]
    res = client.post(f"/api/proposals/{pid}/create-lead")
    assert res.status_code == 409
    assert "connected" in res.json()["detail"] and "copied" in res.json()["detail"]


def test_unconfigured_server_says_so(client):
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    res = client.get("/api/integrations/zoho/connect")
    assert res.status_code == 503
