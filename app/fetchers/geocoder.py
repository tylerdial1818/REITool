"""Geocode an address via the US Census Geocoder API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def fetch_geocode(
    client: httpx.AsyncClient,
    address: str,
) -> dict[str, Any] | None:
    """Return lat, lon, FIPS codes, and resolved address — or *None* on failure."""
    url = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
    params = {
        "address": address,
        "benchmark": "Public_AR_Current",
        "vintage": "Census2020_Current",
        "format": "json",
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        matches = data.get("result", {}).get("addressMatches", [])
        if not matches:
            logger.warning("No address matches for %r", address)
            return None

        match = matches[0]
        coordinates = match["coordinates"]
        geographies = match.get("geographies", {})

        # County FIPS lives inside "Counties"
        county_entry = geographies.get("Counties", [{}])[0]
        county_fips = county_entry.get("COUNTY", "")
        state_fips = county_entry.get("STATE", "")

        # Block-group GEOID comes from "Census Blocks"
        block_entry = geographies.get("Census Blocks", [{}])[0]
        block_group_geoid = block_entry.get("GEOID", "")

        return {
            "lat": float(coordinates["y"]),
            "lon": float(coordinates["x"]),
            "county_fips": county_fips,
            "state_fips": state_fips,
            "block_group_geoid": block_group_geoid,
            "resolved_address": match.get("matchedAddress", ""),
        }

    except Exception:
        logger.exception("Geocoding failed for %r", address)
        return None
