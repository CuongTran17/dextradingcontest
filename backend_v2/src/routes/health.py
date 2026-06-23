from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Response
from sqlalchemy import text

from src.database.db import AsyncSessionLocal
from src.database.redis_db import check_redis_health
from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["Health"])
settings = get_settings()


async def _check_database() -> dict[str, Any]:
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as exc:
        logger.exception("Health database check failed")
        return {"status": "error", "error": exc.__class__.__name__}


async def _check_migrations() -> dict[str, Any]:
    if not settings.db_migrations_enabled:
        return {"status": "skipped", "reason": "DB_MIGRATIONS_ENABLED=false"}

    try:
        async with AsyncSessionLocal() as db:
            table = await db.execute(text("SHOW TABLES LIKE 'alembic_version'"))
            if not table.scalar_one_or_none():
                return {"status": "error", "error": "missing_alembic_version"}

            result = await db.execute(text("SELECT version_num FROM alembic_version LIMIT 1"))
            version = result.scalar_one_or_none()
        if not version:
            return {"status": "error", "error": "missing_alembic_version"}
        return {"status": "ok", "version": version}
    except Exception as exc:
        logger.exception("Health migration check failed")
        return {"status": "error", "error": exc.__class__.__name__}


def _check_redis() -> dict[str, Any]:
    try:
        available = check_redis_health()
    except Exception as exc:
        logger.exception("Health Redis check failed")
        return {"status": "degraded", "error": exc.__class__.__name__}

    return {"status": "ok" if available else "degraded", "optional": True}


def _status_from_checks(checks: dict[str, dict[str, Any]]) -> str:
    required = [checks["database"], checks["migrations"]]
    if any(item["status"] == "error" for item in required):
        return "error"
    if any(item["status"] == "degraded" for item in checks.values()):
        return "degraded"
    return "ok"


@router.get("/live")
async def liveness() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "backend_v2",
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
async def readiness(response: Response) -> dict[str, Any]:
    checks = {
        "database": await _check_database(),
        "migrations": await _check_migrations(),
        "redis": _check_redis(),
    }
    status = _status_from_checks(checks)
    if status == "error":
        response.status_code = 503

    return {
        "status": status,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "checks": checks,
    }


@router.get("")
async def health(response: Response) -> dict[str, Any]:
    return await readiness(response)
