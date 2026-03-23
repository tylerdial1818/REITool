"""Fetch property-tax data from the NY ORPTS open-data API."""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

_FIELDS = (
    "full_market_val",
    "assessed_val",
    "property_class_code",
    "year_built",
    "sq_footage",
    "front_feet",
    "depth_feet",
)


def _parse_address(resolved_address: str) -> tuple[str, str, str]:
    """Split a Census-resolved address into (house_number, street_name, muni_name).

    Expected format: ``"123 MAIN ST, ALBANY, NY, 12345"``
    """
    parts = [p.strip() for p in resolved_address.split(",")]
    street_part = parts[0] if parts else ""
    muni_name = parts[1] if len(parts) > 1 else ""

    # First token is the house number; remainder is the street name
    tokens = street_part.split(None, 1)
    house_number = tokens[0] if tokens else ""
    street_name = tokens[1] if len(tokens) > 1 else ""

    # Strip any trailing directional suffix that ORPTS might not have
    street_name = re.sub(r"\s+(N|S|E|W|NE|NW|SE|SW)$", "", street_name)

    return house_number, street_name.upper(), muni_name.upper()


async def fetch_orpts(
    client: httpx.AsyncClient,
    resolved_address: str,
) -> dict[str, Any] | None:
    """Query the ORPTS dataset for a single property; return key fields or *None*."""
    url = "https://data.ny.gov/resource/8h5j-fqxa.json"

    house_number, street_name, muni_name = _parse_address(resolved_address)
    if not street_name:
        logger.warning("Could not parse street name from %r", resolved_address)
        return None

    where_clause = (
        f"upper(street_name) = '{street_name}' "
        f"AND house_number = '{house_number}'"
    )
    if muni_name:
        where_clause += f" AND upper(muni_name) = '{muni_name}'"

    params = {
        "$where": where_clause,
        "$limit": "1",
    }

    try:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        rows = resp.json()

        if not rows:
            logger.info("No ORPTS results for %r", resolved_address)
            return None

        row = rows[0]
        return {field: row.get(field) for field in _FIELDS}

    except Exception:
        logger.exception("ORPTS fetch failed for %r", resolved_address)
        return None
