# REITool — Product Requirements Document

## 1. Problem Statement

Commercial real estate brokers in New York State need fast, credible property overviews before client meetings. Today they cobble this together manually from multiple sources (public records, market reports, risk databases), which takes 30–60 minutes per property and introduces inconsistency.

**REITool reduces this to a single address input with a structured briefing returned in under 15 seconds.**

---

## 2. Target User

**Primary:** Commercial real estate broker operating in New York State  
**Secondary:** Buyer/seller agents preparing for listing or offer discussions

**User context:** The broker has an address. They are preparing talking points and want to understand value, risk, and neighborhood quality before walking into a meeting. They are not data scientists — they need interpretation, not raw numbers.

---

## 3. MVP Scope

### In Scope
- Single property lookup by address string
- Statewide New York coverage (with enhanced detail for NYC)
- Structured output: Risk, Price, Location Quality, Market Context sections
- Narrative description and specific talking points
- Property parcel visualization on map (NYC) or centroid + approximate footprint (rest of state)
- Census block group boundary overlay with demographic context
- Real-time response (target: < 15s p90)

### Explicitly Out of Scope (v1)
- Portfolio / batch queries
- Caching layer / database persistence
- User authentication
- Comparable property search
- Historical trend analysis
- Non-New York geographies
- Front-end UI (API-only for MVP; Streamlit demo layer acceptable for presentation)

---

## 4. Data Sources

| Source | What It Provides | Access Method | Notes |
|---|---|---|---|
| Census Geocoder | Coords, county FIPS, block group GEOID | REST — no key required | Entry point for all downstream fetches |
| NY ORPTS (data.ny.gov) | Assessed value, market value, property class, sq ft, year built, SBL | Socrata API — no key required | Fuzzy address match via `$where`; may return multiple candidates; use top result |
| Census ACS 5-Year | Median HH income, vacancy rate, renter/owner split, population | Census API — free key required | Query at block group level using GEOID from geocoder |
| FEMA NFHL | Flood zone designation | ArcGIS REST point-in-polygon | No key; can spike to 2-3s |
| BLS QCEW | County-level employment by industry, trend | BLS public API — free key required | Use to characterize local demand drivers |
| Census TIGER/Line | Block group polygon geometry (GeoJSON) | tigerweb.geo.census.gov REST | Use GEOID from geocoder; negligible latency |
| NYC MapPLUTO | Parcel polygon geometry for NYC only | Socrata GeoJSON (NYC Open Data) | Only called when county FIPS ∈ {36005, 36047, 36061, 36081, 36085} |

**NYC County FIPS Reference:**
- 36005 = Bronx
- 36047 = Kings (Brooklyn)
- 36061 = New York (Manhattan)
- 36081 = Queens
- 36085 = Richmond (Staten Island)

---

## 5. System Architecture

```
POST /analyze
  └── AddressInput (Pydantic)
        │
        ▼
  [1] Census Geocoder  ──────────────────────────── sequential (required first)
        │  returns: lat, lon, county_fips, block_group_geoid
        │
        ▼
  [2] Parallel async fetches (httpx.AsyncClient gather)
        ├── ORPTS Socrata
        ├── Census ACS (block group)
        ├── FEMA NFHL
        ├── BLS QCEW
        ├── Census TIGER block group geometry
        └── MapPLUTO geometry  ← only if NYC county FIPS
        │
        ▼
  [3] Assemble PropertyContext (Pydantic)
        │
        ▼
  [4] Claude synthesis call (Anthropic SDK)
        │  input: structured context JSON
        │  output: structured JSON matching BriefingOutput schema
        │
        ▼
  [5] Return BriefingOutput (FastAPI JSON response)
```

**Key architectural decisions:**
- Steps 1 and 2 are deterministic Python — no LLM involvement until Step 4
- All parallel fetches are fire-and-forget with individual try/except; a failed fetch returns `None` for that field (synthesis prompt handles missing data gracefully)
- Claude is given a strict output schema via the system prompt; response is parsed as JSON
- No database in v1; stateless per-request

---

## 6. API Contract

### Request

```
POST /analyze
Content-Type: application/json

{
  "address": "350 Fifth Avenue, New York, NY 10118"
}
```

### Response Schema

```json
{
  "input_address": "string",
  "resolved_address": "string",
  "coordinates": { "lat": 0.0, "lon": 0.0 },
  "sections": {
    "risk": {
      "flood_zone": "string",
      "flood_zone_description": "string",
      "risk_score": 1,
      "risk_flags": ["string"]
    },
    "price": {
      "assessed_value": 0,
      "full_market_value": 0,
      "price_per_sqft": 0.0,
      "equalization_note": "string"
    },
    "location_quality": {
      "median_household_income": 0,
      "vacancy_rate": 0.0,
      "renter_pct": 0.0,
      "population_trend": "string",
      "block_group_geometry": {}
    },
    "market_context": {
      "county": "string",
      "total_employment": 0,
      "employment_trend": "string",
      "dominant_industries": ["string"]
    }
  },
  "property_facts": {
    "property_class": "string",
    "year_built": 0,
    "lot_size_sqft": 0.0,
    "building_sqft": 0.0,
    "parcel_geometry": {}
  },
  "narrative": "string",
  "talking_points": ["string", "string", "string"]
}
```

### Error Responses
- `422` — Invalid or unresolvable address
- `503` — One or more required upstream sources failed (ORPTS or Geocoder)
- `200` with partial nulls — Non-critical source failed; narrative acknowledges missing data

---

## 7. Claude Synthesis Prompt Design

The synthesis call receives the full `PropertyContext` as JSON and must return a `BriefingOutput` JSON object. Key prompt requirements:

- **System prompt** instructs Claude to act as a commercial real estate analyst writing for a broker audience
- **Output must be strict JSON** — no markdown, no preamble
- **Narrative** target: 3-4 sentences, broker-readable, specific to the data (no generic filler)
- **Talking points** target: exactly 3-5 bullet strings, actionable and specific
- **Risk score** (1-5): Claude derives this from flood zone + any environmental flags in the data
- Prompt must explicitly handle null fields: "If a data field is null, omit it from analysis rather than fabricating"

---

## 8. Non-Functional Requirements

| Requirement | Target |
|---|---|
| p90 end-to-end latency | < 15 seconds |
| p50 end-to-end latency | < 10 seconds |
| ORPTS match rate | > 85% on valid NY commercial addresses |
| Geocoder failure handling | Return 422 with descriptive message |
| Upstream timeout | 8s per fetcher; continue with null on timeout |
| Test coverage | All fetcher functions testable in isolation with mocked HTTP |

---

## 9. Project Structure

```
reitool/
├── CLAUDE.md               ← AI assistant context file
├── PRD.md                  ← this document
├── README.md
├── requirements.txt
├── .env.example
├── main.py                 ← uvicorn entry point
├── app/
│   ├── api/
│   │   └── routes.py       ← POST /analyze endpoint
│   ├── core/
│   │   └── config.py       ← settings via pydantic-settings
│   ├── fetchers/
│   │   ├── geocoder.py     ← Census Geocoder
│   │   ├── orpts.py        ← data.ny.gov Socrata
│   │   ├── census_acs.py   ← Census ACS 5-year
│   │   ├── fema.py         ← FEMA NFHL
│   │   ├── bls.py          ← BLS QCEW
│   │   ├── tiger.py        ← Census TIGER block group geometry
│   │   └── pluto.py        ← NYC MapPLUTO (conditional)
│   ├── schemas/
│   │   ├── input.py        ← AddressInput
│   │   ├── context.py      ← PropertyContext (internal)
│   │   └── output.py       ← BriefingOutput (API response)
│   └── synthesis/
│       └── claude.py       ← Anthropic SDK call + prompt
└── tests/
    ├── conftest.py
    └── test_fetchers.py
```

---

## 10. Future Iterations (v2+)

- PostgreSQL caching layer (ORPTS + FEMA responses; TTL = 30 days)
- Portfolio / batch endpoint (`POST /analyze/batch`)
- Comparable property endpoint (`GET /comparables`)
- Streamlit or React front-end with embedded map
- HUD Fair Market Rent enrichment for rental properties
- EPA FRS brownfield proximity flag
