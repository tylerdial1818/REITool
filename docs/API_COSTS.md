# REITool — API Cost Analysis

## Per-Request Cost Breakdown

| # | API | Endpoint | Method | Auth | Cost/Request | Daily Limit |
|---|-----|----------|--------|------|-------------|-------------|
| 1 | Census Geocoder | geocoding.geo.census.gov | GET | None | **$0.00** | Unlimited |
| 2 | ORPTS (Socrata) | data.ny.gov | GET | None | **$0.00** | ~1,000/hr |
| 3 | Census ACS 5-Year | api.census.gov | GET | Free key | **$0.00** | 500/day |
| 4 | FEMA NFHL | hazards.fema.gov | GET | None | **$0.00** | Unlimited |
| 5 | BLS QCEW | api.bls.gov | POST | Free key | **$0.00** | 500/day (v2) |
| 6 | Census TIGER | tigerweb.geo.census.gov | GET | None | **$0.00** | Unlimited |
| 7 | NYC MapPLUTO | data.cityofnewyork.us | GET | None | **$0.00** | Unlimited |
| 8 | **OpenAI gpt-4o** | api.openai.com | POST | Paid key | **~$0.02-0.04** | Pay-per-use |

**Total cost per request: ~$0.02-0.04** (OpenAI is the only paid API)

## OpenAI Token Estimates

Typical request profile for a single property briefing:

| Component | Tokens | Cost |
|-----------|--------|------|
| System prompt | ~500 | $0.0025 |
| PropertyContext (input) | ~1,000 | $0.0050 |
| Briefing output | ~600-800 | $0.009-0.012 |
| **Total** | **~2,100-2,300** | **~$0.017-0.020** |

Pricing: gpt-4o at $5/1M input tokens, $15/1M output tokens.

## Scaling Projections

| Usage Level | Requests/Day | Monthly Cost | Annual Cost |
|-------------|-------------|--------------|-------------|
| Demo / Testing | 10 | ~$6-12 | ~$72-144 |
| Light production | 100 | ~$60-120 | ~$720-1,440 |
| Medium production | 500 | ~$300-600 | ~$3,600-7,200 |
| Heavy production | 1,000 | ~$600-1,200 | ~$7,200-14,400 |

## Cost Optimization Options

| Strategy | Impact | Trade-off |
|----------|--------|-----------|
| Switch to **gpt-4o-mini** | ~10x cheaper (~$0.003/req) | Slightly less nuanced narratives |
| Cache ORPTS + FEMA responses (30-day TTL) | Reduces API load, improves latency | Requires PostgreSQL (v2 feature) |
| Batch BLS/ACS queries | Fewer API calls per day | Adds complexity |

## Rate Limit Bottlenecks

The binding constraints at scale:

- **BLS API v2**: 500 requests/day → max ~500 unique counties/day
- **Census ACS**: 500 requests/day → max ~500 unique block groups/day
- Both can be mitigated with response caching in v2.

## Real-Time Cost Monitoring

The synthesis module logs token usage after every OpenAI call:
```
INFO reitool.synthesis: OpenAI usage: input=1523 output=687 total=2210 est_cost=$0.0179
```

This is visible in the server terminal during the demo.
