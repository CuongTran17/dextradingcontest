"""ETL status and trigger endpoints."""
from __future__ import annotations

import asyncio
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src.api.auth import require_role
from src.database.models import User
from src.market_data_status import DATA_AVAILABLE, ETL_FAILED, ETL_RUNNING, SNAPSHOT_NOT_BUILT, STALE_SNAPSHOT
from src.settings import get_settings
from src.services.vnstock_fetcher import VN30_SYMBOLS

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from etl.config import DEFAULT_SYMBOLS, EtlConfig
from etl.health import check_etl_health, get_recent_runs
from etl.execution import run_etl_in_process

router = APIRouter(prefix="/api/etl", tags=["ETL"])
_require_admin = require_role("admin")
_last_trigger_at: datetime | None = None
_trigger_lock = asyncio.Lock()
settings = get_settings()


class TriggerRequest(BaseModel):
    symbols: Optional[list[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    disable_mysql_load: bool = False
    disable_tick_eod: bool = False


def _default_cfg(symbols: list[str] | None = None) -> EtlConfig:
    today = date.today()
    selected = symbols or settings.etl_symbol_list
    if not selected:
        selected = list(DEFAULT_SYMBOLS or VN30_SYMBOLS)
    return EtlConfig.from_args(
        start_date=today - timedelta(days=settings.etl_lookback_days),
        end_date=today,
        symbols=selected,
        enable_mysql_load=True,
        tick_source=settings.etl_tick_source,
        run_mode=settings.etl_run_mode,
        incremental_overlap_days=settings.etl_incremental_overlap_days,
    )


def _etl_data_status(health: dict) -> str:
    latest_run = health.get("latest_run") or {}
    latest_snapshot = health.get("latest_snapshot")
    if latest_run.get("status") == "running":
        return ETL_RUNNING
    if latest_run.get("status") == "failed":
        return ETL_FAILED
    if not latest_snapshot:
        return SNAPSHOT_NOT_BUILT
    if health.get("status") == "stale":
        return STALE_SNAPSHOT
    return DATA_AVAILABLE


@router.get("/status")
async def get_etl_status() -> dict:
    health = check_etl_health(_default_cfg())
    data_status = _etl_data_status(health)
    latest = health.get("latest_run") or {}
    snapshot = health.get("latest_snapshot") or {}
    return {
        "status": health["status"],
        "data_status": data_status,
        "details": health["details"],
        "last_run_id": latest.get("run_id") or snapshot.get("run_id"),
        "last_run_time": latest.get("completed_at") or snapshot.get("_mtime"),
        "row_count": latest.get("row_count") or snapshot.get("row_count"),
        "symbols": latest.get("symbols") or snapshot.get("symbols") or [],
    }


@router.get("/runs")
async def get_etl_runs(limit: int = Query(default=10, ge=1, le=100)) -> dict:
    runs = get_recent_runs(_default_cfg(), limit=limit)
    return {"count": len(runs), "runs": runs}


@router.get("/health")
async def get_etl_health() -> dict:
    health = check_etl_health(_default_cfg())
    health["data_status"] = _etl_data_status(health)
    return health


@router.post("/trigger")
async def trigger_etl_run(
    body: TriggerRequest | None = None,
    current_user: User = Depends(_require_admin),
) -> dict:
    del current_user
    global _last_trigger_at
    now = datetime.now(timezone.utc)
    async with _trigger_lock:
        if _last_trigger_at and (now - _last_trigger_at).total_seconds() < 1800:
            raise HTTPException(status_code=429, detail="ETL trigger is rate-limited to once every 30 minutes")
        _last_trigger_at = now

    body = body or TriggerRequest()
    symbols = [item.strip().upper() for item in (body.symbols or []) if item.strip()]
    cfg = _default_cfg(symbols or None)
    if body.start_date and body.end_date:
        cfg = EtlConfig.from_args(
            start_date=body.start_date,
            end_date=body.end_date,
            symbols=symbols or cfg.symbols,
            enable_mysql_load=not body.disable_mysql_load,
            enable_tick_eod=not body.disable_tick_eod,
            tick_source=settings.etl_tick_source,
            run_mode="backfill",
        )
    else:
        cfg = EtlConfig.from_args(
            start_date=cfg.user_start,
            end_date=cfg.user_end,
            symbols=symbols or cfg.symbols,
            enable_mysql_load=not body.disable_mysql_load,
            enable_tick_eod=not body.disable_tick_eod,
            tick_source=settings.etl_tick_source,
            run_mode=settings.etl_run_mode,
            incremental_overlap_days=settings.etl_incremental_overlap_days,
        )

    async def _run_background() -> None:
        await run_etl_in_process(cfg)

    asyncio.create_task(_run_background(), name=f"manual-etl-{cfg.run_id}")
    return {"run_id": cfg.run_id, "status": "started", "data_status": ETL_RUNNING, "symbols": cfg.symbols}
