"""The shared vocabulary (picklists.json): Zoho Lead picklists, Work-history
vertical and project type, and the F6 confidence thresholds."""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).with_name("picklists.json")
_DATA = json.loads(_PATH.read_text(encoding="utf-8"))

INDUSTRY: list[str] = list(_DATA["industry"])
JOB_TYPE: list[str] = list(_DATA["job_type"])
THRESHOLDS: dict[str, float] = {
    k: float(v) for k, v in _DATA["thresholds"].items() if not k.startswith("_")
}
