"""Tests E-001 through E-007: Edge cases."""

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from main import app
from app.schemas.output import BriefingOutput
from tests.conftest import load_fixture

from app.fetchers.geocoder import fetch_geocoder
from app.fetchers.orpts import fetch_orpts
from app.fetchers.census_acs import fetch_census_acs
from app.fetchers.bls import fetch_bls

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Shared mock data
# ---------------------------------------------------------------------------

GEOCODER_RESULT_NYC = {
    "lat": 40.748817,
    "lon": -73.985428,
    "county_fips": "061",
    "state_fips": "36",
    "block_group_geoid": "360610076001",
    "resolved_address": "350 FIFTH AVE UNIT 5A, NEW YORK, NY, 10118",
}

GEOCODER_RESULT_RURAL = {
    "lat": 43.0481,
    "lon": -76.1474,
    "county_fips": "067",
    "state_fips": "36",
    "block_group_geoid": "360670001001",
    "resolved_address": "100 MAIN ST, SYRACUSE, NY, 13202",
}

ORPTS_RESULT = {
    "full_market_val": 5000000,
    "assessed_val": 2250000,
    "property_class_code": "421",
    "property_class_desc": "Retail store",
    "year_built": 1920,
    "sq_footage": 12000,
    "equalization_rate": "45.00",
}

ACS_RESULT = {"median_hh_income": 55000, "vacancy_rate": 0.12, "renter_pct": 0.65}
FEMA_RESULT = {"flood_zone": "X", "flood_zone_description": "Minimal flood risk."}
BLS_RESULT = {"total_employment": 500000, "employment_trend": "1.2% YoY", "dominant_industries": ["Healthcare"]}
TIGER_RESULT = {"type": "Polygon", "coordinates": []}


def _synthesis_output():
    return BriefingOutput(**load_fixture("synthesis_valid_output"))


def _all_patches(**overrides):
    defaults = dict(
        geocoder=GEOCODER_RESULT_NYC,
        orpts=ORPTS_RESULT,
        acs=ACS_RESULT,
        fema=FEMA_RESULT,
        bls=BLS_RESULT,
        tiger=TIGER_RESULT,
        pluto=None,
        synthesis=_synthesis_output(),
    )
    defaults.update(overrides)
    return [
        patch("app.api.routes.fetch_geocoder", new_callable=AsyncMock, return_value=defaults["geocoder"]),
        patch("app.api.routes.fetch_orpts", new_callable=AsyncMock, return_value=defaults["orpts"]),
        patch("app.api.routes.fetch_census_acs", new_callable=AsyncMock, return_value=defaults["acs"]),
        patch("app.api.routes.fetch_fema", new_callable=AsyncMock, return_value=defaults["fema"]),
        patch("app.api.routes.fetch_bls", new_callable=AsyncMock, return_value=defaults["bls"]),
        patch("app.api.routes.fetch_tiger", new_callable=AsyncMock, return_value=defaults["tiger"]),
        patch("app.api.routes.fetch_pluto", new_callable=AsyncMock, return_value=defaults["pluto"]),
        patch("app.api.routes.synthesize", new_callable=AsyncMock, return_value=defaults["synthesis"]),
    ]


# ---------------------------------------------------------------------------
# E-001  Address with unit number
# ---------------------------------------------------------------------------

async def test_address_with_unit_number():  # E-001
    patches = _all_patches(geocoder=GEOCODER_RESULT_NYC)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await client.post("/analyze", json={"address": "350 Fifth Ave Unit 5A, New York, NY"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# E-002  PO Box address
# ---------------------------------------------------------------------------

async def test_address_with_po_box():  # E-002
    patches = _all_patches(geocoder=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await client.post("/analyze", json={"address": "PO Box 123, Albany, NY 12201"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# E-003  Rural NY address (non-NYC)
# ---------------------------------------------------------------------------

async def test_rural_ny_address():  # E-003
    patches = _all_patches(geocoder=GEOCODER_RESULT_RURAL, pluto=None)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await client.post("/analyze", json={"address": "100 Main St, Syracuse, NY 13202"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200
    data = resp.json()
    if "property_facts" in data:
        assert data["property_facts"].get("parcel_geometry") is None


# ---------------------------------------------------------------------------
# E-004  ORPTS equalization note present
# ---------------------------------------------------------------------------

async def test_orpts_equalization_note_present():  # E-004
    patches = _all_patches()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            resp = await client.post("/analyze", json={"address": "30 Rockefeller Plaza, New York, NY 10112"})
        finally:
            for p in patches:
                p.stop()
    assert resp.status_code == 200
    data = resp.json()
    eq_note = data.get("sections", {}).get("price", {}).get("equalization_note")
    assert eq_note is not None and len(eq_note) > 0


# ---------------------------------------------------------------------------
# E-005  Census ACS zero population block (division by zero)
# ---------------------------------------------------------------------------

@respx.mock
async def test_census_acs_zero_population_block():  # E-005
    fixture = [
        ["B19013_001E", "B25002_003E", "B25002_001E", "B25003_003E", "B25003_001E",
         "state", "county", "tract", "block group"],
        ["0", "0", "0", "0", "0", "36", "061", "007600", "1"],
    ]
    respx.get(url__startswith="https://api.census.gov/data/").mock(
        return_value=httpx.Response(200, json=fixture)
    )
    async with httpx.AsyncClient() as client:
        result = await fetch_census_acs(client, "360610076001", api_key="test-key")
    if result is not None:
        assert result["vacancy_rate"] is None or result["vacancy_rate"] == 0.0
        assert result["renter_pct"] is None or result["renter_pct"] == 0.0


# ---------------------------------------------------------------------------
# E-006  BLS county with no data
# ---------------------------------------------------------------------------

@respx.mock
async def test_bls_county_with_no_data():  # E-006
    fixture = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {"series": []},
    }
    respx.get(url__startswith="https://api.bls.gov/publicAPI/v2/timeseries/data/").mock(
        return_value=httpx.Response(200, json=fixture)
    )
    async with httpx.AsyncClient() as client:
        result = await fetch_bls(client, county_fips="999", state_fips="36", api_key="test-key")
    assert result is None


# ---------------------------------------------------------------------------
# E-007  Concurrent requests (no shared state corruption)
# ---------------------------------------------------------------------------

async def test_concurrent_requests():  # E-007
    patches = _all_patches()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        for p in patches:
            p.start()
        try:
            tasks = [
                client.post("/analyze", json={"address": f"Address {i}, New York, NY"})
                for i in range(3)
            ]
            responses = await asyncio.gather(*tasks)
        finally:
            for p in patches:
                p.stop()
    for resp in responses:
        assert resp.status_code == 200
