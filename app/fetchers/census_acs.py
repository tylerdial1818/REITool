"""Fetch ACS 5-year estimates from the Census Bureau API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_VARIABLES = "B19013_001E,B25002_003E,B25002_001E,B25003_003E,B25003_001E"


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    """Return numerator/denominator as a float, or None when impossible."""
    try:
        n, d = float(numerator), float(denominator)
        if d == 0:
            return None
        return round(n / d, 4)
    except (TypeError, ValueError):
        return None


async def fetch_census_acs(
    client: httpx.AsyncClient,
    geoid: str,
    state_fips: str,
    county_fips: str,
) -> dict[str, Any] | None:
    """Return median household income, vacancy rate, and renter percentage."""
    url = "https://api.census.gov/data/2022/acs/acs5"

    # GEOID for a block group: STATE(2) + COUNTY(3) + TRACT(6) + BG(1)
    # Tract is characters [5:11], block group is character [11]
    if len(geoid) < 12:
        logger.warning("GEOID too short to decompose: %r", geoid)
        return None

    tract = geoid[5:11]
    block_group = geoid[11]

    settings = get_settings()
    params = {
        "get": f"NAME,{_VARIABLES}",
        "for": f"block group:{block_group}",
        "in": f"state:{state_fips} county:{county_fips} tract:{tract}",
        "key": settings.census_api_key,
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        # Census API returns a list of lists; first row is headers.
        if len(data) < 2:
            logger.info("No ACS data returned for GEOID %s", geoid)
            return None

        headers = data[0]
        values = data[1]
        row = dict(zip(headers, values))

        median_hh_income = row.get("B19013_001E")
        vacancy_rate = _safe_divide(
            row.get("B25002_003E"), row.get("B25002_001E")
        )
        renter_pct = _safe_divide(
            row.get("B25003_003E"), row.get("B25003_001E")
        )

        # Census uses -666666666 as a suppression sentinel
        try:
            income_val = int(median_hh_income) if median_hh_income not in (None, "") else None
            if income_val is not None and income_val < 0:
                income_val = None
        except (ValueError, TypeError):
            income_val = None

        return {
            "median_hh_income": income_val,
            "vacancy_rate": vacancy_rate,
            "renter_pct": renter_pct,
        }

    except Exception:
        logger.exception("Census ACS fetch failed for GEOID %s", geoid)
        return None
