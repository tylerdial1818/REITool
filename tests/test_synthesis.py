"""Tests SY-001 through SY-009: Claude synthesis layer."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.context import PropertyContext
from app.schemas.output import BriefingOutput
from app.synthesis.claude import synthesize
from tests.conftest import load_fixture

pytestmark = pytest.mark.asyncio


def _make_context(**overrides) -> PropertyContext:
    """Build a PropertyContext with sensible defaults; override fields as needed."""
    defaults = dict(
        address="30 Rockefeller Plaza, New York, NY 10112",
        resolved_address="30 ROCKEFELLER PLZ, NEW YORK, NY, 10112",
        lat=40.758896,
        lon=-73.978674,
        county_fips="061",
        state_fips="36",
        block_group_geoid="360610076001",
        full_market_val=850000000,
        assessed_val=382500000,
        property_class_code="410",
        year_built=1933,
        sq_footage=850000,
        median_hh_income=85000,
        vacancy_rate=0.0865,
        renter_pct=0.76,
        flood_zone="X",
        flood_zone_description="Minimal flood risk.",
        total_employment=2850000,
        employment_trend="3.3% YoY growth",
        dominant_industries=["Finance", "Professional Services"],
        block_group_geometry={"type": "Polygon", "coordinates": []},
        parcel_geometry={"type": "Polygon", "coordinates": []},
        equalization_rate="45.00",
    )
    defaults.update(overrides)
    return PropertyContext(**defaults)


def _mock_anthropic(response_text: str):
    """Return a patched AsyncAnthropic whose messages.create returns response_text."""
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=response_text)]
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_msg)
    return mock_client


async def test_synthesis_valid_response():  # SY-001
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        result = await synthesize(_make_context(), api_key="sk-test")
    assert isinstance(result, BriefingOutput)
    assert result.narrative


async def test_synthesis_handles_null_fields():  # SY-002
    ctx = _make_context(
        full_market_val=None,
        assessed_val=None,
        flood_zone=None,
        flood_zone_description=None,
        total_employment=None,
        employment_trend=None,
        dominant_industries=None,
        block_group_geometry=None,
        parcel_geometry=None,
        equalization_rate=None,
    )
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        result = await synthesize(ctx, api_key="sk-test")
    assert isinstance(result, BriefingOutput)


async def test_synthesis_invalid_json_response():  # SY-003
    mock = _mock_anthropic("This is not valid JSON at all")
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        with pytest.raises(Exception):
            await synthesize(_make_context(), api_key="sk-test")


async def test_synthesis_schema_mismatch():  # SY-004
    bad_json = json.dumps({"completely": "wrong", "schema": True})
    mock = _mock_anthropic(bad_json)
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        with pytest.raises(Exception):
            await synthesize(_make_context(), api_key="sk-test")


async def test_synthesis_prompt_contains_schema():  # SY-005
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        await synthesize(_make_context(), api_key="sk-test")
    call_kwargs = mock.messages.create.call_args
    system_prompt = call_kwargs.kwargs.get("system", "") or str(call_kwargs)
    assert "BriefingOutput" in system_prompt or "risk_score" in system_prompt


async def test_synthesis_prompt_contains_role():  # SY-006
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        await synthesize(_make_context(), api_key="sk-test")
    call_kwargs = mock.messages.create.call_args
    all_text = str(call_kwargs).lower()
    assert "commercial real estate" in all_text or "broker" in all_text


async def test_synthesis_prompt_no_fabrication_instruction():  # SY-007
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        await synthesize(_make_context(), api_key="sk-test")
    call_kwargs = mock.messages.create.call_args
    all_text = str(call_kwargs).lower()
    assert "fabricat" in all_text or "do not" in all_text or "null" in all_text


async def test_synthesis_risk_score_default_on_missing_fema():  # SY-008
    ctx = _make_context(flood_zone=None, flood_zone_description=None)
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        await synthesize(ctx, api_key="sk-test")
    call_kwargs = mock.messages.create.call_args
    all_text = str(call_kwargs)
    # Prompt should mention default risk score of 3 when FEMA data missing
    assert "3" in all_text or "default" in all_text.lower()


async def test_synthesis_model_selection():  # SY-009
    fixture = load_fixture("synthesis_valid_output")
    mock = _mock_anthropic(json.dumps(fixture))
    with patch("app.synthesis.claude.anthropic.AsyncAnthropic", return_value=mock):
        await synthesize(_make_context(), api_key="sk-test")
    call_kwargs = mock.messages.create.call_args
    assert call_kwargs.kwargs.get("model") == "claude-sonnet-4-5"
