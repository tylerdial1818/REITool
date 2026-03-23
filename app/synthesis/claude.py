"""OpenAI-powered synthesis module for generating structured property briefings."""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

logger = logging.getLogger("reitool.synthesis")

from app.core.config import get_settings

SYSTEM_PROMPT = """\
You are a commercial real estate analyst writing structured property briefings \
for brokers.

Return ONLY valid JSON matching the schema below. No markdown, no preamble.

{
  "risk": {
    "flood_zone": "<string|null>",
    "flood_zone_description": "<string|null>",
    "risk_score": "<int 1-5>",
    "risk_flags": ["<string>"]
  },
  "price": {
    "assessed_value": "<int|null>",
    "full_market_value": "<int|null>",
    "price_per_sqft": "<float|null>",
    "equalization_note": "<string|null>"
  },
  "location_quality": {
    "median_household_income": "<int|null>",
    "vacancy_rate": "<float|null>",
    "renter_pct": "<float|null>",
    "population_trend": "<string|null>",
    "block_group_geometry": "<GeoJSON dict|null>"
  },
  "market_context": {
    "county": "<string|null>",
    "total_employment": "<int|null>",
    "employment_trend": "<string|null>",
    "dominant_industries": ["<string>"]
  },
  "property_facts": {
    "property_class": "<string|null>",
    "year_built": "<int|null>",
    "lot_size_sqft": "<float|null>",
    "building_sqft": "<float|null>",
    "parcel_geometry": "<GeoJSON dict|null>"
  },
  "narrative": "<string>",
  "talking_points": ["<string>"]
}

Rules:
- If any input field is null, omit it from your analysis. Do not fabricate data.
- narrative: 3-4 sentences, specific to the data, broker-readable.
- talking_points: Exactly 3-5 actionable bullet strings specific to this property.
- risk_score: 1-5 scale. Derive from flood zone + data completeness. \
If flood data is missing, default to 3.\
"""


async def synthesize_briefing(context_data: dict) -> dict:
    """Call OpenAI to produce a structured property briefing.

    Parameters
    ----------
    context_data:
        A serialised ``PropertyContext`` dict containing all fetched data for
        a single property.

    Returns
    -------
    dict
        Parsed JSON matching the ``BriefingOutput`` sections schema.

    Raises
    ------
    ValueError
        If the model response cannot be parsed as valid JSON.
    """
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    user_msg = json.dumps(context_data, default=str)

    response = await client.chat.completions.create(
        model="gpt-4o",
        max_tokens=2048,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
    )

    # Log token usage and estimated cost (gpt-4o: $5/1M input, $15/1M output)
    usage = response.usage
    if usage:
        est_cost = (usage.prompt_tokens * 5.0 / 1_000_000) + (
            usage.completion_tokens * 15.0 / 1_000_000
        )
        logger.info(
            "OpenAI usage: input=%d output=%d total=%d est_cost=$%.4f",
            usage.prompt_tokens,
            usage.completion_tokens,
            usage.total_tokens,
            est_cost,
        )

    raw_text = response.choices[0].message.content

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"OpenAI returned invalid JSON: {raw_text}"
        ) from exc
