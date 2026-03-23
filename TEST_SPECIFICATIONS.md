# REITool — Engineering Test Specifications

This document defines every test that must pass before the MVP is considered complete. Tests use **pytest**, **pytest-asyncio**, and **respx** (httpx mock library). No real API calls are made in tests.

---

## 1. Schema Validation Tests (`tests/test_schemas.py`)

### 1.1 AddressInput

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| S-001 | `test_valid_address_input` | Construct `AddressInput` with a valid NY address string | Model validates successfully |
| S-002 | `test_empty_address_rejected` | Pass empty string as address | `ValidationError` raised |
| S-003 | `test_whitespace_only_rejected` | Pass whitespace-only string | `ValidationError` raised |

### 1.2 PropertyContext

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| S-010 | `test_property_context_full_data` | Construct `PropertyContext` with all fields populated | Model validates successfully |
| S-011 | `test_property_context_nullable_fields` | Construct `PropertyContext` with optional fetcher fields as `None` | Model validates; nullable fields accepted |
| S-012 | `test_property_context_requires_geocoder_fields` | Omit required geocoder fields (lat, lon, county_fips) | `ValidationError` raised |

### 1.3 BriefingOutput

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| S-020 | `test_briefing_output_full` | Construct `BriefingOutput` with all sections populated | Model validates successfully |
| S-021 | `test_briefing_output_nullable_sections` | Sections with `None` sub-fields validate correctly | Model validates; partial data accepted |
| S-022 | `test_briefing_output_risk_score_range` | Risk score outside 1-5 range | `ValidationError` raised |
| S-023 | `test_briefing_output_talking_points_count` | Talking points list with 0 items | `ValidationError` raised (minimum 3) |
| S-024 | `test_briefing_output_serialization` | Serialize `BriefingOutput` to JSON and back | Round-trip produces identical object |

---

## 2. Configuration Tests (`tests/test_config.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| C-001 | `test_settings_loads_from_env` | Set env vars and verify `Settings` reads them | All API keys populated correctly |
| C-002 | `test_settings_missing_required_key` | Omit `ANTHROPIC_API_KEY` from env | `ValidationError` raised on construction |
| C-003 | `test_default_timeout` | Construct `Settings` without explicit timeout | `fetcher_timeout_seconds` defaults to 8 |

---

## 3. Fetcher Tests (`tests/test_fetchers.py`)

All fetcher tests use `respx` to mock HTTP responses. Each fetcher receives an `httpx.AsyncClient` instance.

### 3.1 Census Geocoder (`fetchers/geocoder.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-001 | `test_geocoder_success` | Mock valid Census Geocoder JSON response | Returns `lat`, `lon`, `county_fips`, `block_group_geoid`, `resolved_address` |
| F-002 | `test_geocoder_no_match` | Mock response with empty `addressMatches` array | Returns `None` or raises appropriate error for 422 |
| F-003 | `test_geocoder_timeout` | Mock `httpx.TimeoutException` | Returns `None` / raises for 422 handling |
| F-004 | `test_geocoder_malformed_response` | Mock response with missing `result` key | Returns `None` with graceful error handling |
| F-005 | `test_geocoder_extracts_geoid` | Mock response with full geography block | Correctly parses `GEOID` from nested Census response |

### 3.2 ORPTS Socrata (`fetchers/orpts.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-010 | `test_orpts_success` | Mock Socrata JSON array with one property record | Returns `full_market_val`, `assessed_val`, `property_class_code`, `year_built`, `sq_footage` |
| F-011 | `test_orpts_multiple_results` | Mock response with 3 candidate rows | Uses first result only |
| F-012 | `test_orpts_no_match` | Mock empty array response | Returns `None` |
| F-013 | `test_orpts_timeout` | Mock timeout | Returns `None`, does not raise |
| F-014 | `test_orpts_address_parsing` | Verify address is parsed into `street_name`, `house_number`, `muni_name` components | Query params correctly constructed |

### 3.3 Census ACS (`fetchers/census_acs.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-020 | `test_census_acs_success` | Mock ACS response with header row + data row | Returns `median_hh_income`, computed `vacancy_rate`, computed `renter_pct` |
| F-021 | `test_census_acs_division_by_zero` | Mock data where `B25002_001E` (total units) = 0 | `vacancy_rate` returns `None` or 0.0, no crash |
| F-022 | `test_census_acs_missing_variable` | Mock response missing one variable column | Returns partial data with `None` for missing field |
| F-023 | `test_census_acs_timeout` | Mock timeout | Returns `None` |
| F-024 | `test_census_acs_geoid_decomposition` | Verify GEOID is correctly split into state, county, tract, block group for API params | Correct query parameters sent |

### 3.4 FEMA NFHL (`fetchers/fema.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-030 | `test_fema_flood_zone_ae` | Mock response with `FLD_ZONE = "AE"` | Returns zone `"AE"` with high-risk description |
| F-031 | `test_fema_flood_zone_x` | Mock response with `FLD_ZONE = "X"` | Returns zone `"X"` with minimal-risk description |
| F-032 | `test_fema_flood_zone_ve` | Mock response with `FLD_ZONE = "VE"` | Returns zone `"VE"` with coastal high-hazard description |
| F-033 | `test_fema_no_features` | Mock response with empty `features` array | Returns `None` |
| F-034 | `test_fema_timeout` | Mock timeout (simulates FEMA's slow responses) | Returns `None` |
| F-035 | `test_fema_point_query_params` | Verify lat/lon are passed as correct ArcGIS geometry params | Request URL contains properly formatted `geometry` and `geometryType=esriGeometryPoint` |

### 3.5 BLS QCEW (`fetchers/bls.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-040 | `test_bls_success` | Mock BLS response with 4 quarters of data | Returns `total_employment`, `employment_trend` (YoY %), `dominant_industries` |
| F-041 | `test_bls_series_id_construction` | Pass county FIPS `"061"` and state FIPS `"36"` | Series ID is `"ENU3606110"` |
| F-042 | `test_bls_insufficient_data` | Mock response with only 1 quarter | Returns employment data without trend (trend = `None`) |
| F-043 | `test_bls_timeout` | Mock timeout | Returns `None` |
| F-044 | `test_bls_zero_padded_fips` | County FIPS with various lengths | All produce correctly zero-padded series IDs |

### 3.6 Census TIGER Geometry (`fetchers/tiger.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-050 | `test_tiger_success` | Mock TIGERweb response with GeoJSON polygon | Returns block group polygon geometry dict |
| F-051 | `test_tiger_no_result` | Mock response with empty `features` | Returns `None` |
| F-052 | `test_tiger_timeout` | Mock timeout | Returns `None` |
| F-053 | `test_tiger_geoid_query` | Verify GEOID is passed correctly in query params | Request includes `where=GEOID='360610001001'` or equivalent |

### 3.7 NYC MapPLUTO (`fetchers/pluto.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| F-060 | `test_pluto_success_nyc` | Mock MapPLUTO GeoJSON response for NYC address | Returns parcel polygon geometry |
| F-061 | `test_pluto_no_match` | Mock empty feature collection | Returns `None` |
| F-062 | `test_pluto_timeout` | Mock timeout | Returns `None` |
| F-063 | `test_pluto_nyc_fips_gate` | Verify function is only called for NYC FIPS codes | Function correctly identifies `{36005, 36047, 36061, 36081, 36085}` as NYC |
| F-064 | `test_pluto_non_nyc_skipped` | Pass non-NYC county FIPS | Returns `None` immediately without HTTP call |

---

## 4. Synthesis Tests (`tests/test_synthesis.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| SY-001 | `test_synthesis_valid_response` | Mock Anthropic SDK to return valid JSON matching `BriefingOutput` | Returns parsed `BriefingOutput` object |
| SY-002 | `test_synthesis_handles_null_fields` | Pass `PropertyContext` with multiple `None` fields | Claude prompt includes null-handling instruction; mock returns valid output |
| SY-003 | `test_synthesis_invalid_json_response` | Mock Anthropic SDK to return non-JSON text | Raises appropriate error (500-level) |
| SY-004 | `test_synthesis_schema_mismatch` | Mock return of JSON that doesn't match `BriefingOutput` fields | `ValidationError` raised during parsing |
| SY-005 | `test_synthesis_prompt_contains_schema` | Inspect the system prompt string | Contains `BriefingOutput` JSON schema definition |
| SY-006 | `test_synthesis_prompt_contains_role` | Inspect the system prompt string | Contains commercial real estate analyst role instruction |
| SY-007 | `test_synthesis_prompt_no_fabrication_instruction` | Inspect the system prompt string | Contains "do not fabricate" / null-handling instruction |
| SY-008 | `test_synthesis_risk_score_default_on_missing_fema` | `PropertyContext` with `fema_data = None` | Synthesis prompt instructs default risk score of 3 |
| SY-009 | `test_synthesis_model_selection` | Verify the Anthropic SDK call uses `claude-sonnet-4-5` | Model parameter is correct |

---

## 5. API Route / Integration Tests (`tests/test_api.py`)

These tests use FastAPI's `TestClient` (or `httpx.AsyncClient` with `ASGITransport`). All external calls are mocked.

### 5.1 Happy Path

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| A-001 | `test_analyze_success_full_data` | Mock all fetchers to return valid data; mock synthesis | 200 response with complete `BriefingOutput` JSON |
| A-002 | `test_analyze_success_partial_data` | Mock geocoder + ORPTS success; other fetchers return `None` | 200 response with partial nulls; narrative acknowledges missing data |
| A-003 | `test_analyze_nyc_includes_pluto` | Use NYC county FIPS in geocoder mock | MapPLUTO fetch is triggered; `parcel_geometry` is populated |
| A-004 | `test_analyze_non_nyc_excludes_pluto` | Use non-NYC county FIPS | MapPLUTO fetch is NOT triggered; `parcel_geometry` is `null` |

### 5.2 Error Handling

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| A-010 | `test_analyze_invalid_address_422` | Send empty address string | 422 response with descriptive error message |
| A-011 | `test_analyze_geocoder_failure_422` | Mock geocoder returning no match | 422 response: "Address could not be resolved" |
| A-012 | `test_analyze_geocoder_timeout_422` | Mock geocoder timeout | 422 response |
| A-013 | `test_analyze_orpts_failure_degraded` | Mock ORPTS failure, all others succeed | 200 with ORPTS fields as `null`; narrative notes missing property data |
| A-014 | `test_analyze_synthesis_failure_500` | Mock synthesis returning invalid JSON | 500 response with error detail |
| A-015 | `test_analyze_all_optional_fetchers_fail` | Only geocoder succeeds; all parallel fetchers fail | 200 response; narrative heavily caveated |

### 5.3 Request Validation

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| A-020 | `test_analyze_missing_body` | POST with no JSON body | 422 response |
| A-021 | `test_analyze_wrong_content_type` | POST with `text/plain` body | 422 response |
| A-022 | `test_analyze_extra_fields_ignored` | POST with extra fields beyond `address` | 200 response (extra fields ignored) |

### 5.4 Response Structure Validation

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| A-030 | `test_response_contains_all_sections` | Successful response | JSON contains `risk`, `price`, `location_quality`, `market_context` sections |
| A-031 | `test_response_contains_property_facts` | Successful response | JSON contains `property_facts` with expected fields |
| A-032 | `test_response_contains_narrative` | Successful response | `narrative` is a non-empty string |
| A-033 | `test_response_talking_points_count` | Successful response | `talking_points` has 3-5 items |
| A-034 | `test_response_coordinates_present` | Successful response | `coordinates.lat` and `coordinates.lon` are valid floats |

---

## 6. Performance / Non-Functional Tests (`tests/test_performance.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| P-001 | `test_parallel_fetchers_concurrent` | Time the parallel fetch phase with mocked instant responses | All fetchers execute concurrently (total time ≈ slowest single fetcher, not sum) |
| P-002 | `test_individual_fetcher_timeout_respected` | Mock a fetcher that sleeps > 8s | Fetcher returns `None` after timeout; does not block other fetchers |
| P-003 | `test_end_to_end_latency_under_budget` | Mock all externals with realistic delays (geocoder 1s, FEMA 2s, others 0.5s, synthesis 3s) | Total < 15 seconds |

---

## 7. Edge Case Tests (`tests/test_edge_cases.py`)

| ID | Test Name | Description | Expected Result |
|----|-----------|-------------|-----------------|
| E-001 | `test_address_with_unit_number` | Address like "350 Fifth Ave Unit 5A, New York, NY" | Geocoder and ORPTS handle correctly |
| E-002 | `test_address_with_po_box` | PO Box address (non-physical) | Graceful failure: 422 with descriptive message |
| E-003 | `test_rural_ny_address` | Valid rural NY address far from NYC | Returns data without MapPLUTO; all other sections populated |
| E-004 | `test_orpts_equalization_note_present` | Any successful ORPTS match | `equalization_note` field is populated (not null/empty) |
| E-005 | `test_census_acs_zero_population_block` | Mock ACS data with 0 total units | Division by zero avoided; vacancy/renter rates are `None` or 0 |
| E-006 | `test_bls_county_with_no_data` | Mock BLS returning no series data | Returns `None` gracefully |
| E-007 | `test_concurrent_requests` | Fire 3 simultaneous `/analyze` requests with mocked backends | All return successfully; no shared state corruption |

---

## Test Execution

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_fetchers.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run only fast tests (exclude performance)
pytest tests/ -v -k "not performance"
```

---

## Coverage Targets

| Module | Minimum Coverage |
|--------|-----------------|
| `app/schemas/` | 100% |
| `app/core/config.py` | 100% |
| `app/fetchers/` | 95% |
| `app/synthesis/claude.py` | 90% |
| `app/api/routes.py` | 90% |
| **Overall** | **90%** |

---

## Test Data Fixtures

All mock responses should be defined in `tests/fixtures/` as JSON files:

```
tests/
├── fixtures/
│   ├── geocoder_success.json
│   ├── geocoder_no_match.json
│   ├── orpts_single_result.json
│   ├── orpts_multiple_results.json
│   ├── census_acs_success.json
│   ├── fema_flood_ae.json
│   ├── fema_flood_x.json
│   ├── fema_no_features.json
│   ├── bls_four_quarters.json
│   ├── tiger_polygon.json
│   ├── pluto_parcel.json
│   └── synthesis_valid_output.json
```

Each fixture should contain a realistic API response from the corresponding data source, based on a reference property (e.g., 30 Rockefeller Plaza, New York, NY 10112).
