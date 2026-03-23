"""Fetch block-group geometry from the TIGERweb ArcGIS service."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def fetch_tiger(
    client: httpx.AsyncClient,
    geoid: str,
) -> dict[str, Any] | None:
    """Return the GeoJSON geometry for the given block-group GEOID."""
    url = (
        "https://tigerweb.geo.census.gov/arcgis/rest/services/"
        "TIGERweb/tigerWMS_Census2020/MapServer/10/query"
    )
    params = {
        "where": f"GEOID='{geoid}'",
        "outFields": "*",
        "f": "geojson",
        "returnGeometry": "true",
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            logger.info("No TIGER features for GEOID %s", geoid)
            return None

        return features[0].get("geometry")

    except Exception:
        logger.exception("TIGER fetch failed for GEOID %s", geoid)
        return None
