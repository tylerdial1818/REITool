"""Query FEMA's NFHL service for flood-zone designation."""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_ZONE_DESCRIPTIONS: dict[str, str] = {
    "X": "Minimal risk",
    "A": "100-year floodplain",
    "AE": "100-year floodplain",
    "AH": "100-year floodplain",
    "AO": "100-year floodplain",
    "V": "Coastal high-hazard",
    "VE": "Coastal high-hazard",
}


async def fetch_fema(
    client: httpx.AsyncClient,
    lat: float,
    lon: float,
) -> dict[str, Any] | None:
    """Return the FEMA flood zone and a human-readable description."""
    url = (
        "https://hazards.fema.gov/arcgis/rest/services/"
        "public/NFHL/MapServer/28/query"
    )
    params = {
        "geometry": f"{lon},{lat}",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "outFields": "FLD_ZONE",
        "returnGeometry": "false",
        "f": "json",
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        features = data.get("features", [])
        if not features:
            logger.info("No FEMA features for (%s, %s)", lat, lon)
            return None

        zone = features[0].get("attributes", {}).get("FLD_ZONE", "")
        description = _ZONE_DESCRIPTIONS.get(zone, "Unknown")

        return {
            "flood_zone": zone,
            "flood_zone_description": description,
        }

    except Exception:
        logger.exception("FEMA flood-zone fetch failed for (%s, %s)", lat, lon)
        return None
