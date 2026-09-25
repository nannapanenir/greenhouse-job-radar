from pathlib import Path

import pytest

from agent.adapters import FixtureTransport

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def transport() -> FixtureTransport:
    return FixtureTransport(FIXTURES)
