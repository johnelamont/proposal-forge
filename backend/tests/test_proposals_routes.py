"""F3/F4 routes with fake DB and drafter: versions append, approvals hash."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.main import app
from app.models.job import AiFailure, AiReading
from app.models.proposal import AiMeta, Answer, DraftOutput, Sections
from app.routes.jobs import get_reader
from app.routes.proposals import get_drafter
from app.services.db import DbError
from app.services.drafter import content_hash, frame
from tests.test_advisory_route import FakeDb as AdvisoryFakeDb
from tests.test_claude_service import GOOD_READING
from tests.test_jobs_routes import FakeReader

PROFILE_IN = {
    "signature_name": "John Lamont",
    "positioning": "Independent Zoho consultant.",
    "never_claim": ["Zoho Partner"],
    "default_hourly_rate": "60",
}


class FakeDb(AdvisoryFakeDb):
    def __init__(self):
        super().__init__()
        self.profile = None
        self.proposals: dict[str, dict] = {}
        self.versions: dict[str, dict] = {}
        self.approvals: list[dict] = []

    # profiles
    def get_profile(self):
        return self.profile

    def upsert_profile(self, row):
        now = datetime.now(UTC).isoformat()
        self.profile = {"user_id": "u", "created_at": now, "updated_at": now, **row}
        return self.profile

    # proposals
    def insert_proposal(self, row):
        if any(p["job_post_id"] == row["job_post_id"] for p in self.proposals.values()):
            raise DbError(409, "duplicate")
        now = datetime.now(UTC).isoformat()
        p = {
            "id": str(uuid4()),
            "status": "draft",
            "current_version_id": None,
            "created_at": now,
            "updated_at": now,
            **row,
        }
        self.proposals[p["id"]] = p
        return p

    def get_proposal(self, pid):
        return self.proposals.get(pid)

    def get_proposal_by_job(self, jid):
        return next(
            (p for p in self.proposals.values() if p["job_post_id"] == jid), None
        )

    def update_proposal(self, pid, patch):
        self.proposals[pid].update(patch)
        return self.proposals[pid]

    def list_versions(self, pid):
        return sorted(
            (v for v in self.versions.values() if v["proposal_id"] == pid),
            key=lambda v: v["version"],
        )

    def get_version(self, vid):
        return self.versions.get(vid)

    def insert_version(self, row):
        v = {"id": str(uuid4()), "created_at": datetime.now(UTC).isoformat(), **row}
        self.versions[v["id"]] = v
        return v

    def list_approvals(self, pid):
        return [a for a in self.approvals if a["proposal_id"] == pid]

    def insert_approval(self, row):
        a = {
            "id": str(uuid4()),
            "approved_by": "u",
            "approved_at": datetime.now(UTC).isoformat(),
            **row,
        }
        self.approvals.append(a)
        return a

    def get_work_history_many(self, ids):
        return [e for e in self.history if e["id"] in ids]


class FakeDrafter:
    def __init__(self):
        self.fail = False
        self.refine_fail = False

    def draft(self, analysis, advisory, cited, profile, questions):
        if self.fail:
            return (
                Sections(
                    cover_letter=None,
                    answers=[Answer(question=q, answer="") for q in questions],
                ),
                AiMeta(model="m", failure=AiFailure(kind="error", message="down")),
            )
        out = DraftOutput.model_validate(
            {
                "cover_letter": "Body of the letter.",
                "answers": [{"question": q, "answer": f"A: {q}"} for q in questions],
                "confidence": {"cover_letter": 0.9, "answers": 0.8},
            }
        )
        return (
            Sections(
                cover_letter=frame(out.cover_letter, profile), answers=out.answers
            ),
            AiMeta(model="m", confidence=out.confidence.model_dump()),
        )

    def refine(self, current, instruction, profile, is_cover):
        if self.refine_fail:
            return None, AiMeta(
                model="m", failure=AiFailure(kind="error", message="down")
            )
        text = f"{instruction}: {current}"
        return (frame(text, profile) if is_cover else text), AiMeta(
            model="m", confidence={"refined": 0.7}
        )


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def drafter():
    return FakeDrafter()


@pytest.fixture
def client(db, drafter):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_reader] = lambda: FakeReader(
        AiReading.model_validate(GOOD_READING)
    )
    app.dependency_overrides[get_drafter] = lambda: drafter
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _job(client, raw):
    res = client.post("/api/jobs/parse", json={"raw_paste": raw})
    assert res.status_code == 201
    return res.json()["id"]


def test_profile_roundtrip(client):
    assert client.get("/api/profile").json() is None
    res = client.put("/api/profile", json=PROFILE_IN)
    assert res.status_code == 200
    assert res.json()["greeting"] == "Hi,"  # default
    assert client.get("/api/profile").json()["signature_name"] == "John Lamont"


def test_drafting_requires_a_profile(client, desktop_conflict):
    job_id = _job(client, desktop_conflict)
    res = client.post("/api/proposals", json={"job_post_id": job_id})
    assert res.status_code == 409 and "profile" in res.json()["detail"].lower()


def test_create_writes_version_one_with_quote_and_questions(client, db, desktop_hourly):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = _job(client, desktop_hourly)
    res = client.post("/api/proposals", json={"job_post_id": job_id})
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["job_title"] == "Zoho Consulting"
    assert len(body["versions"]) == 1
    v1 = body["versions"][0]
    assert v1["version"] == 1 and v1["source"] == "ai"
    assert v1["sections"]["cover_letter"].startswith("Hi,\n\nBody of the letter.")
    assert v1["sections"]["cover_letter"].endswith("Kind Regards,\nJohn Lamont")
    assert (
        v1["sections"]["quote"]["amount"] == "60"
        and v1["sections"]["quote"]["model"] == "hourly"
    )
    assert body["proposal"]["current_version_id"] == v1["id"]
    # Creating again for the same job returns the existing proposal, no new version.
    again = client.post("/api/proposals", json={"job_post_id": job_id})
    assert again.status_code == 201 and len(again.json()["versions"]) == 1


def test_form_paste_adds_questions_answered_in_the_draft(client, desktop_hourly):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = _job(client, desktop_hourly)  # no questions in this job
    form = "Questions\n1. What is your availability?\n2. Share a similar project\n"
    body = client.post(
        "/api/proposals", json={"job_post_id": job_id, "form_paste": form}
    ).json()
    assert body["proposal"]["extra_questions"] == [
        "What is your availability?",
        "Share a similar project",
    ]
    answers = body["versions"][0]["sections"]["answers"]
    assert [a["question"] for a in answers] == [
        "What is your availability?",
        "Share a similar project",
    ]


def test_draft_failure_is_stored_as_a_version_with_the_failure(
    client, drafter, desktop_conflict
):
    client.put("/api/profile", json=PROFILE_IN)
    drafter.fail = True
    job_id = _job(client, desktop_conflict)
    body = client.post("/api/proposals", json={"job_post_id": job_id}).json()
    v1 = body["versions"][0]
    assert v1["sections"]["cover_letter"] is None
    assert v1["ai_meta"]["failure"]["kind"] == "error"
    assert v1["sections"]["quote"] is not None  # F4 still ran


def test_refine_and_edit_append_versions_and_failure_keeps_previous(
    client, drafter, desktop_conflict
):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = _job(client, desktop_conflict)
    # The fake F1 reading finds no questions, so supply one via the form paste.
    pid = client.post(
        "/api/proposals",
        json={"job_post_id": job_id, "form_paste": "Questions\n1. Availability?"},
    ).json()["proposal"]["id"]

    r = client.post(
        f"/api/proposals/{pid}/refine",
        json={"section": "cover_letter", "instruction": "shorter"},
    )
    assert r.status_code == 200, r.text
    assert (
        len(r.json()["versions"]) == 2 and r.json()["versions"][1]["source"] == "refine"
    )
    assert r.json()["versions"][1]["sections"]["cover_letter"].startswith(
        "Hi,\n\nshorter:"
    )

    e = client.post(
        f"/api/proposals/{pid}/edit",
        json={"section": "answer", "index": 0, "content": "My own words."},
    )
    assert e.status_code == 200
    assert e.json()["versions"][2]["source"] == "edit"
    assert (
        e.json()["versions"][2]["sections"]["answers"][0]["answer"] == "My own words."
    )

    drafter.refine_fail = True
    f = client.post(
        f"/api/proposals/{pid}/refine",
        json={"section": "answer", "index": 0, "instruction": "x"},
    )
    assert f.status_code == 502 and "Previous version kept" in f.json()["detail"]
    assert len(client.get(f"/api/proposals/{pid}").json()["versions"]) == 3

    q = client.post(
        f"/api/proposals/{pid}/edit",
        json={
            "section": "quote",
            "content": "Agreed on a call.",
            "quote_amount": "4500",
        },
    )
    assert q.json()["versions"][3]["sections"]["quote"]["amount"] == "4500"


def test_copy_text_and_approval_hash(client, db, desktop_conflict):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = _job(client, desktop_conflict)
    body = client.post("/api/proposals", json={"job_post_id": job_id}).json()
    pid, vid = body["proposal"]["id"], body["versions"][0]["id"]

    ct = client.get(
        f"/api/proposals/{pid}/copy-text",
        params={"section": "cover_letter", "version_id": vid},
    ).json()
    assert ct["text"].startswith("Hi,") and ct["content_hash"] == content_hash(
        ct["text"]
    )

    ok = client.post(
        f"/api/proposals/{pid}/approvals",
        json={
            "draft_version_id": vid,
            "section": "cover_letter",
            "content_hash": ct["content_hash"],
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["section"] == "cover_letter"

    bad = client.post(
        f"/api/proposals/{pid}/approvals",
        json={
            "draft_version_id": vid,
            "section": "cover_letter",
            "content_hash": "0" * 64,
        },
    )
    assert bad.status_code == 409

    all_text = client.get(
        f"/api/proposals/{pid}/copy-text", params={"section": "all", "version_id": vid}
    ).json()
    assert "Quote: $60/hr" in all_text["text"]
    assert all_text["text"].startswith("Hi,")
    assert len(client.get(f"/api/proposals/{pid}").json()["approvals"]) == 1


def test_abandoned_job_cannot_be_drafted(client, desktop_conflict):
    client.put("/api/profile", json=PROFILE_IN)
    job_id = _job(client, desktop_conflict)
    client.post(f"/api/jobs/{job_id}/decision", json={"decision": "abandon"})
    assert (
        client.post("/api/proposals", json={"job_post_id": job_id}).status_code == 409
    )


def test_routes_require_auth():
    app.dependency_overrides.clear()
    assert TestClient(app).get("/api/profile").status_code == 401
