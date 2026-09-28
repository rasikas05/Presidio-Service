"""Request-scoped correlation ID for Presidio logs (contextvars — safe under concurrency)."""
from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

CORRELATION_HEADER = "X-Correlation-Id"

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_correlation_id() -> str:
    return _correlation_id.get()


class CorrelationIdFilter(logging.Filter):
    """Injects request-scoped correlation id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        inbound = (request.headers.get(CORRELATION_HEADER) or "").strip()
        cid = inbound if inbound else str(uuid.uuid4())
        token = _correlation_id.set(cid)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = cid
            return response
        finally:
            _correlation_id.reset(token)
