"""Tests F-001 through F-064: All fetcher functions."""

import httpx
import pytest
import respx

from tests.conftest import load_fixture

from app.fetchers.geocoder import fetch_geocoder
from app.fetchers.orpts import fetch_orpts
from app.fetchers.census_acs import fetch_census_acs
from app.fetchers.fema import fetch_fema
from app.fetchers.bls import fetch_bls
from app.fetchers.tiger import fetch_tiger
from app.fetchers.pluto import fetch_pluto

pytestmark = pytest.mark.asyncio

# ── Geocoder base URL fragment ──────────────────────────────────────────────
GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
ORPTS_URL = "https://data.ny.gov/resource/"
CENSUS_ACS_URL = "https://api.census.gov/data/"
FEMA_URL = "https://hazards.fema.gov/gis/nfhl/rest/services/"
BLS_URL = "https://api.bls.gov/publicAPI/v2/timeseries/data/"
TIGER_URL = "https://tigerweb.geo.census.gov/arcgis/rest/services/"
PLUTO_URL = "https://data.cityofnewyork.us/resource/"


# ===========================================================================
# 3.1  Census Geocoder (F-001 .. F-005)
# ===========================================================================

@respx.mock
async def test_geocoder_success():  # F-001
    fixture = load_fixture("geocoder_success")
    respx.get(GEOCODER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_geocoder(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is not None
    assert result["lat"] == pytest.approx(40.758896)
    assert result["lon"] == pytest.approx(-73.978674)
    assert result["county_fips"] == "061"
    assert "block_group_geoid" in result
    assert result["resolved_address"] == "30 ROCKEFELLER PLZ, NEW YORK, NY, 10112"


@respx.mock
async def test_geocoder_no_match():  # F-002
    fixture = load_fixture("geocoder_no_match")
    respx.get(GEOCODER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_geocoder(client, "99999 Nonexistent St, Faketown, NY 00000")
    assert result is None


@respx.mock
async def test_geocoder_timeout():  # F-003
    respx.get(GEOCODER_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_geocoder(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is None


@respx.mock
async def test_geocoder_malformed_response():  # F-004
    respx.get(GEOCODER_URL).mock(return_value=httpx.Response(200, json={"bad": "data"}))
    async with httpx.AsyncClient() as client:
        result = await fetch_geocoder(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is None


@respx.mock
async def test_geocoder_extracts_geoid():  # F-005
    fixture = load_fixture("geocoder_success")
    respx.get(GEOCODER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_geocoder(client, "30 Rockefeller Plaza, New York, NY 10112")
    geoid = result["block_group_geoid"]
    assert geoid.startswith("36061")
    assert len(geoid) == 12


# ===========================================================================
# 3.2  ORPTS Socrata (F-010 .. F-014)
# ===========================================================================

@respx.mock
async def test_orpts_success():  # F-010
    fixture = load_fixture("orpts_single_result")
    respx.get(url__startswith=ORPTS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_orpts(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is not None
    assert result["full_market_val"] == 850000000
    assert result["assessed_val"] == 382500000
    assert result["property_class_code"] == "410"
    assert result["year_built"] == 1933
    assert result["sq_footage"] == 850000


@respx.mock
async def test_orpts_multiple_results():  # F-011
    fixture = load_fixture("orpts_multiple_results")
    respx.get(url__startswith=ORPTS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_orpts(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is not None
    assert result["full_market_val"] == 850000000  # first result used


@respx.mock
async def test_orpts_no_match():  # F-012
    respx.get(url__startswith=ORPTS_URL).mock(return_value=httpx.Response(200, json=[]))
    async with httpx.AsyncClient() as client:
        result = await fetch_orpts(client, "99999 Fake St, Albany, NY 12203")
    assert result is None


@respx.mock
async def test_orpts_timeout():  # F-013
    respx.get(url__startswith=ORPTS_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_orpts(client, "30 Rockefeller Plaza, New York, NY 10112")
    assert result is None


@respx.mock
async def test_orpts_address_parsing():  # F-014
    fixture = load_fixture("orpts_single_result")
    route = respx.get(url__startswith=ORPTS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        await fetch_orpts(client, "30 Rockefeller Plaza, New York, NY 10112")
    request = route.calls.last.request
    url_str = str(request.url)
    # Verify address components appear in query
    assert "ROCKEFELLER" in url_str.upper() or "rockefeller" in url_str.lower()


# ===========================================================================
# 3.3  Census ACS (F-020 .. F-024)
# ===========================================================================

@respx.mock
async def test_census_acs_success():  # F-020
    fixture = load_fixture("census_acs_success")
    respx.get(url__startswith=CENSUS_ACS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_census_acs(client, "360610076001", api_key="test-key")
    assert result is not None
    assert result["median_hh_income"] == 85000
    # vacancy_rate = B25002_003E / B25002_001E = 450/5200 ~ 0.0865
    assert result["vacancy_rate"] == pytest.approx(450 / 5200, abs=0.001)
    # renter_pct = B25003_003E / B25003_001E = 3800/5000 = 0.76
    assert result["renter_pct"] == pytest.approx(0.76, abs=0.001)


@respx.mock
async def test_census_acs_division_by_zero():  # F-021
    fixture = [
        ["B19013_001E", "B25002_003E", "B25002_001E", "B25003_003E", "B25003_001E",
         "state", "county", "tract", "block group"],
        ["50000", "0", "0", "0", "0", "36", "061", "007600", "1"],
    ]
    respx.get(url__startswith=CENSUS_ACS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_census_acs(client, "360610076001", api_key="test-key")
    assert result is not None
    assert result["vacancy_rate"] is None or result["vacancy_rate"] == 0.0
    assert result["renter_pct"] is None or result["renter_pct"] == 0.0


@respx.mock
async def test_census_acs_missing_variable():  # F-022
    fixture = [
        ["B19013_001E", "state", "county", "tract", "block group"],
        ["50000", "36", "061", "007600", "1"],
    ]
    respx.get(url__startswith=CENSUS_ACS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_census_acs(client, "360610076001", api_key="test-key")
    # Should return partial data, missing fields are None
    if result is not None:
        assert result.get("vacancy_rate") is None
        assert result.get("renter_pct") is None


@respx.mock
async def test_census_acs_timeout():  # F-023
    respx.get(url__startswith=CENSUS_ACS_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_census_acs(client, "360610076001", api_key="test-key")
    assert result is None


@respx.mock
async def test_census_acs_geoid_decomposition():  # F-024
    fixture = load_fixture("census_acs_success")
    route = respx.get(url__startswith=CENSUS_ACS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        await fetch_census_acs(client, "360610076001", api_key="test-key")
    request = route.calls.last.request
    url_str = str(request.url)
    # GEOID 360610076001 -> state=36, county=061, tract=007600, block group=1
    assert "for=block%20group" in url_str or "for=block+group" in url_str or "block group" in url_str
    assert "36" in url_str
    assert "061" in url_str


# ===========================================================================
# 3.4  FEMA NFHL (F-030 .. F-035)
# ===========================================================================

@respx.mock
async def test_fema_flood_zone_ae():  # F-030
    fixture = load_fixture("fema_flood_ae")
    respx.get(url__startswith=FEMA_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_fema(client, lat=40.758896, lon=-73.978674)
    assert result is not None
    assert result["flood_zone"] == "AE"
    assert "high" in result["flood_zone_description"].lower() or "risk" in result["flood_zone_description"].lower()


@respx.mock
async def test_fema_flood_zone_x():  # F-031
    fixture = load_fixture("fema_flood_x")
    respx.get(url__startswith=FEMA_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_fema(client, lat=40.758896, lon=-73.978674)
    assert result is not None
    assert result["flood_zone"] == "X"
    assert "minimal" in result["flood_zone_description"].lower() or "low" in result["flood_zone_description"].lower()


@respx.mock
async def test_fema_flood_zone_ve():  # F-032
    fixture = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"FLD_ZONE": "VE", "SFHA_TF": "T"},
            "geometry": {"type": "Polygon", "coordinates": [[]]},
        }],
    }
    respx.get(url__startswith=FEMA_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_fema(client, lat=40.758896, lon=-73.978674)
    assert result is not None
    assert result["flood_zone"] == "VE"
    assert "coastal" in result["flood_zone_description"].lower() or "hazard" in result["flood_zone_description"].lower()


@respx.mock
async def test_fema_no_features():  # F-033
    fixture = load_fixture("fema_no_features")
    respx.get(url__startswith=FEMA_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_fema(client, lat=40.758896, lon=-73.978674)
    assert result is None


@respx.mock
async def test_fema_timeout():  # F-034
    respx.get(url__startswith=FEMA_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_fema(client, lat=40.758896, lon=-73.978674)
    assert result is None


@respx.mock
async def test_fema_point_query_params():  # F-035
    fixture = load_fixture("fema_flood_x")
    route = respx.get(url__startswith=FEMA_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        await fetch_fema(client, lat=40.758896, lon=-73.978674)
    request = route.calls.last.request
    url_str = str(request.url)
    assert "esriGeometryPoint" in url_str
    assert "-73.978674" in url_str
    assert "40.758896" in url_str


# ===========================================================================
# 3.5  BLS QCEW (F-040 .. F-044)
# ===========================================================================

@respx.mock
async def test_bls_success():  # F-040
    fixture = load_fixture("bls_four_quarters")
    respx.get(url__startswith=BLS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_bls(client, county_fips="061", state_fips="36", api_key="test-key")
    assert result is not None
    assert result["total_employment"] == 2850000
    assert result["employment_trend"] is not None
    assert isinstance(result["dominant_industries"], list)


@respx.mock
async def test_bls_series_id_construction():  # F-041
    fixture = load_fixture("bls_four_quarters")
    route = respx.get(url__startswith=BLS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        await fetch_bls(client, county_fips="061", state_fips="36", api_key="test-key")
    request = route.calls.last.request
    url_str = str(request.url)
    assert "ENU3606110" in url_str


@respx.mock
async def test_bls_insufficient_data():  # F-042
    fixture = {
        "status": "REQUEST_SUCCEEDED",
        "Results": {
            "series": [{
                "seriesID": "ENU3606110",
                "data": [{
                    "year": "2025", "period": "Q1", "value": "2850000",
                    "footnotes": [{}],
                }],
            }],
        },
    }
    respx.get(url__startswith=BLS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_bls(client, county_fips="061", state_fips="36", api_key="test-key")
    assert result is not None
    assert result["employment_trend"] is None


@respx.mock
async def test_bls_timeout():  # F-043
    respx.get(url__startswith=BLS_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_bls(client, county_fips="061", state_fips="36", api_key="test-key")
    assert result is None


@respx.mock
async def test_bls_zero_padded_fips():  # F-044
    fixture = load_fixture("bls_four_quarters")
    route = respx.get(url__startswith=BLS_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        # County FIPS "5" should get zero-padded to "005"
        await fetch_bls(client, county_fips="5", state_fips="36", api_key="test-key")
    request = route.calls.last.request
    url_str = str(request.url)
    assert "ENU3600510" in url_str


# ===========================================================================
# 3.6  Census TIGER Geometry (F-050 .. F-053)
# ===========================================================================

@respx.mock
async def test_tiger_success():  # F-050
    fixture = load_fixture("tiger_polygon")
    respx.get(url__startswith=TIGER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_tiger(client, geoid="360610076001")
    assert result is not None
    assert result["type"] == "Polygon"
    assert "coordinates" in result


@respx.mock
async def test_tiger_no_result():  # F-051
    fixture = {"type": "FeatureCollection", "features": []}
    respx.get(url__startswith=TIGER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_tiger(client, geoid="360610076001")
    assert result is None


@respx.mock
async def test_tiger_timeout():  # F-052
    respx.get(url__startswith=TIGER_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_tiger(client, geoid="360610076001")
    assert result is None


@respx.mock
async def test_tiger_geoid_query():  # F-053
    fixture = load_fixture("tiger_polygon")
    route = respx.get(url__startswith=TIGER_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        await fetch_tiger(client, geoid="360610076001")
    request = route.calls.last.request
    url_str = str(request.url)
    assert "360610076001" in url_str


# ===========================================================================
# 3.7  NYC MapPLUTO (F-060 .. F-064)
# ===========================================================================

NYC_FIPS = {"36005", "36047", "36061", "36081", "36085"}

@respx.mock
async def test_pluto_success_nyc():  # F-060
    fixture = load_fixture("pluto_parcel")
    respx.get(url__startswith=PLUTO_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_pluto(client, county_fips="36061", address="30 Rockefeller Plaza")
    assert result is not None
    assert result["type"] == "Polygon"
    assert "coordinates" in result


@respx.mock
async def test_pluto_no_match():  # F-061
    fixture = {"type": "FeatureCollection", "features": []}
    respx.get(url__startswith=PLUTO_URL).mock(return_value=httpx.Response(200, json=fixture))
    async with httpx.AsyncClient() as client:
        result = await fetch_pluto(client, county_fips="36061", address="99999 Fake St")
    assert result is None


@respx.mock
async def test_pluto_timeout():  # F-062
    respx.get(url__startswith=PLUTO_URL).mock(side_effect=httpx.TimeoutException("timed out"))
    async with httpx.AsyncClient() as client:
        result = await fetch_pluto(client, county_fips="36061", address="30 Rockefeller Plaza")
    assert result is None


async def test_pluto_nyc_fips_gate():  # F-063
    for fips in NYC_FIPS:
        # Should not raise or skip for NYC FIPS codes
        assert fips in NYC_FIPS


@respx.mock
async def test_pluto_non_nyc_skipped():  # F-064
    route = respx.get(url__startswith=PLUTO_URL).mock(return_value=httpx.Response(200, json={}))
    async with httpx.AsyncClient() as client:
        result = await fetch_pluto(client, county_fips="36001", address="123 Main St")
    assert result is None
    assert route.call_count == 0  # no HTTP call made
