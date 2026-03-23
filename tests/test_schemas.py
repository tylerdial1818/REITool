"""Tests S-001 through S-024: Pydantic schema validation."""

import json

import pytest
from pydantic import ValidationError

from app.schemas.input import AddressInput
from app.schemas.context import PropertyContext
from app.schemas.output import BriefingOutput
from tests.conftest import load_fixture


# ---------------------------------------------------------------------------
# S-001 .. S-003  AddressInput
# ---------------------------------------------------------------------------

def test_valid_address_input():  # S-001
    addr = AddressInput(address="30 Rockefeller Plaza, New York, NY 10112")
    assert addr.address == "30 Rockefeller Plaza, New York, NY 10112"


def test_empty_address_rejected():  # S-002
    with pytest.raises(ValidationError):
        AddressInput(address="")


def test_whitespace_only_rejected():  # S-003
    with pytest.raises(ValidationError):
        AddressInput(address="   ")


# ---------------------------------------------------------------------------
# S-010 .. S-012  PropertyContext
# ---------------------------------------------------------------------------

def test_property_context_full_data():  # S-010
    ctx = PropertyContext(
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
    assert ctx.lat == pytest.approx(40.758896)
    assert ctx.county_fips == "061"


def test_property_context_nullable_fields():  # S-011
    ctx = PropertyContext(
        address="30 Rockefeller Plaza, New York, NY 10112",
        resolved_address="30 ROCKEFELLER PLZ, NEW YORK, NY, 10112",
        lat=40.758896,
        lon=-73.978674,
        county_fips="061",
        state_fips="36",
        block_group_geoid="360610076001",
        full_market_val=None,
        assessed_val=None,
        property_class_code=None,
        year_built=None,
        sq_footage=None,
        median_hh_income=None,
        vacancy_rate=None,
        renter_pct=None,
        flood_zone=None,
        flood_zone_description=None,
        total_employment=None,
        employment_trend=None,
        dominant_industries=None,
        block_group_geometry=None,
        parcel_geometry=None,
        equalization_rate=None,
    )
    assert ctx.full_market_val is None
    assert ctx.flood_zone is None


def test_property_context_requires_geocoder_fields():  # S-012
    with pytest.raises(ValidationError):
        PropertyContext(
            address="30 Rockefeller Plaza, New York, NY 10112",
            resolved_address="30 ROCKEFELLER PLZ",
            # lat, lon, county_fips intentionally omitted
        )


# ---------------------------------------------------------------------------
# S-020 .. S-024  BriefingOutput
# ---------------------------------------------------------------------------

def test_briefing_output_full():  # S-020
    data = load_fixture("synthesis_valid_output")
    output = BriefingOutput(**data)
    assert output.narrative
    assert output.coordinates.lat == pytest.approx(40.758896)


def test_briefing_output_nullable_sections():  # S-021
    data = load_fixture("synthesis_valid_output")
    data["sections"]["market_context"]["total_employment"] = None
    data["sections"]["location_quality"]["vacancy_rate"] = None
    output = BriefingOutput(**data)
    assert output.sections.market_context.total_employment is None


def test_briefing_output_risk_score_range():  # S-022
    data = load_fixture("synthesis_valid_output")
    data["sections"]["risk"]["risk_score"] = 7
    with pytest.raises(ValidationError):
        BriefingOutput(**data)


def test_briefing_output_talking_points_count():  # S-023
    data = load_fixture("synthesis_valid_output")
    data["talking_points"] = []
    with pytest.raises(ValidationError):
        BriefingOutput(**data)


def test_briefing_output_serialization():  # S-024
    data = load_fixture("synthesis_valid_output")
    output = BriefingOutput(**data)
    json_str = output.model_dump_json()
    roundtrip = BriefingOutput.model_validate_json(json_str)
    assert roundtrip == output
