"""Shared test fixtures for REITool."""

import json
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> dict | list:
    """Load a JSON fixture file by name (with or without .json extension)."""
    if not name.endswith(".json"):
        name = f"{name}.json"
    path = FIXTURES_DIR / name
    return json.loads(path.read_text())


@pytest.fixture
def mock_client():
    """Provide a respx-mocked httpx.AsyncClient for fetcher tests."""
    with respx.mock(assert_all_called=False) as respx_mock:
        async with httpx.AsyncClient() as client:
            yield client, respx_mock
