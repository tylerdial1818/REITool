# CLAUDE.md — REITool

This file gives you the context you need to work on this codebase without re-explaining decisions. Read it before writing or modifying code.

---

## What This Project Does

REITool is a FastAPI service that takes a New York State property address and returns a structured commercial real estate briefing in real time. It is built for real estate brokers who need a fast property overview before a client meeting.

A request follows this exact sequence:
1. Geocode the address (Census Geocoder) to get coordinates, county FIPS, and block group GEOID
2. Fire parallel async fetches across 5-6 data sources
3. Assemble all results into a `PropertyContext` Pydantic object
4. Send `PropertyContext` to Claude for synthesis into a structured `BriefingOutput`
5. Return `BriefingOutput` as JSON

**Steps 1-3 are fully deterministic. No LLM involvement until step 4.**

---

## Tech Stack

- **Python 3.11+**
- **FastAPI** — async API framework
- **httpx** — async HTTP client for all external API calls
- **Pydantic v2** — request/response validation and internal schema
- **pydantic-settings** — environment variable config
- **Anthropic SDK** — Claude synthesis call
- **uvicorn** — ASGI server

No database in v1. No background tasks. No auth. Stateless per request.

---

## Project Layout

```
app/
├── api/routes.py         Single endpoint: POST /analyze
├── core/config.py        Settings class (reads from .env)
├── fetchers/             One file per external data source
│   ├── geocoder.py
│   ├── orpts.py
│   ├── census_acs.py
│   ├── fema.py
│   ├── bls.py
│   ├── tiger.py
│   └── pluto.py          NYC only — see conditional logic below
├── schemas/
│   ├── input.py          AddressInput
│   ├── context.py        PropertyContext (internal, never returned directly)
│   └── output.py         BriefingOutput (the API response)
└── synthesis/
    └── claude.py         Prompt construction + Anthropic SDK call
```

---

## Data Sources and How They Are Called

### 1. Census Geocoder (`fetchers/geocoder.py`)
**URL:** `https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress`  
**No API key required.**  
Returns: `lat`, `lon`, `county_fips`, `block_group_geoid`, `resolved_address`  
This is always called first, sequentially. Every downstream fetcher depends on its output.  
If this fails, raise HTTP 422 immediately — nothing else can proceed.

### 2. ORPTS via data.ny.gov Socrata (`fetchers/orpts.py`)
**Base URL:** `https://data.ny.gov/resource/8h5j-fqxa.json`  
**No API key required (public dataset).**  
Query via `$where` fuzzy address match. The dataset uses `street_name`, `house_number`, and `muni_name` columns — parse the input address to construct the query.  
**Returns multiple candidate rows — use the first result.**  
Key fields: `full_market_val`, `assessed_val`, `property_class_code`, `year_built`, `front_feet`, `depth_feet`, `sq_footage`  
Note: assessed values are NOT comparable across municipalities without equalization. ORPTS publishes equalization rates separately — for v1, include `equalization_note` in output to flag this to the broker.

### 3. Census ACS 5-Year (`fetchers/census_acs.py`)
**URL:** `https://api.census.gov/data/2022/acs/acs5`  
**Requires free Census API key** — store as `CENSUS_API_KEY` in `.env`  
Query at block group level using the GEOID from the geocoder.  
Variables to fetch: `B19013_001E` (median HH income), `B25002_003E` (vacant units), `B25002_001E` (total units), `B25003_003E` (renter-occupied), `B25003_001E` (total occupied)  
Derive: `vacancy_rate = B25002_003E / B25002_001E`, `renter_pct = B25003_003E / B25003_001E`

### 4. FEMA NFHL (`fetchers/fema.py`)
**URL:** `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query`  
**No API key required.**  
Point-in-polygon query using lat/lon from geocoder.  
Key return field: `FLD_ZONE` (e.g., AE, X, VE)  
Zone interpretation for synthesis prompt:
- `X` = Minimal flood risk
- `A`, `AE`, `AH`, `AO` = 100-year floodplain (high risk)
- `V`, `VE` = Coastal high-hazard (highest risk)
- `0.2 PCT ANNUAL CHANCE FLOOD HAZARD` = 500-year floodplain (moderate)

### 5. BLS QCEW (`fetchers/bls.py`)
**URL:** `https://api.bls.gov/publicAPI/v2/timeseries/data/`  
**Requires free BLS API key** — store as `BLS_API_KEY` in `.env`  
Use county FIPS from geocoder to construct the QCEW series ID.  
Series ID format: `ENU{state_fips}{county_fips}10` for total covered employment  
Fetch last 4 quarters to compute trend (YoY % change).

### 6. Census TIGER Block Group Geometry (`fetchers/tiger.py`)
**URL:** `https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/tigerWMS_Census2020/MapServer/10/query`  
**No API key required.**  
Query by `GEOID` (block group) from geocoder. Returns GeoJSON polygon.  
This is added to the `location_quality` section of the output and is used for the map overlay.

### 7. NYC MapPLUTO Geometry (`fetchers/pluto.py`)
**URL:** `https://data.cityofnewyork.us/resource/64uk-42ks.geojson`  
**No API key required.**  
**Only called when `county_fips` is in `{36005, 36047, 36061, 36081, 36085}`.**  
Query by address. Returns parcel polygon geometry.  
If not NYC, `parcel_geometry` in output is `null` — this is acceptable in v1.

---

## Parallel Fetch Pattern

All fetchers after the geocoder are called together using `asyncio.gather` with `return_exceptions=True`. Each fetcher must:
- Accept `httpx.AsyncClient` as a parameter (shared client, do not create per-fetcher)
- Return its Pydantic result model on success
- Return `None` on any exception (log the exception, do not raise)

**This means the synthesis step must handle `None` gracefully for every field.**

```python
# Pattern used in routes.py
results = await asyncio.gather(
    fetch_orpts(client, resolved_address),
    fetch_census_acs(client, block_group_geoid, county_fips, state_fips),
    fetch_fema(client, lat, lon),
    fetch_bls(client, county_fips, state_fips),
    fetch_tiger(client, block_group_geoid),
    fetch_pluto(client, resolved_address) if is_nyc else asyncio.coroutine(lambda: None)(),
    return_exceptions=True,
)
```

Handle `Exception` instances in results (return_exceptions=True returns them rather than raising).

---

## Schemas

### `PropertyContext` (internal, `schemas/context.py`)
This is the assembled object passed to Claude. It should contain all raw data returned from fetchers, structured cleanly. Never return this object directly from the API.

### `BriefingOutput` (API response, `schemas/output.py`)
The final API response. Claude's JSON output is parsed and validated against this schema before returning. If parsing fails, return a 500 with the raw synthesis output in the error detail for debugging.

---

## Claude Synthesis (`synthesis/claude.py`)

### Model
Use `claude-sonnet-4-5` (not Opus — latency matters here, Sonnet is sufficient).

### Prompt Design Rules
1. System prompt establishes role: commercial real estate analyst writing for a broker audience
2. User message contains the full `PropertyContext` serialized as JSON
3. **The system prompt must explicitly instruct Claude to return only valid JSON matching `BriefingOutput` schema — no markdown, no preamble, no explanation**
4. Include the `BriefingOutput` schema directly in the system prompt so Claude knows the expected structure
5. Include explicit instruction: "If any input field is null, omit it from analysis. Do not fabricate data."
6. Narrative target: 3-4 sentences, specific to the data, broker-readable
7. Talking points target: 3-5 strings, actionable and specific (not generic observations)
8. Risk score (1-5): derived from flood zone + any null flags (missing data = uncertainty = higher risk)

### Parsing
Parse Claude's text response as JSON. Validate against `BriefingOutput` using Pydantic. If validation fails, log the raw response and raise a 500.

---

## Configuration (`core/config.py`)

```python
class Settings(BaseSettings):
    census_api_key: str
    bls_api_key: str
    anthropic_api_key: str
    
    fetcher_timeout_seconds: int = 8
    
    model_config = SettingsConfig(env_file=".env")
```

All timeouts are 8 seconds per fetcher. If a fetcher times out, it returns `None` (not a 503).  
503 is only returned if the Census Geocoder or ORPTS fetch fails — these are the two required sources.

---

## Environment Variables (`.env`)

```
CENSUS_API_KEY=your_census_key
BLS_API_KEY=your_bls_key
ANTHROPIC_API_KEY=your_anthropic_key
```

Census key: https://api.census.gov/data/key_signup.html  
BLS key: https://www.bls.gov/developers/home.htm  
Both are free with email signup.

---

## Running Locally

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in API keys
uvicorn main:app --reload --port 8000
```

Test with a real NY address:
```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{"address": "30 Rockefeller Plaza, New York, NY 10112"}'
```

---

## Testing

Each fetcher should be independently testable with mocked HTTP responses using `pytest` + `respx` (httpx mock library). Do not make real API calls in tests.

Test file: `tests/test_fetchers.py`  
The synthesis step can be tested by mocking the Anthropic SDK call and verifying that `BriefingOutput` parses correctly from a sample JSON string.

---

## Key Constraints and Gotchas

**ORPTS address matching is imprecise.** The Socrata dataset does not have a true address index. You are doing string matching on `street_name` and `house_number` columns. Always take the first result. If zero results, return `null` for all ORPTS fields and flag it in the narrative.

**Equalization rates.** ORPTS assessed values are not directly comparable across municipalities. Do not claim price comparisons across different municipalities in the synthesis prompt. The `equalization_note` field in the price section must acknowledge this.

**FEMA can be slow.** The NFHL ArcGIS endpoint is a government REST service and can spike to 3+ seconds. The 8-second timeout handles this. If it times out, the risk section notes missing flood data and the risk score defaults to 3 (uncertain).

**BLS series IDs.** The QCEW series ID format requires zero-padded county FIPS. County FIPS from the Census Geocoder is already 3 digits — confirm this before constructing the series ID.

**NYC detection.** MapPLUTO is only called for the five NYC boroughs. Use `county_fips` to gate this call. The FIPS values are hardcoded constants in `fetchers/pluto.py`.

---

## What Is Not Built Yet (Do Not Implement in v1)

- Caching or database persistence
- Portfolio / batch endpoints
- Authentication
- Front-end (a Streamlit demo layer is acceptable but is not part of the core application)
- Comparable property search
- HUD Fair Market Rent enrichment
- EPA brownfield proximity
