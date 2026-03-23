"""Structured request/response logging middleware."""

from __future__ import annotations

import json
import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.middleware.sanitizer import sanitize_for_logging

logger = logging.getLogger("reitool.access")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.monotonic()

        # Log request (sanitized)
        body = b""
        if request.method in ("POST", "PUT", "PATCH"):
            body = await request.body()
        sanitized_body = sanitize_for_logging(body.decode("utf-8", errors="replace"))

        logger.info(
            json.dumps({
                "event": "request",
                "request_id": request_id,
                "method": request.method,
                "path": str(request.url.path),
                "body_preview": sanitized_body[:500],
            })
        )

        response = await call_next(request)
        elapsed_ms = round((time.monotonic() - start) * 1000, 1)

        logger.info(
            json.dumps({
                "event": "response",
                "request_id": request_id,
                "status": response.status_code,
                "latency_ms": elapsed_ms,
            })
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Latency-MS"] = str(elapsed_ms)
        return response
