"""Tests A-001 through A-034: FastAPI route integration tests."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from main import app
from app.schemas.output import BriefingOutput
from tests.conftest import load_fixture

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GEOCODER_RESULT = {
    "lat": 40.758896,
    "lon": -73.978674,
    "county_fips": "061",
    "state_fips": "36",
    "block_group_geoid": "360610076001",
    "resolved_address": "30 ROCKEFELLER PLZ, NEW YORK, NY, 10112",
}

GEOCODER_RESULT_NON_NYC = {
    "lat": 42.6526,
    "lon": -73.7562,
    "county_fips": "001",
    "state_fips": "36",
    "block_group_geoid": "360010001001",
    "resolved_address": "1 MAIN ST, ALBANY, NY, 12207",
}

ORPTS_RESULT = {
    "full_market_val": 850000000,
    "assessed_val": 382500000,
    "property_class_code": "410",
    "property_class_desc": "Living accomodations",
    "year_built": 1933,
    "sq_footage": 850000,
    "equalization_rate": "45.00",
}

ACS_RESULT = {
    "median_hh_income": 85000,
    "vacancy_rate": 0.0865,
    "renter_pct": 0.76,
}

FEMA_RESULT = {
    "flood_zone": "X",
    "flood_zone_description": "Minimal flood risk.",
}

BLS_RESULT = {
    "total_employment": 2850000,
    "employment_trend": "3.3% YoY growth",
    "dominant_industries": ["Finance", "Professional Services"],
}

TIGER_RESULT = {"type": "Polygon", "coordinates": []}
PLUTO_RESULT = {"type": "Polygon", "coordinates": []}


def _synthesis_output():
    return load_fixture("synthesis_valid_output")


def _patch_all_fetchers(
    geocoder=GEOCODER_RESULT,
    orpts=ORPTS_RESULT,
    acs=ACS_RESULT,
    fema=FEMA_RESULT,
    bls=BLS_RESULT,
    tiger=TIGER_RESULT,
    pluto=PLUTO_RESULT,
    synthesis=None,
):
    """Return a stack of patches for all fetchers + synthesis."""
    if synthesis is None:
        synthesis = BriefingOutput(**_synthesis_output())
    patches = [
        patch("app.api.routes.fetch_geocoder", new_callable=AsyncMock, return_value=geocoder),
        patch("app.api.routes.fetch_orpts", new_callable=AsyncMock, return_value=orpts),
        patch("app.api.routes.fetch_census_acs", new_callable=AsyncMock, return_value=acs),
        patch("app.api.routes.fetch_fema", new_callable=AsyncMock, return_value=fema),
        patch("app.api.routes.fetch_bls", new_callable=AsyncMock, return_value=bls),
        patch("app.api.routes.fetch_tiger", new_callable=AsyncMock, return_value=tiger),
        patch("app.api.routes.fetch_pluto", new_callable=AsyncMock, return_value=pluto),
        patch("app.api.routes.synthesize", new_callable=AsyncMock, return_value=synthesis),
    ]
    return patches


async def _post_analyze(client: httpx.AsyncClient, body: dict | None = None, **kwargs):
    return await client.post("/analyze", json=body, **kwargs)


# ---------------------------------------------------------------------------
# 5.1  Happy Path (A-001 .. A-004)
# ---------------------------------------------------------------------------

async def test_analyze_success_full_data():  # A-001
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200
    data = resp.json()
    assert "sections" in data
    assert "narrative" in data


async def test_analyze_success_partial_data():  # A-002
    patches = _patch_all_fetchers(fema=None, bls=None, tiger=None, pluto=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200


async def test_analyze_nyc_includes_pluto():  # A-003
    patches = _patch_all_fetchers(geocoder=GEOCODER_RESULT)  # NYC county 061
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
            pluto_mock = patches[6]  # fetch_pluto is index 6
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200
    assert pluto_mock.new.called  # pluto was invoked


async def test_analyze_non_nyc_excludes_pluto():  # A-004
    patches = _patch_all_fetchers(geocoder=GEOCODER_RESULT_NON_NYC, pluto=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "1 Main St, Albany, NY 12207"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200
    data = resp.json()
    # parcel_geometry should be null for non-NYC
    if "property_facts" in data:
        assert data["property_facts"].get("parcel_geometry") is None


# ---------------------------------------------------------------------------
# 5.2  Error Handling (A-010 .. A-015)
# ---------------------------------------------------------------------------

async def test_analyze_invalid_address_422():  # A-010
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await _post_analyze(client, {"address": ""})
    assert resp.status_code == 422


async def test_analyze_geocoder_failure_422():  # A-011
    patches = _patch_all_fetchers(geocoder=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "99999 Nonexistent St, Faketown, NY 00000"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 422
    assert "address" in resp.json().get("detail", "").lower() or "resolve" in resp.json().get("detail", "").lower()


async def test_analyze_geocoder_timeout_422():  # A-012
    geocoder_mock = AsyncMock(side_effect=Exception("timeout"))
    patches = _patch_all_fetchers()
    patches[0] = patch("app.api.routes.fetch_geocoder", new=geocoder_mock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 422


async def test_analyze_orpts_failure_degraded():  # A-013
    patches = _patch_all_fetchers(orpts=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200


async def test_analyze_synthesis_failure_500():  # A-014
    synth_mock = AsyncMock(side_effect=Exception("invalid JSON from Claude"))
    patches = _patch_all_fetchers()
    patches[7] = patch("app.api.routes.synthesize", new=synth_mock)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 500


async def test_analyze_all_optional_fetchers_fail():  # A-015
    patches = _patch_all_fetchers(orpts=None, acs=None, fema=None, bls=None, tiger=None, pluto=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5.3  Request Validation (A-020 .. A-022)
# ---------------------------------------------------------------------------

async def test_analyze_missing_body():  # A-020
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/analyze")
    assert resp.status_code == 422


async def test_analyze_wrong_content_type():  # A-021
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/analyze",
            content="address=30 Rockefeller Plaza",
            headers={"Content-Type": "text/plain"},
        )
    assert resp.status_code == 422


async def test_analyze_extra_fields_ignored():  # A-022
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {
                "address": "30 Rockefeller Plaza, New York, NY 10112",
                "extra_field": "should be ignored",
            })
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 5.4  Response Structure Validation (A-030 .. A-034)
# ---------------------------------------------------------------------------

async def test_response_contains_all_sections():  # A-030
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    data = resp.json()
    sections = data["sections"]
    assert "risk" in sections
    assert "price" in sections
    assert "location_quality" in sections
    assert "market_context" in sections


async def test_response_contains_property_facts():  # A-031
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    data = resp.json()
    pf = data["property_facts"]
    assert "property_class" in pf
    assert "year_built" in pf
    assert "building_sqft" in pf


async def test_response_contains_narrative():  # A-032
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    data = resp.json()
    assert isinstance(data["narrative"], str)
    assert len(data["narrative"]) > 0


async def test_response_talking_points_count():  # A-033
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    data = resp.json()
    assert 3 <= len(data["talking_points"]) <= 5


async def test_response_coordinates_present():  # A-034
    patches = _patch_all_fetchers()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await _post_analyze(client, {"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    data = resp.json()
    coords = data["coordinates"]
    assert isinstance(coords["lat"], float)
    assert isinstance(coords["lon"], float)
