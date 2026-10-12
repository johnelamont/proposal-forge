"""F8 routes with a fake database that mirrors the SQL functions' behaviour.

The real `record_outcome()` runs inside Postgres (verified against the local
stack when the migration landed); here the fake reproduces its contract so the
HTTP layer — validation, auth, status codes, queue, attention — is exercised.
"""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, current_user
from app.core.config import get_settings
from app.core.deps import get_db
from app.main import app
from app.models.job import AiReading
from app.models.outcomes import LEAD_ALLOW_LIST
from app.routes import outcomes as outcomes_routes
from app.routes.jobs import get_reader
from app.routes.outcomes import get_anon_db
from app.routes.proposals import get_drafter
from app.routes.zoho import get_classifier, get_zoho
from app.services.db import DbError
from tests.test_claude_service import GOOD_READING
from tests.test_jobs_routes import FakeReader
from tests.test_proposals_routes import PROFILE_IN, FakeDrafter
from tests.test_zoho_routes import (
    SETTINGS,
    FakeClassifier,
    FakeZoho,
    connect,
    proposal_with_approval,
)
from tests.test_zoho_routes import FakeDb as ZohoFakeDb

JOB_ID = "~021000000000000000002"  # the mortgage fixture's Upwork job ID
NOW = datetime.now(UTC).isoformat()


def _h(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


class FakeDb(ZohoFakeDb):
    """Adds the F8 tables and the two SQL functions' behaviour."""

    def __init__(self):
        super().__init__()
        self.secret: dict | None = None
        self.outcomes: list[dict] = []
        self.queue: list[dict] = []
        self.index: dict[str, dict] = {}

    # secret
    def get_integration_secret(self):
        if not self.secret:
            return None
        return {k: v for k, v in self.secret.items() if k != "secret_hash"}

    def upsert_integration_secret(self, row):
        self.secret = {"user_id": "u", **row}
        return self.get_integration_secret()

    def delete_integration_secret(self):
        self.secret = None

    # history / index / queue
    def list_outcomes(self, pid):
        return sorted(
            (o for o in self.outcomes if o["proposal_id"] == pid),
            key=lambda o: o["received_at"],
            reverse=True,
        )

    def get_rag_index(self, pid):
        return self.index.get(pid)

    def set_rag_archived(self, pid, archived):
        row = self.index.get(pid)
        if row:
            row["archived"] = archived
        return row

    def list_outcome_queue(self):
        return [q for q in self.queue if not q["resolved_at"] and not q["dismissed_at"]]

    def dismiss_queued_outcome(self, qid):
        for q in self.queue:
            if q["id"] == qid and not q["dismissed_at"]:
                q["dismissed_at"] = NOW
                return True
        return False

    def list_proposals_for_attention(self):
        out = []
        for p in self.proposals.values():
            if p["status"] in ("draft", "submitted"):
                job = self.rows[p["job_post_id"]]
                out.append(
                    {**p, "job_posts": {"title": job["analysis"]["parsed"]["title"]}}
                )
        return out

    def rebuild_rag_index(self):
        return len(self.index)

    # the SQL functions
    def _apply(self, pid, payload, source):
        last = self.list_outcomes(pid)
        reason = payload.get("lost_reason")
        label = payload["outcome"] + (f" ({reason})" if reason else "")
        if (
            last
            and last[0]["outcome"] == payload["outcome"]
            and last[0]["lost_reason"] == reason
        ):
            return {
                "code": 200,
                "message": f"Already recorded as {label} in Proposal Forge",
                "proposal_id": pid,
                "outcome": payload["outcome"],
                "indexed": True,
                "queued": False,
                "duplicate": True,
            }
        self.outcomes.append(
            {
                "id": str(uuid4()),
                "proposal_id": pid,
                "user_id": "u",
                "outcome": payload["outcome"],
                "lost_reason": reason,
                "decided_at": payload.get("decided_at"),
                "zoho_lead_id": payload.get("zoho_lead_id"),
                "lead": payload.get("lead") or {},
                "source": source,
                "received_at": datetime.now(UTC).isoformat(),
            }
        )
        p = self.proposals[pid]
        p["status"] = payload["outcome"]
        p["outcome_recorded_at"] = NOW
        approvals = self.list_approvals(pid)
        excerpt = None
        if approvals:
            latest = max(approvals, key=lambda a: a["approved_at"])
            excerpt = (self.versions[latest["draft_version_id"]]["sections"] or {}).get(
                "cover_letter"
            )
        lead = payload.get("lead") or {}
        fields = p.get("lead_fields") or {}
        self.index[pid] = {
            "proposal_id": pid,
            "outcome": payload["outcome"],
            "lost_reason": reason,
            "industry": lead.get("Industry") or fields.get("industry"),
            "job_type": lead.get("Job_Type") or fields.get("job_type"),
            "tools": lead.get("Tools"),
            "rate_type": lead.get("Rate_Type"),
            "hourly_rate": lead.get("Hourly_Rate"),
            "fixed_price": lead.get("Upwork_Fixed_Price"),
            "budget": lead.get("Budget"),
            "budget_band": None,
            "quote_model": None,
            "quote_amount": None,
            "job_title": self.rows[p["job_post_id"]]["analysis"]["parsed"]["title"],
            "skills": [],
            "proposal_excerpt": (excerpt or "")[:1500] or None,
            "decided_at": payload.get("decided_at"),
            "archived": False,
            "indexed_at": NOW,
        }
        return {
            "code": 200,
            "message": f"Recorded {label} in Proposal Forge",
            "proposal_id": pid,
            "outcome": payload["outcome"],
            "indexed": True,
            "queued": False,
            "duplicate": False,
        }

    def record_outcome(self, secret_hash, payload):
        if not self.secret or self.secret["secret_hash"] != secret_hash:
            return {"code": 401, "message": "Proposal Forge rejected the secret"}
        self.secret["last_used_at"] = NOW
        pid = next(
            (
                p["id"]
                for p in self.proposals.values()
                if self.rows[p["job_post_id"]].get("upwork_job_id")
                == payload["upwork_job_id"]
            ),
            None,
        )
        if pid is None:
            self.queue.append(
                {
                    "id": str(uuid4()),
                    "upwork_job_id": payload["upwork_job_id"],
                    "zoho_lead_id": payload.get("zoho_lead_id"),
                    "payload": payload,
                    "received_at": NOW,
                    "resolved_at": None,
                    "resolved_proposal_id": None,
                    "dismissed_at": None,
                }
            )
            return {
                "code": 202,
                "message": "No matching proposal — held for review in Proposal Forge",
                "indexed": False,
                "queued": True,
                "duplicate": False,
            }
        return self._apply(pid, payload, "zoho")

    def resolve_queued_outcome(self, qid, pid):
        q = next((q for q in self.list_outcome_queue() if q["id"] == qid), None)
        if q is None:
            raise DbError(400, "queued outcome not found")
        result = self._apply(pid, q["payload"], "manual_match")
        q["resolved_at"], q["resolved_proposal_id"] = NOW, pid
        return result


class FakeAnon:
    def __init__(self, db: FakeDb):
        self.db = db
        self.fail = False

    def record_outcome(self, secret_hash, payload):
        if self.fail:
            raise DbError(500, "db down")
        return self.db.record_outcome(secret_hash, payload)


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def client(db):
    outcomes_routes.limiter.reset()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_anon_db] = lambda: FakeAnon(db)
    app.dependency_overrides[get_settings] = lambda: SETTINGS
    app.dependency_overrides[current_user] = lambda: CurrentUser(id="u", token="t")
    app.dependency_overrides[get_reader] = lambda: FakeReader(
        AiReading.model_validate(GOOD_READING)
    )
    app.dependency_overrides[get_drafter] = lambda: FakeDrafter()
    app.dependency_overrides[get_zoho] = lambda: FakeZoho()
    app.dependency_overrides[get_classifier] = lambda: FakeClassifier()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        outcomes_routes.limiter.reset()


def generate_secret(client) -> str:
    res = client.post("/api/integrations/outcome-secret")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["exists"] and body["endpoint_url"].endswith("/zoho/outcome")
    return body["secret"]


def post_outcome(client, secret, **over):
    payload = {
        "schema_version": "1.0",
        "upwork_job_id": JOB_ID,
        "zoho_lead_id": "5550001",
        "outcome": "won",
        "lost_reason": None,
        "decided_at": "2026-10-20T09:00:00-07:00",
        "lead": {"Industry": "Mortgage / Lending", "Rate_Type": "Hourly"},
    }
    payload.update(over)
    return client.post(
        "/api/integrations/zoho/outcome",
        json=payload,
        headers={"Authorization": f"Bearer {secret}"},
    )


# --- allow-list parity with the Deluge helper --------------------------------


def test_allow_list_matches_the_deluge_helper():
    helper = Path(__file__).parents[2] / "zoho" / "deluge" / "forge_helper.dg"
    in_deluge = re.findall(r'allowed\.add\("([A-Za-z_]+)"\)', helper.read_text("utf-8"))
    assert tuple(in_deluge) == LEAD_ALLOW_LIST


# --- secret ----------------------------------------------------------------------


def test_secret_lifecycle(client, db):
    assert client.get("/api/integrations/outcome-secret").json()["exists"] is False
    first = generate_secret(client)
    assert db.secret["secret_hash"] == _h(first)
    assert "secret" not in client.get("/api/integrations/outcome-secret").json()
    second = generate_secret(client)  # rotate: old one stops working
    assert db.secret["secret_hash"] == _h(second) and first != second
    assert client.delete("/api/integrations/outcome-secret").status_code == 204
    assert client.get("/api/integrations/outcome-secret").json()["exists"] is False


# --- inbound: auth and validation -------------------------------------------------


def test_missing_or_unknown_secret_is_401(client, db, desktop_conflict):
    proposal_with_approval(client, desktop_conflict)
    res = client.post("/api/integrations/zoho/outcome", json={})
    assert res.status_code == 401
    generate_secret(client)
    res = post_outcome(client, "not-the-secret-at-all")
    assert res.status_code == 401 and db.outcomes == []


def test_invalid_payloads_are_400_with_the_reason(client, desktop_conflict):
    proposal_with_approval(client, desktop_conflict)
    secret = generate_secret(client)
    lost_without_reason = post_outcome(client, secret, outcome="lost")
    assert lost_without_reason.status_code == 400
    assert "lost_reason is required" in lost_without_reason.json()["detail"]

    reason_on_won = post_outcome(client, secret, lost_reason="job_closed")
    assert reason_on_won.status_code == 400

    off_list = post_outcome(
        client, secret, lead={"Industry": "Legal", "Email": "a@b.c"}
    )
    assert off_list.status_code == 400 and "Email" in off_list.json()["detail"]

    old_schema = post_outcome(client, secret, schema_version="0.9")
    assert old_schema.status_code == 400

    too_big = client.post(
        "/api/integrations/zoho/outcome",
        content=b"x" * (32 * 1024 + 1),
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
        },
    )
    assert too_big.status_code == 413


def test_rate_limit_is_429(client, desktop_conflict, monkeypatch):
    secret = generate_secret(client)
    monkeypatch.setattr(outcomes_routes.limiter, "_limit", 2)
    assert post_outcome(client, secret).status_code in (200, 202)
    assert post_outcome(client, secret).status_code in (200, 202)
    assert post_outcome(client, secret).status_code == 429


# --- inbound: recording ---------------------------------------------------------------


def test_won_is_recorded_indexed_and_replay_is_a_noop(client, db, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    connect(client)
    client.post(f"/api/proposals/{pid}/create-lead")
    secret = generate_secret(client)

    res = post_outcome(client, secret)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["outcome"] == "won" and body["indexed"] and not body["duplicate"]
    assert body["message"].startswith("Recorded won")
    assert db.proposals[pid]["status"] == "won"

    again = post_outcome(client, secret).json()
    assert again["duplicate"] and again["message"].startswith("Already recorded")
    assert len(db.outcomes) == 1

    detail = client.get(f"/api/proposals/{pid}/outcomes").json()
    assert detail["status"] == "won" and len(detail["history"]) == 1
    assert detail["history"][0]["source"] == "zoho"
    assert detail["history"][0]["lead"] == {
        "Industry": "Mortgage / Lending",
        "Rate_Type": "Hourly",
    }
    assert detail["index"]["industry"] == "Mortgage / Lending"
    assert detail["index"]["proposal_excerpt"].startswith("Hi,")
    assert detail["lead_url"] == "https://crm.zoho.com/crm/tab/Leads/5550001"
    assert detail["stale"] is False


def test_correction_appends_and_reasons_are_kept(client, db, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    secret = generate_secret(client)
    assert (
        post_outcome(
            client, secret, outcome="lost", lost_reason="job_closed"
        ).status_code
        == 200
    )
    assert (
        post_outcome(
            client, secret, outcome="lost", lost_reason="hired_other"
        ).status_code
        == 200
    )
    assert post_outcome(client, secret, outcome="won").status_code == 200
    history = client.get(f"/api/proposals/{pid}/outcomes").json()["history"]
    assert [(h["outcome"], h["lost_reason"]) for h in history] == [
        ("won", None),
        ("lost", "hired_other"),
        ("lost", "job_closed"),
    ]
    assert db.proposals[pid]["status"] == "won"
    assert db.index[pid]["outcome"] == "won"


def test_database_failure_is_500_never_silent(client, db, desktop_conflict):
    proposal_with_approval(client, desktop_conflict)
    secret = generate_secret(client)
    anon = FakeAnon(db)
    anon.fail = True
    app.dependency_overrides[get_anon_db] = lambda: anon
    res = post_outcome(client, secret)
    assert res.status_code == 500 and "could not record" in res.json()["detail"]
    assert db.outcomes == []


# --- queue ---------------------------------------------------------------


def test_unmatched_job_is_queued_then_matched(client, db, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    secret = generate_secret(client)
    res = post_outcome(client, secret, upwork_job_id="~01unknown")
    assert res.status_code == 202 and res.json()["queued"]
    queue = client.get("/api/outcomes/queue").json()
    assert len(queue) == 1 and queue[0]["upwork_job_id"] == "~01unknown"
    assert client.get("/api/attention").json()["queued_outcomes"] == 1

    matched = client.post(
        f"/api/outcomes/queue/{queue[0]['id']}/match", json={"proposal_id": pid}
    )
    assert matched.status_code == 200 and matched.json()["outcome"] == "won"
    assert client.get("/api/outcomes/queue").json() == []
    history = client.get(f"/api/proposals/{pid}/outcomes").json()["history"]
    assert history[0]["source"] == "manual_match"

    gone = client.post(
        f"/api/outcomes/queue/{queue[0]['id']}/match", json={"proposal_id": pid}
    )
    assert gone.status_code == 404


def test_dismiss_queued(client, desktop_conflict):
    proposal_with_approval(client, desktop_conflict)
    secret = generate_secret(client)
    post_outcome(client, secret, upwork_job_id="~01other")
    qid = client.get("/api/outcomes/queue").json()[0]["id"]
    assert client.post(f"/api/outcomes/queue/{qid}/dismiss").status_code == 204
    assert client.get("/api/outcomes/queue").json() == []
    assert client.post(f"/api/outcomes/queue/{qid}/dismiss").status_code == 404


# --- archive, attention, nudge --------------------------------------------


def test_archive_requires_an_index_row(client, db, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    none_yet = client.put(f"/api/proposals/{pid}/rag-archived", json={"archived": True})
    assert none_yet.status_code == 404
    secret = generate_secret(client)
    post_outcome(client, secret)
    row = client.put(
        f"/api/proposals/{pid}/rag-archived", json={"archived": True}
    ).json()
    assert row["archived"] is True and db.index[pid]["archived"] is True


def test_attention_lists_failed_leads_and_stale_submitted(client, db, desktop_conflict):
    pid = proposal_with_approval(client, desktop_conflict)
    client.put("/api/profile", json={**PROFILE_IN, "stale_submitted_days": 7})
    db.proposals[pid].update(
        status="submitted",
        submitted_at=(datetime.now(UTC) - timedelta(days=8)).isoformat(),
        lead_sync_state="failed",
    )
    strip = client.get("/api/attention").json()
    assert strip["stale_after_days"] == 7
    assert [s["proposal_id"] for s in strip["stale_submitted"]] == [pid]
    assert strip["stale_submitted"][0]["job_title"].startswith("Looking for Zoho")
    assert [f["proposal_id"] for f in strip["lead_failed"]] == [pid]
    detail = client.get(f"/api/proposals/{pid}/outcomes").json()
    assert detail["stale"] is True and detail["stale_after_days"] == 7

    # Once an outcome lands it is neither stale nor open.
    secret = generate_secret(client)
    post_outcome(client, secret)
    strip = client.get("/api/attention").json()
    assert strip["stale_submitted"] == [] and strip["lead_failed"] == []
