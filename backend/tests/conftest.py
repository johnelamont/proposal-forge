from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


@pytest.fixture
def desktop_hourly() -> str:
    return load_fixture("job_desktop_hourly_zoho_consulting.txt")


@pytest.fixture
def desktop_conflict() -> str:
    return load_fixture("job_desktop_hourly_vs_fixed_conflict_mortgage.txt")


@pytest.fixture
def mobile_relayed() -> str:
    return load_fixture("job_mobile_relayed_airtable_law_dashboard.txt")
