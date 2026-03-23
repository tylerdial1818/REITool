"""POST /analyze endpoint — orchestrates geocoding, parallel data fetches, and synthesis."""

import asyncio
import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.fetchers.bls import fetch_bls
from app.fetchers.census_acs import fetch_census_acs
from app.fetchers.fema import fetch_fema
from app.fetchers.geocoder import fetch_geocode
from app.fetchers.orpts import fetch_orpts
from app.fetchers.pluto import fetch_pluto
from app.fetchers.tiger import fetch_tiger
from app.schemas.input import AddressInput
from app.synthesis.claude import synthesize_briefing

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze")
async def analyze(payload: AddressInput):
    # Step 1: Geocode (sequential, required)
    async with httpx.AsyncClient(timeout=8.0) as client:
        geo = await fetch_geocode(client, payload.address)
        if geo is None:
            raise HTTPException(422, "Address could not be resolved")

        lat, lon = geo["lat"], geo["lon"]
        county_fips = geo["county_fips"]
        state_fips = geo["state_fips"]
        geoid = geo["block_group_geoid"]
        resolved = geo["resolved_address"]
        is_nyc = county_fips in {"36005", "36047", "36061", "36081", "36085"}

        # Step 2: Parallel fetches
        tasks = [
            fetch_orpts(client, resolved),
            fetch_census_acs(client, geoid, state_fips, county_fips),
            fetch_fema(client, lat, lon),
            fetch_bls(client, county_fips, state_fips),
            fetch_tiger(client, geoid),
        ]
        if is_nyc:
            tasks.append(fetch_pluto(client, resolved, county_fips))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Replace exceptions with None
        results = [None if isinstance(r, Exception) else r for r in results]

        orpts, acs, fema, bls, tiger = (
            results[0],
            results[1],
            results[2],
            results[3],
            results[4],
        )
        pluto = results[5] if is_nyc and len(results) > 5 else None

    # Step 3: Assemble PropertyContext dict
    context = {
        "lat": lat,
        "lon": lon,
        "county_fips": county_fips,
        "state_fips": state_fips,
        "block_group_geoid": geoid,
        "resolved_address": resolved,
        # Spread fetcher results
        **(orpts or {}),
        **(acs or {}),
        **(fema or {}),
        **(bls or {}),
        "block_group_geometry": tiger,
        "parcel_geometry": pluto,
    }

    # Step 4: Synthesis
    try:
        briefing = await synthesize_briefing(context)
    except Exception as e:
        logger.error("Synthesis failed: %s", e)
        raise HTTPException(500, detail=f"Synthesis failed: {str(e)}")

    # Step 5: Return — add input_address and coordinates
    briefing["input_address"] = payload.address
    briefing["resolved_address"] = resolved
    briefing["coordinates"] = {"lat": lat, "lon": lon}
    return briefing
