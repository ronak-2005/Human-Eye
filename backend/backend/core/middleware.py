"""
Security-owned middleware. Register in main.py in this exact order (FastAPI reverses).
Tag security engineer on any PR touching this file.
"""
import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from core.config import settings

logger = logging.getLogger(__name__)


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    """Runs FIRST — rejects oversized payloads before any processing."""
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > settings.MAX_PAYLOAD_BYTES:
            return Response(
                content='{"error":"payload_too_large","message":"Request body exceeds 10MB limit","code":"PAYLOAD_TOO_LARGE"}',
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attaches X-Request-ID to every request and response."""
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security response headers."""
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


class TimingMiddleware(BaseHTTPMiddleware):
    """Runs LAST — measures total request time, logs it."""
    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        response.headers["X-Process-Time-Ms"] = str(duration_ms)
        logger.info(
            "request_complete",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration_ms,
                "request_id": getattr(request.state, "request_id", ""),
            },
        )
        return response
