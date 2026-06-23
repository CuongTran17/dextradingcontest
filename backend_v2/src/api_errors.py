from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.observability import get_request_id

logger = logging.getLogger(__name__)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or get_request_id()


def _payload(*, detail: Any, code: str, request: Request) -> dict[str, Any]:
    return {
        "detail": detail,
        "error": {
            "code": code,
            "request_id": _request_id(request),
        },
    }


def _response(
    status_code: int,
    payload: dict[str, Any],
    request: Request,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    response = JSONResponse(status_code=status_code, content=jsonable_encoder(payload), headers=headers)
    request_id = _request_id(request)
    if request_id:
        response.headers["X-Request-ID"] = request_id
    return response


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _response(
            exc.status_code,
            _payload(detail=exc.detail, code="http_error", request=request),
            request,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return _response(
            422,
            _payload(detail=exc.errors(), code="validation_error", request=request),
            request,
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        logger.exception("Database error request_id=%s", _request_id(request), exc_info=exc)
        return _response(
            500,
            _payload(detail="Database error", code="database_error", request=request),
            request,
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error request_id=%s", _request_id(request), exc_info=exc)
        return _response(
            500,
            _payload(detail="Internal server error", code="internal_error", request=request),
            request,
        )
