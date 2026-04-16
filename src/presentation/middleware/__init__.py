"""Middleware — request ID injection, secure headers, Prometheus HTTP metrics."""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from src.infrastructure.observability import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID into every request and bind to structlog context."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Add request_id to context and response headers."""
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        request.state.request_id = request_id

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = (time.perf_counter() - start) * 1000

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed:.1f}"
        return response


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Attach security headers."""
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Record HTTP request counts and latencies in Prometheus metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Measure request duration and increment counters."""
        method = request.method
        path = request.url.path

        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start

        status_code = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(method=method, path=path, status_code=status_code).inc()
        HTTP_REQUEST_DURATION.labels(method=method, path=path).observe(elapsed)

        return response
