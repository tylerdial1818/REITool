"""Output schemas returned by the REITool API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# ── Nested helper models ──────────────────────────────────────────────────


class Coordinates(BaseModel):
    """Latitude / longitude pair."""

    lat: float
    lon: float


# ── Section models ────────────────────────────────────────────────────────


class RiskSection(BaseModel):
    """Flood-risk and general risk assessment."""

    model_config = ConfigDict(populate_by_name=True)

    flood_zone: str | None = None
    flood_zone_description: str | None = None
    risk_score: int = Field(ge=1, le=5)
    risk_flags: list[str]


class PriceSection(BaseModel):
    """Assessed value and pricing metrics."""

    model_config = ConfigDict(populate_by_name=True)

    assessed_value: int | None = None
    full_market_value: int | None = None
    price_per_sqft: float | None = None
    equalization_note: str | None = None


class LocationQualitySection(BaseModel):
    """Demographic and location-quality indicators."""

    model_config = ConfigDict(populate_by_name=True)

    median_household_income: int | None = None
    vacancy_rate: float | None = None
    renter_pct: float | None = None
    population_trend: str | None = None
    block_group_geometry: dict | None = None  # GeoJSON


class MarketContextSection(BaseModel):
    """County-level employment and market data."""

    model_config = ConfigDict(populate_by_name=True)

    county: str | None = None
    total_employment: int | None = None
    employment_trend: str | None = None
    dominant_industries: list[str] | None = None


# ── Composite sections wrapper ────────────────────────────────────────────


class Sections(BaseModel):
    """All analysis sections grouped together."""

    risk: RiskSection
    price: PriceSection
    location_quality: LocationQualitySection
    market_context: MarketContextSection


# ── Property facts ────────────────────────────────────────────────────────


class PropertyFacts(BaseModel):
    """Physical property attributes and parcel geometry."""

    model_config = ConfigDict(populate_by_name=True)

    property_class: str | None = None
    year_built: int | None = None
    lot_size_sqft: float | None = None
    building_sqft: float | None = None
    parcel_geometry: dict | None = None  # GeoJSON


# ── Top-level API response ────────────────────────────────────────────────


class BriefingOutput(BaseModel):
    """Full briefing returned to the API consumer."""

    model_config = ConfigDict(populate_by_name=True)

    input_address: str
    resolved_address: str
    coordinates: Coordinates
    sections: Sections
    property_facts: PropertyFacts
    narrative: str
    talking_points: list[str] = Field(min_length=3)
