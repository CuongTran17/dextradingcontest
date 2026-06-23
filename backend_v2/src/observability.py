from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_ctx.get()


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        token = _request_id_ctx.set(request_id)
        started_at = time.perf_counter()
        response = None

        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.info(
                "request completed method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
                request.method,
                request.url.path,
                getattr(response, "status_code", "error"),
                elapsed_ms,
                request_id,
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id
            _request_id_ctx.reset(token)
