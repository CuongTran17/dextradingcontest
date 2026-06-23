"""
Cache helpers.

Provides MySQL-backed helpers for symbol payload caches and financial-report
caches, plus DuckDB-backed helpers for technical-indicator cache.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from src.database.db import AsyncSessionLocal
from src.database.market_duckdb import TechnicalCacheRow, market_repo
from src.database.models import FinancialReportCache
from src.settings import get_settings
from src.utils import _json_dumps, _json_loads, _row_is_fresh, _row_iso_timestamp

logger = logging.getLogger(__name__)


# ── Symbol payload cache (news, events, company overview) ─────────────


async def _load_symbol_payload_cache(
    model_cls: Any,
    symbol: str,
    max_age_seconds: Optional[int],
) -> tuple[Optional[Any], Optional[str]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(model_cls).where(model_cls.symbol == symbol))
        row = result.scalars().first()
        if not row:
            return None, None

        if max_age_seconds is not None and not _row_is_fresh(row.updated_at, max_age_seconds):
            return None, _row_iso_timestamp(row.updated_at)

        payload = _json_loads(row.payload_json, fallback=[])
        return payload, _row_iso_timestamp(row.updated_at)


async def _save_symbol_payload_cache(
    model_cls: Any,
    symbol: str,
    payload: Any,
    source: str,
) -> Optional[str]:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(select(model_cls).where(model_cls.symbol == symbol))
            row = result.scalars().first()
            if row is None:
                row = model_cls(symbol=symbol)

            row.payload_json = _json_dumps(payload)
            if hasattr(row, "item_count"):
                row.item_count = len(payload) if isinstance(payload, list) else 0
            if hasattr(row, "source"):
                row.source = source
            row.updated_at = datetime.now(timezone.utc)

            db.add(row)
            await db.commit()
            return _row_iso_timestamp(row.updated_at)
        except Exception as exc:
            await db.rollback()
            logger.warning("Failed to save %s cache for %s: %s", model_cls.__name__, symbol, exc)
            return None


# ── Financial-report cache ────────────────────────────────────────────


async def _load_financial_report_cache(
    symbol: str,
    report_type: str,
    max_age_seconds: Optional[int],
) -> tuple[Optional[list[dict[str, Any]]], Optional[str]]:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(FinancialReportCache).where(
                FinancialReportCache.symbol == symbol,
                FinancialReportCache.report_type == report_type,
            )
        )
        row = result.scalars().first()
        if not row:
            return None, None

        if max_age_seconds is not None and not _row_is_fresh(row.updated_at, max_age_seconds):
            return None, _row_iso_timestamp(row.updated_at)

        payload = _json_loads(row.payload_json, fallback=[])
        if not isinstance(payload, list):
            payload = []
        return payload, _row_iso_timestamp(row.updated_at)


async def _save_financial_report_cache(
    symbol: str,
    report_type: str,
    records: list[dict[str, Any]],
    source: str,
) -> Optional[str]:
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(FinancialReportCache).where(
                    FinancialReportCache.symbol == symbol,
                    FinancialReportCache.report_type == report_type,
                )
            )
            row = result.scalars().first()
            if row is None:
                row = FinancialReportCache(symbol=symbol, report_type=report_type)

            row.row_count = len(records)
            row.payload_json = _json_dumps(records)
            row.source = source
            row.updated_at = datetime.now(timezone.utc)

            db.add(row)
            await db.commit()
            return _row_iso_timestamp(row.updated_at)
        except Exception as exc:
            await db.rollback()
            logger.warning("Failed to save financial cache for %s (%s): %s", symbol, report_type, exc)
            return None


# ── Technical-indicator cache ─────────────────────────────────────────


async def _load_technical_cache(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> tuple[Optional[TechnicalCacheRow], Optional[dict[str, Any]]]:
    if not get_settings().duckdb_request_reads_enabled:
        return None, None

    try:
        return await asyncio.to_thread(
            market_repo.load_technical_cache,
            symbol,
            start_date,
            end_date,
            limit,
        )
    except Exception as exc:
        logger.warning("Failed to load DuckDB technical cache for %s: %s", symbol, exc)
        return None, None


async def _save_technical_cache(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
    history_count: int,
    history_last_time: Optional[str],
    payload: dict[str, Any],
) -> Optional[str]:
    if not get_settings().duckdb_request_writes_enabled:
        return None

    try:
        return await asyncio.to_thread(
            market_repo.upsert_technical_cache,
            symbol,
            start_date,
            end_date,
            limit,
            history_count,
            history_last_time,
            payload,
            "duckdb",
        )
    except Exception as exc:
        logger.warning("Failed to save DuckDB technical cache for %s: %s", symbol, exc)
        return None
