"""
Internal / debug routes – /api/dnse/* and /api/debug/*

Provides quote ingestion from DNSE and manual intraday refresh for debugging.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from src.api.auth import require_role
from src.database.models import User
from src.market_data_status import reject_refresh_in_snapshot_mode
from src.services.vnstock_fetcher import fetcher_service

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Internal"])


# ── Pydantic models ───────────────────────────────────────────────────


class SaveQuotePayload(BaseModel):
    symbol: str = Field(min_length=1, max_length=10)
    price: float
    change: float = 0.0
    changePercent: float = 0.0
    volume: int = 0
    high: float = 0.0
    low: float = 0.0
    open: float = 0.0
    time: str


# ── Routes ────────────────────────────────────────────────────────────


@router.post("/api/dnse/save-quotes")
async def save_quotes(
    quotes: list[SaveQuotePayload],
    _: User = Depends(require_role("admin")),
) -> dict[str, int]:
    # Explicit admin/manual ingestion remains allowed; read APIs must not call this path.
    if not quotes:
        return {"saved": 0}

    payloads = [item.model_dump() for item in quotes]
    saved = await fetcher_service.ingest_realtime_quotes(payloads)
    return {"saved": saved}


@router.post("/api/debug/intraday/refresh")
async def debug_refresh_intraday(
    symbols: Optional[str] = Query(default=None, description="Comma-separated VN30 symbols"),
    force: bool = Query(default=True, description="Allow refresh outside trading session windows"),
    cache_limit: int = Query(default=240, ge=1, le=2000),
    _: User = Depends(require_role("admin")),
) -> dict[str, Any]:
    del symbols, force, cache_limit, _
    reject_refresh_in_snapshot_mode(True)
    return {}
