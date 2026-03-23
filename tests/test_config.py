"""Tests C-001 through C-003: Configuration / settings."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_loads_from_env(monkeypatch):  # C-001
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("CENSUS_API_KEY", "census-test-key")
    monkeypatch.setenv("BLS_API_KEY", "bls-test-key")
    settings = Settings()
    assert settings.ANTHROPIC_API_KEY == "sk-ant-test-key"
    assert settings.CENSUS_API_KEY == "census-test-key"
    assert settings.BLS_API_KEY == "bls-test-key"


def test_settings_missing_required_key(monkeypatch):  # C-002
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)
    monkeypatch.delenv("BLS_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        Settings()


def test_default_timeout(monkeypatch):  # C-003
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key")
    monkeypatch.setenv("CENSUS_API_KEY", "census-test-key")
    monkeypatch.setenv("BLS_API_KEY", "bls-test-key")
    settings = Settings()
    assert settings.fetcher_timeout_seconds == 8
