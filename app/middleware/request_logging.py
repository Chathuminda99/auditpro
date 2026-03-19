"""Request-scoped access and error logging middleware."""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.logging_config import bind_log_context, reset_log_context


ACCESS_LOGGER = logging.getLogger("auditpro.access")
APP_LOGGER = logging.getLogger("auditpro.app")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Attach request context and emit readable request lifecycle logs."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        forwarded_for = request.headers.get("X-Forwarded-For", "")
        client_ip = (
            forwarded_for.split(",")[0].strip()
            if forwarded_for
            else (request.client.host if request.client else "-")
        )

        request.state.request_id = request_id
        bind_log_context(
            request_id=request_id,
            client_ip=client_ip,
            method=request.method,
            path=request.url.path,
        )

        started_at = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - started_at) * 1000
            APP_LOGGER.exception(
                "request_failed duration_ms=%.2f",
                duration_ms,
            )
            reset_log_context()
            raise

        duration_ms = (time.perf_counter() - started_at) * 1000
        response.headers["X-Request-ID"] = request_id

        level = logging.INFO
        if response.status_code >= 500:
            level = logging.ERROR
        elif response.status_code >= 400:
            level = logging.WARNING

        ACCESS_LOGGER.log(
            level,
            "request_completed status=%s duration_ms=%.2f bytes=%s",
            response.status_code,
            duration_ms,
            response.headers.get("content-length", "-"),
        )
        reset_log_context()
        return response
