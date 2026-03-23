"""Fetch quarterly employment data from the Bureau of Labor Statistics API."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


async def fetch_bls(
    client: httpx.AsyncClient,
    county_fips: str,
    state_fips: str,
) -> dict[str, Any] | None:
    """Return total employment, YoY trend, and dominant industries."""
    url = "https://api.bls.gov/publicAPI/v2/timeseries/data/"

    # QCEW series ID: ENU + state_fips(2) + county_fips(3) + "10" (total covered)
    series_id = f"ENU{state_fips}{county_fips}10"

    settings = get_settings()
    payload = {
        "seriesid": [series_id],
        "registrationkey": settings.bls_api_key,
        "latest": True,
    }

    try:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        body = resp.json()

        series_list = body.get("Results", {}).get("series", [])
        if not series_list:
            logger.info("No BLS series returned for %s", series_id)
            return None

        data_points = series_list[0].get("data", [])
        if not data_points:
            logger.info("No data points in BLS series %s", series_id)
            return None

        # data_points are ordered most-recent first.
        # Most recent value
        latest = data_points[0]
        total_employment = int(latest.get("value", "0").replace(",", ""))

        # Compute YoY trend: compare most recent quarter to the same quarter
        # one year prior (4 quarters back).
        employment_trend: float | None = None
        if len(data_points) >= 5:
            try:
                recent_val = int(data_points[0]["value"].replace(",", ""))
                prior_val = int(data_points[4]["value"].replace(",", ""))
                if prior_val:
                    employment_trend = round(
                        (recent_val - prior_val) / prior_val, 4
                    )
            except (KeyError, ValueError, ZeroDivisionError):
                pass

        return {
            "total_employment": total_employment,
            "employment_trend": employment_trend,
            "dominant_industries": [],  # placeholder for v1
        }

    except Exception:
        logger.exception("BLS fetch failed for series %s", series_id)
        return None
