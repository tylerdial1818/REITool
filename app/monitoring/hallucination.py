"""Detect LLM fabrication by comparing synthesis output against source input."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("reitool.hallucination")

# Maps output path → input source field name
_FIELD_PROVENANCE: dict[str, str] = {
    "risk.flood_zone": "flood_zone",
    "risk.flood_zone_description": "flood_zone_description",
    "price.assessed_value": "assessed_val",
    "price.full_market_value": "full_market_val",
    "location_quality.median_household_income": "median_hh_income",
    "location_quality.vacancy_rate": "vacancy_rate",
    "location_quality.renter_pct": "renter_pct",
    "market_context.total_employment": "total_employment",
    "property_facts.year_built": "year_built",
    "property_facts.building_sqft": "sq_footage",
}


def _get_nested(d: dict, path: str) -> Any:
    """Traverse a dotted path like 'risk.flood_zone' in a nested dict."""
    for key in path.split("."):
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return None
    return d


def detect_hallucinations(
    input_context: dict,
    llm_output: dict,
) -> list[str]:
    """Return warning strings for any detected fabrications.

    Two detection modes:
    1. **Fabrication**: input field was null/missing but LLM produced a value.
    2. **Numeric mismatch**: LLM output differs >1% from the input value.
    """
    warnings: list[str] = []

    for output_path, input_key in _FIELD_PROVENANCE.items():
        input_val = input_context.get(input_key)
        out_val = _get_nested(llm_output, output_path)

        # Fabrication: source was null but LLM invented a value
        if input_val is None and out_val is not None:
            warnings.append(
                f"FABRICATION: '{output_path}' = {out_val!r} "
                f"but source '{input_key}' was null"
            )

        # Numeric mismatch: LLM changed a number significantly
        if (
            input_val is not None
            and out_val is not None
            and isinstance(input_val, (int, float))
            and isinstance(out_val, (int, float))
            and input_val != 0
            and abs(out_val - input_val) / abs(input_val) > 0.01
        ):
            warnings.append(
                f"MISMATCH: '{output_path}' = {out_val} "
                f"vs source '{input_key}' = {input_val}"
            )

    return warnings
