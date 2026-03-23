"""Fetch parcel geometry from NYC's MapPLUTO dataset (NYC only)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

NYC_FIPS: set[str] = {"36005", "36047", "36061", "36081", "36085"}


async def fetch_pluto(
    client: httpx.AsyncClient,
    address: str,
    county_fips: str,
) -> dict[str, Any] | None:
    """Return the GeoJSON geometry for an NYC parcel, or *None* outside NYC."""
    # Full county FIPS = state (36) + county
    full_fips = f"36{county_fips}" if len(county_fips) == 3 else county_fips
    if full_fips not in NYC_FIPS:
        return None

    url = "https://data.cityofnewyork.us/resource/64uk-42ks.geojson"
    params = {
        "$where": f"upper(address) LIKE '%{address.upper().replace(chr(39), chr(39)+chr(39))}%'",
        "$limit": "1",
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            logger.info("No PLUTO features for %r", address)
            return None

        return features[0].get("geometry")

    except Exception:
        logger.exception("PLUTO fetch failed for %r", address)
        return None
