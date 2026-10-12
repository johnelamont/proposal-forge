"""F7: the manifest's Rule 5 boundary, deterministic rendering, and the
preview → approve → logged export routes with their failure paths."""

import base64
import hashlib
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.auth import CurrentUser, current_user
from app.core.deps import get_db
from app.main import app
from app.models.portfolio import Selection
from app.routes import portfolio as portfolio_routes
from app.services import portfolio as svc
from app.services.db import DbError
from app.services.portfolio import (
    PortfolioError,
    build_manifest,
    manifest_hash,
    render_pdf,
)
from tests.test_drafter import PROFILE

TODAY = date(2026, 10, 12)


def entry(**over):
    base = {
        "id": "e1",
        "name": "Velocity → Zoho sync",
        "summary": "Connected a mortgage broker's Velocity system to Zoho CRM.",
        "tech_stack": ["Zoho CRM", "Deluge", "Webhooks"],
        "vertical": "mortgage brokerage",
        "project_type": "CRM integration",
        "complexity": "medium",
        "role": "Solo consultant",
        "outcomes": ["Funded deals sync automatically"],
        "client_name": "Northwind Mortgage",
        "may_name_client": False,
        "budget_band": "$1–5K",
        "started": "2025-03",
        "ended": "2025-06",
        "source_files": [{"name": "README.md"}],
        "ai_extraction": {"model": "m"},
    }
    return {**base, **over}


def idx(**over):
    base = {
        "proposal_id": str(uuid4()),
        "outcome": "won",
        "lost_reason": None,
        "industry": "Mortgage / Lending",
        "archived": False,
    }
    return {**base, **over}


def sel(**over):
    return Selection.model_validate({"entry_ids": ["e1"], **over})


# --- manifest ------------------------------------------------------------------------


def test_client_named_only_when_permitted_and_money_never_present():
    m, warnings = build_manifest(PROFILE, [entry()], [], sel(), TODAY)
    e = m.entries[0]
    assert e.client_line == "for a mortgage brokerage client"
    assert any('not marked "OK to name"' in w for w in warnings)
    dumped = m.model_dump_json()
    assert "Northwind" not in dumped
    assert "$1–5K" not in dumped and "README.md" not in dumped and "model" not in dumped

    named, warnings = build_manifest(
        PROFILE, [entry(may_name_client=True)], [], sel(), TODAY
    )
    assert named.entries[0].client_line == "for Northwind Mortgage"
    assert warnings == []
    assert named.entries[0].period == "Mar 2025 – Jun 2025"


def test_date_range_order_and_tech_counts():
    rows = [
        entry(id="a", name="A", ended="2024-01", tech_stack=["Zoho CRM"]),
        entry(id="b", name="B", ended="2026-02", tech_stack=["Zoho CRM", "Python"]),
        entry(id="c", name="C", started=None, ended=None, tech_stack=["Go"]),
    ]
    m, warnings = build_manifest(
        PROFILE, rows, [], sel(entry_ids=["a", "b", "c", "ghost"]), TODAY
    )
    assert [e.name for e in m.entries] == ["B", "A", "C"]  # newest first, undated last
    assert [(t.name, t.count) for t in m.tech] == [
        ("Zoho CRM", 2),
        ("Go", 1),
        ("Python", 1),
    ]
    assert any("no longer exist" in w for w in warnings)

    ranged, warnings = build_manifest(
        PROFILE, rows, [], sel(entry_ids=["a", "b", "c"], **{"from": "2025-01"}), TODAY
    )
    assert [e.name for e in ranged.entries] == ["B"]
    assert any("outside the date range" in w for w in warnings)

    with pytest.raises(PortfolioError):
        build_manifest(
            PROFILE, rows, [], sel(entry_ids=["a"], **{"from": "2025-01"}), TODAY
        )

    no_tech, _ = build_manifest(
        PROFILE, rows, [], sel(entry_ids=["a"], include_tech=False), TODAY
    )
    assert no_tech.tech == []


def test_results_are_counts_and_skip_not_worth_bidding():
    rows = [
        idx(),
        idx(industry="Legal"),
        idx(outcome="lost", lost_reason="job_closed"),
        idx(outcome="lost", lost_reason="junk_lead"),
        idx(outcome="withdrawn"),
        idx(outcome="won", archived=True, industry="Archived Co"),
    ]
    m, _ = build_manifest(PROFILE, [entry()], rows, sel(), TODAY)
    assert m.results is not None
    assert (m.results.won, m.results.lost, m.results.withdrawn) == (2, 1, 1)
    assert m.results.industries_won == ["Legal", "Mortgage / Lending"]

    none, _ = build_manifest(PROFILE, [entry()], [], sel(), TODAY)
    assert none.results is None
    off, _ = build_manifest(PROFILE, [entry()], rows, sel(include_results=False), TODAY)
    assert off.results is None


def test_manifest_hash_is_canonical_and_title_defaults():
    m1, _ = build_manifest(PROFILE, [entry()], [], sel(), TODAY)
    m2, _ = build_manifest(PROFILE, [entry()], [], sel(), TODAY)
    assert manifest_hash(m1) == manifest_hash(m2)
    assert m1.title == "John Lamont — Selected work"
    titled, _ = build_manifest(PROFILE, [entry()], [], sel(title="Zoho work"), TODAY)
    assert titled.title == "Zoho work" and manifest_hash(titled) != manifest_hash(m1)


# --- renderer -------------------------------------------------------------------------


def test_render_is_a_deterministic_pdf():
    m, _ = build_manifest(PROFILE, [entry(may_name_client=True)], [idx()], sel(), TODAY)
    pdf1, pages1 = render_pdf(m)
    pdf2, pages2 = render_pdf(m)
    assert pdf1[:5] == b"%PDF-" and pages1 == 1 and pages2 == 1
    assert pdf1 == pdf2  # invariant mode: same manifest, same bytes
    assert (
        b"Proposal Forge" in pdf1 or b"Proposal" in pdf1
    )  # footer text is in the stream

    many, _ = build_manifest(
        PROFILE,
        [entry(id=f"e{i}", name=f"Project {i}", summary="x " * 400) for i in range(12)],
        [],
        sel(entry_ids=[f"e{i}" for i in range(12)]),
        TODAY,
    )
    _, pages = render_pdf(many)
    assert pages > 1


# --- routes ----------------------------------------------------------------


class FakeDb:
    def __init__(self):
        self.profile = {
            "user_id": "u",
            "created_at": "t",
            "updated_at": "t",
            **PROFILE.model_dump(exclude={"user_id", "created_at", "updated_at"}),
        }
        self.entries = [
            entry(),
            entry(id="e2", name="Second", may_name_client=True, ended="2026-01"),
        ]
        self.index = [idx()]
        self.exports: list[dict] = []
        self.fail_insert = False

    def get_profile(self):
        return self.profile

    def list_work_history_for_portfolio(self):
        return self.entries

    def list_rag_index_for_matching(self):
        return [r for r in self.index if not r.get("archived")]

    def insert_portfolio_export(self, row):
        if self.fail_insert:
            raise DbError(500, "db down")
        rec = {
            "id": str(uuid4()),
            "exported_by": "u",
            "exported_at": datetime.now(UTC).isoformat(),
            **row,
        }
        self.exports.append(rec)
        return rec

    def list_portfolio_exports(self):
        return list(reversed(self.exports))


@pytest.fixture
def db():
    return FakeDb()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[current_user] = lambda: CurrentUser(id="u", token="t")
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_entries_expose_naming_state(client):
    rows = client.get("/api/portfolio/entries").json()
    assert [r["id"] for r in rows] == ["e1", "e2"]
    assert rows[0]["has_client_name"] and not rows[0]["may_name_client"]
    assert rows[1]["may_name_client"]


def test_preview_then_approve_logs_and_downloads(client, db):
    body = {"entry_ids": ["e1", "e2"], "title": "Zoho work"}
    pv = client.post("/api/portfolio/preview", json=body)
    assert pv.status_code == 200, pv.text
    p = pv.json()
    assert p["page_count"] >= 1 and p["manifest"]["entries"][0]["name"] == "Second"
    pdf = base64.b64decode(p["pdf_base64"])
    assert pdf[:5] == b"%PDF-"
    assert any("not shown" in w for w in p["warnings"])
    assert db.exports == []  # a preview records nothing

    res = client.post(
        "/api/portfolio/exports",
        json={"selection": body, "content_hash": p["content_hash"]},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.headers["content-disposition"].startswith(
        'attachment; filename="portfolio-'
    )
    assert res.headers["x-content-hash"] == p["content_hash"]
    assert hashlib.sha256(res.content).hexdigest() == res.headers["x-pdf-hash"]
    assert res.content == pdf  # exactly the previewed document
    assert len(db.exports) == 1
    rec = db.exports[0]
    assert rec["content_hash"] == p["content_hash"] and rec["entry_count"] == 2
    assert rec["selection"]["entry_ids"] == ["e1", "e2"]

    log = client.get("/api/portfolio/exports").json()
    assert len(log) == 1 and log[0]["pdf_hash"] == res.headers["x-pdf-hash"]


def test_approve_with_stale_hash_is_409_and_logs_nothing(client, db):
    body = {"entry_ids": ["e1"]}
    stale = client.post("/api/portfolio/preview", json=body).json()["content_hash"]
    db.entries[0]["may_name_client"] = True  # the operator changed a naming flag
    res = client.post(
        "/api/portfolio/exports", json={"selection": body, "content_hash": stale}
    )
    assert res.status_code == 409 and "Preview again" in res.json()["detail"]
    assert db.exports == []


def test_failures_halt_without_a_file(client, db, monkeypatch):
    assert (
        client.post("/api/portfolio/preview", json={"entry_ids": []}).status_code == 422
    )
    assert (
        client.post("/api/portfolio/preview", json={"entry_ids": ["nope"]}).status_code
        == 422
    )

    db.profile["positioning"] = ""
    assert (
        client.post("/api/portfolio/preview", json={"entry_ids": ["e1"]}).status_code
        == 409
    )
    db.profile["positioning"] = "Independent Zoho consultant."

    body = {"entry_ids": ["e1"]}
    h = client.post("/api/portfolio/preview", json=body).json()["content_hash"]
    db.fail_insert = True
    res = client.post(
        "/api/portfolio/exports", json={"selection": body, "content_hash": h}
    )
    assert res.status_code == 500 and "not downloaded" in res.json()["detail"]
    db.fail_insert = False

    def boom(manifest):
        raise RuntimeError("font missing")

    monkeypatch.setattr(portfolio_routes, "render_pdf", boom)
    res = client.post("/api/portfolio/preview", json=body)
    assert res.status_code == 500 and "nothing was exported" in res.json()["detail"]
    assert db.exports == []
    assert svc.FOOTER.startswith("Prepared from the consultant's own records")
