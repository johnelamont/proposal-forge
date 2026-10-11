"""The shared vocabulary: one JSON in the backend, an identical copy in the
frontend (Vercel builds cannot read outside frontend/). This test keeps the
two from drifting; it runs wherever the repo is checked out and is skipped in
the backend-only Docker image."""

import json
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1] / "app" / "config" / "picklists.json"
FRONTEND = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "picklists.json"
)


def test_backend_picklists_are_well_formed():
    data = json.loads(BACKEND.read_text(encoding="utf-8"))
    for key in ("industry", "job_type"):
        values = data[key]
        assert values and len(values) == len(set(values)), key
        assert values[-1] == "Other", f"{key} must end with the honest fallback"
    t = data["thresholds"]
    assert {"Industry", "Job_Type", "Tools"} <= set(t)
    assert all(0 < v <= 1 for k, v in t.items() if not k.startswith("_"))


@pytest.mark.skipif(not FRONTEND.exists(), reason="frontend not checked out")
def test_frontend_copy_is_identical():
    assert json.loads(FRONTEND.read_text(encoding="utf-8")) == json.loads(
        BACKEND.read_text(encoding="utf-8")
    )
