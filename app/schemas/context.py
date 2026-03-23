"""Internal property context assembled from parallel data fetchers.

This model is never returned directly to the API consumer.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class PropertyContext(BaseModel):
    """Aggregated context for a single property lookup.

    Required fields come from the geocoder; every other field is populated
    by its respective fetcher and defaults to ``None`` until filled.
    """

    model_config = ConfigDict(populate_by_name=True)

    # ── Required (geocoder) ───────────────────────────────────────────
    lat: float
    lon: float
    county_fips: str
    state_fips: str
    block_group_geoid: str
    resolved_address: str

    # ── ORPTS ─────────────────────────────────────────────────────────
    assessed_value: int | None = None
    full_market_value: int | None = None
    property_class_code: str | None = None
    year_built: int | None = None
    sq_footage: float | None = None
    lot_front: float | None = None
    lot_depth: float | None = None

    # ── ACS (American Community Survey) ───────────────────────────────
    median_hh_income: int | None = None
    vacancy_rate: float | None = None
    renter_pct: float | None = None
    total_population: int | None = None

    # ── FEMA ──────────────────────────────────────────────────────────
    flood_zone: str | None = None
    flood_zone_description: str | None = None

    # ── BLS (Bureau of Labor Statistics) ──────────────────────────────
    total_employment: int | None = None
    employment_trend: str | None = None
    dominant_industries: list[str] | None = None

    # ── TIGER ─────────────────────────────────────────────────────────
    block_group_geometry: dict | None = None  # GeoJSON

    # ── PLUTO ─────────────────────────────────────────────────────────
    parcel_geometry: dict | None = None  # GeoJSON
