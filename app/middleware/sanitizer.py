"""PII and secret redaction for log output."""

from __future__ import annotations

import re

_PATTERNS: list[tuple[re.Pattern, str]] = [
    # API keys in JSON
    (re.compile(r'"(?:api_key|apikey|key|secret|password|token)":\s*"[^"]*"', re.I), '"***": "REDACTED"'),
    # OpenAI / Stripe-style keys
    (re.compile(r'\b(?:sk-|pk_live_|pk_test_)[A-Za-z0-9_\-]{20,}\b'), '[API_KEY_REDACTED]'),
    # Env-var style keys
    (re.compile(r'(CENSUS_API_KEY|BLS_API_KEY|OPENAI_API_KEY)=[^\s&]+', re.I), r'\1=REDACTED'),
    # Email addresses
    (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'), '[EMAIL_REDACTED]'),
    # SSN patterns
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
]


def sanitize_for_logging(text: str) -> str:
    """Redact sensitive patterns from text before logging."""
    for pattern, replacement in _PATTERNS:
        text = pattern.sub(replacement, text)
    return text
