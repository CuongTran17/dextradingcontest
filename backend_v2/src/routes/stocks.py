"""
Stock routes – /api/stocks/*

Covers: list, snapshots, overview, history, intraday, ticks, technical
indicators, and financial reports.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.cache import (
    _load_financial_report_cache,
    _load_symbol_payload_cache,
    _load_technical_cache,
    _save_technical_cache,
)
from src.database.data_lake import read_latest_session_ticks_from_parquet
from src.database.models import CompanyOverviewCache
from src.market_data_status import DATA_AVAILABLE, NO_DATA_IN_SNAPSHOT, reject_refresh_in_snapshot_mode
from src.services.dnse_realtime_provider import dnse_realtime_provider
from src.services.vnstock_fetcher import (
    VN30_SYMBOLS,
    fetcher_service,
    is_vn30_symbol,
    normalize_symbol,
    parse_symbols_query,
)
from src.services.technical_indicators import build_technical_payload
from src.settings import get_settings
from src.utils import (
    _build_intraday_bars_from_ticks,
    _extract_valuation_from_ratios,
    _parse_datetime,
    _row_is_fresh,
    _row_iso_timestamp,
    _to_float,
    _to_int,
    _to_number_or_none,
    _utc_now,
)

logger = logging.getLogger(__name__)
settings = get_settings()
REPO_ROOT = Path(__file__).resolve().parents[3]
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Constants (mirror from main until fully extracted)
INTRADAY_STALE_SECONDS = settings.vnstock_intraday_stale_seconds
TECHNICAL_CACHE_TTL_SECONDS = settings.vnstock_technical_cache_ttl_seconds

router = APIRouter(tags=["Stocks"])


# ── Intraday cache helpers (depend on fetcher_service) ────────────────


def _intraday_cache_age_seconds() -> Optional[float]:
    last_sync = _parse_datetime(fetcher_service.last_intraday_sync_at)
    if last_sync is None:
        return None
    return max((_utc_now() - last_sync).total_seconds(), 0.0)


def _intraday_cache_is_stale(max_age_seconds: int = INTRADAY_STALE_SECONDS) -> bool:
    age_seconds = _intraday_cache_age_seconds()
    if age_seconds is None:
        return True
    return age_seconds > float(max(max_age_seconds, 1))


# ── Private helpers ───────────────────────────────────────────────────


async def _refresh_dnse_realtime(symbols: list[str]) -> dict[str, Any]:
    in_session = fetcher_service.is_intraday_fetch_window()
    return await dnse_realtime_provider.refresh_symbols(symbols, in_session=in_session)


def _dnse_source_label(result: dict[str, Any], fallback: str) -> str:
    return "dnse-realtime-cache" if result.get("status") in {"ok", "cached"} else fallback


def _load_intraday_ticks(symbol: str, limit: int) -> tuple[list[dict[str, Any]], str]:
    cache_payload = fetcher_service.get_intraday_cache_view(symbols=[symbol], limit=limit)
    ticks = cache_payload.get(symbol, [])
    if ticks:
        return ticks, "intraday-cache"
    return read_latest_session_ticks_from_parquet(symbol), "intraday-parquet"


def _validate_vn30_symbol(symbol: str) -> str:
    normalized = normalize_symbol(symbol)
    if not is_vn30_symbol(normalized):
        raise HTTPException(status_code=404, detail=f"Unsupported symbol '{symbol}'. Only VN30 symbols are allowed.")
    return normalized


async def _load_history_data(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> list[dict[str, Any]]:
    records, _source = await _load_history_data_with_source(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    return records


async def _load_history_data_with_source(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> tuple[list[dict[str, Any]], str]:
    lake_records = _load_history_from_gold_lake(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if lake_records:
        return lake_records, "lake-gold-market-features"

    records = await fetcher_service.load_history_from_db_async(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
    if records:
        return records, "duckdb"
    return [], "snapshot-history-missing"


def _load_history_from_gold_lake(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> list[dict[str, Any]]:
    parquet_path = (
        REPO_ROOT
        / "lake"
        / "gold"
        / "market_features"
        / "by_symbol"
        / f"symbol={symbol.upper()}"
        / "latest.parquet"
    )
    if not parquet_path.exists():
        return []

    try:
        frame = pd.read_parquet(parquet_path)
    except Exception:
        logger.warning("Could not read gold lake history for %s.", symbol, exc_info=True)
        return []

    required_columns = ["data_date", "open_price", "high_price", "low_price", "close_price"]
    if any(column not in frame.columns for column in required_columns):
        return []

    rows = frame.copy()
    rows["data_date"] = pd.to_datetime(rows["data_date"], errors="coerce").dt.date
    rows = rows.dropna(subset=["data_date", "close_price"])
    if isinstance(start_date, date):
        rows = rows[rows["data_date"] >= start_date]
    if isinstance(end_date, date):
        rows = rows[rows["data_date"] <= end_date]

    rows = rows.sort_values("data_date").tail(max(limit, 1))
    output: list[dict[str, Any]] = []
    for raw in rows.to_dict("records"):
        close = _to_float(raw.get("close_price"))
        if close <= 0:
            continue
        output.append(
            {
                "time": str(raw.get("data_date")),
                "open": _to_float(raw.get("open_price"), fallback=close),
                "high": _to_float(raw.get("high_price"), fallback=close),
                "low": _to_float(raw.get("low_price"), fallback=close),
                "close": close,
                "volume": _to_int(raw.get("volume")) if "volume" in raw else 0,
            }
        )
    return output


def _calculate_technical_payload(symbol: str, history: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(history)
    return build_technical_payload(
        symbol,
        frame,
        time_col="time",
        open_col="open",
        high_col="high",
        low_col="low",
        close_col="close",
        volume_col="volume",
    )


def _normalize_legacy_manual_tick_time(tick: dict[str, Any]) -> dict[str, Any]:
    if str(tick.get("match_type") or "").lower() != "manual":
        return tick

    parsed = _parse_datetime(tick.get("time"))
    if parsed is None:
        return tick

    local_time = parsed.astimezone(VN_TZ)
    if local_time.hour < 16:
        return tick

    normalized = dict(tick)
    normalized["time"] = (local_time - timedelta(hours=7)).isoformat()
    return normalized


def _normalize_order_tick(tick: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_legacy_manual_tick_time(tick)
    output = dict(normalized)
    output["match_type"] = str(output.get("match_type") or "unknown")
    output["side_source"] = str(output.get("side_source") or "missing")
    output["side_confidence"] = str(output.get("side_confidence") or "unknown")
    if output["match_type"].lower() == "manual":
        output["match_type"] = "unknown"
    return output


def _market_cap_from_overview(snapshot: dict[str, Any], overview: dict[str, Any]) -> Optional[float]:
    price = _to_float(snapshot.get("price"))
    shares = _to_number_or_none(
        overview.get("outstanding_shares")
        or overview.get("issue_share")
        or overview.get("listed_volume")
    )
    if price <= 0 or shares is None or shares <= 0:
        return None
    return price * 1000 * shares


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/api/stocks")
def list_stocks() -> dict[str, list[str]]:
    return {"tickers": VN30_SYMBOLS}


@router.get("/api/stocks/snapshots")
async def get_snapshots(
    symbols: Optional[str] = Query(default=None, description="Comma-separated symbols"),
    refresh: bool = Query(default=False, description="Force refresh from vnstock before returning"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    target_symbols = parse_symbols_query(symbols, fallback=VN30_SYMBOLS)
    dnse_result = await _refresh_dnse_realtime(target_symbols)
    in_session = fetcher_service.is_intraday_fetch_window()
    snapshots = fetcher_service.get_snapshots(target_symbols)
    has_usable_snapshot = any(_to_float(item.get("price")) > 0 for item in snapshots)
    synced_candidates = [
        item.get("syncedAt")
        for item in snapshots
        if isinstance(item.get("syncedAt"), str) and item.get("syncedAt")
    ]
    latest_sync = fetcher_service.last_intraday_sync_at or (max(synced_candidates) if synced_candidates else None)

    return {
        "count": len(snapshots),
        "data": snapshots,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "last_synced_at": latest_sync,
        "source": _dnse_source_label(dnse_result, "snapshot-mysql-cache"),
        "dnse_realtime": dnse_result,
        "refreshed": False,
        "auto_refreshed": False,
        "is_in_session": in_session,
        "cache_age_seconds": _intraday_cache_age_seconds(),
        "data_status": DATA_AVAILABLE if has_usable_snapshot else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/stocks/{symbol}/overview")
async def get_overview(
    symbol: str,
    refresh: bool = Query(default=False, description="Force refresh overview and valuation from vnstock"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    normalized = _validate_vn30_symbol(symbol)
    snapshot = fetcher_service.get_snapshot(normalized)

    overview_payload: dict[str, Any] = {}
    overview_synced_at: Optional[str] = None
    cached_overview, cached_synced_at = await _load_symbol_payload_cache(
        CompanyOverviewCache,
        normalized,
        max_age_seconds=None,
    )
    if isinstance(cached_overview, dict):
        overview_payload = dict(cached_overview)
        overview_synced_at = cached_synced_at

    ratio_records: list[dict[str, Any]] = []
    ratios_synced_at: Optional[str] = None
    cached_ratios, cached_ratio_synced_at = await _load_financial_report_cache(
        normalized,
        "ratios",
        max_age_seconds=None,
    )
    if isinstance(cached_ratios, list):
        ratio_records = list(cached_ratios)
        ratios_synced_at = cached_ratio_synced_at

    valuation = _extract_valuation_from_ratios(ratio_records)
    market_cap = valuation.get("market_cap") or _market_cap_from_overview(snapshot, overview_payload)
    company_name = (
        str(
            overview_payload.get("company_name")
            or overview_payload.get("companyName")
            or overview_payload.get("name")
            or normalized
        )
        .strip()
        or normalized
    )
    industry = (
        str(
            overview_payload.get("industry")
            or overview_payload.get("icb_name2")
            or overview_payload.get("icb_name3")
            or "VN30"
        )
        .strip()
        or "VN30"
    )

    sync_candidates = [snapshot.get("syncedAt"), overview_synced_at, ratios_synced_at]
    last_synced_at = max([item for item in sync_candidates if isinstance(item, str) and item], default=None)

    return {
        "symbol": normalized,
        "company_name": company_name,
        "companyName": company_name,
        "exchange": "HOSE",
        "industry": industry,
        "company_profile": overview_payload.get("company_profile"),
        "charter_capital": _to_number_or_none(overview_payload.get("charter_capital")),
        "issue_share": _to_number_or_none(overview_payload.get("issue_share")),
        "price": _to_float(snapshot.get("price")),
        "change": _to_float(snapshot.get("change")),
        "change_percent": _to_float(snapshot.get("changePercent")),
        "volume": int(_to_float(snapshot.get("volume"))),
        "pe": valuation.get("pe"),
        "pb": valuation.get("pb"),
        "eps": valuation.get("eps"),
        "roe": valuation.get("roe"),
        "roa": valuation.get("roa"),
        "market_cap": market_cap,
        "last_update": snapshot.get("lastUpdate"),
        "source": "mysql-cache",
        "last_synced_at": last_synced_at,
        "data_status": DATA_AVAILABLE if overview_payload or ratio_records else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/stocks/{symbol}/history")
async def get_history(
    symbol: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=365, ge=1, le=5000),
    refresh: bool = Query(default=False, description="Force refresh historical data from vnstock before reading DuckDB"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    normalized = _validate_vn30_symbol(symbol)
    records, source = await _load_history_data_with_source(normalized, start_date=start_date, end_date=end_date, limit=limit)

    return {
        "symbol": normalized,
        "count": len(records),
        "data": records,
        "source": source,
        "last_synced_at": fetcher_service.last_history_sync_at.get(normalized),
        "data_status": DATA_AVAILABLE if records else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/stocks/{symbol}/intraday")
async def get_intraday(
    symbol: str,
    limit: int = Query(default=320, ge=10, le=2000),
    interval_minutes: int = Query(default=1, ge=1, le=240),
    refresh: bool = Query(default=False, description="Force refresh intraday from vnstock before reading cache"),
    force: bool = Query(default=False, description="Allow refresh outside trading session windows (debug)"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    del force
    normalized = _validate_vn30_symbol(symbol)
    dnse_result = await _refresh_dnse_realtime([normalized])

    tick_window = min(max(limit * max(interval_minutes, 1) * 12, 600), 5000)
    ticks, tick_source = _load_intraday_ticks(normalized, tick_window)
    bars = _build_intraday_bars_from_ticks(ticks, interval_minutes=interval_minutes)

    if len(bars) > limit:
        bars = bars[-limit:]

    return {
        "symbol": normalized,
        "count": len(bars),
        "ticks_count": len(ticks),
        "data": bars,
        "interval_minutes": interval_minutes,
        "source": tick_source if tick_source == "intraday-parquet" else _dnse_source_label(dnse_result, "intraday-cache"),
        "dnse_realtime": dnse_result,
        "last_synced_at": fetcher_service.last_intraday_sync_at,
        "is_in_session": fetcher_service.is_intraday_fetch_window(),
        "refreshed": False,
        "forced": False,
        "data_status": DATA_AVAILABLE if bars else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/stocks/{symbol}/ticks")
async def get_ticks(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    refresh: bool = Query(default=False),
    force: bool = Query(default=False),
) -> dict[str, Any]:
    """Return raw intraday trade ticks (sổ lệnh — matched orders) for a symbol."""
    reject_refresh_in_snapshot_mode(refresh)
    del force
    normalized = _validate_vn30_symbol(symbol)
    in_session = fetcher_service.is_intraday_fetch_window()
    dnse_result = await _refresh_dnse_realtime([normalized])

    raw_ticks, tick_source = _load_intraday_ticks(normalized, limit)
    ticks: list[dict] = [
        _normalize_order_tick(tick)
        for tick in raw_ticks
    ]

    # Return most-recent first for order log display.
    ticks_desc = sorted(
        ticks,
        key=lambda item: _parse_datetime(item.get("time")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )

    return {
        "symbol": normalized,
        "count": len(ticks_desc),
        "ticks": ticks_desc,
        "is_in_session": in_session,
        "last_synced_at": fetcher_service.last_intraday_sync_at,
        "source": tick_source if tick_source == "intraday-parquet" else _dnse_source_label(dnse_result, "intraday-cache"),
        "dnse_realtime": dnse_result,
        "refreshed": False,
        "auto_refreshed": False,
        "cache_age_seconds": _intraday_cache_age_seconds(),
        "data_status": DATA_AVAILABLE if ticks_desc else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/stocks/{symbol}/technical")
async def get_technical(
    symbol: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=365, ge=30, le=5000),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    normalized = _validate_vn30_symbol(symbol)
    records, history_source = await _load_history_data_with_source(normalized, start_date=start_date, end_date=end_date, limit=limit)

    if not records:
        return {
            "symbol": normalized,
            "count": 0,
            "ohlcv": {"time": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
            "indicators": {},
            "signals": {},
            "source": history_source,
            "last_synced_at": None,
            "data_status": NO_DATA_IN_SNAPSHOT,
        }

    history_count = len(records)
    history_last_time = str(records[-1].get("time")) if records else None

    if not refresh:
        cached_row, cached_payload = await _load_technical_cache(
            normalized,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
        if (
            cached_row
            and cached_payload
            and cached_row.history_count == history_count
            and (cached_row.history_last_time or None) == history_last_time
            and _row_is_fresh(cached_row.updated_at, TECHNICAL_CACHE_TTL_SECONDS)
        ):
            payload = dict(cached_payload)
            payload["source"] = "duckdb-technical-cache"
            payload["last_synced_at"] = fetcher_service.last_history_sync_at.get(normalized) or _row_iso_timestamp(cached_row.updated_at)
            payload["data_status"] = DATA_AVAILABLE
            return payload

    payload = _calculate_technical_payload(normalized, records)
    technical_synced_at = await _save_technical_cache(
        normalized,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        history_count=history_count,
        history_last_time=history_last_time,
        payload=payload,
    )
    payload["source"] = history_source
    payload["last_synced_at"] = fetcher_service.last_history_sync_at.get(normalized) or technical_synced_at
    payload["data_status"] = DATA_AVAILABLE
    return payload


@router.get("/api/stocks/{symbol}/financials")
async def get_financials(
    symbol: str,
    report_type: str = Query(default="income", pattern="^(income|balance|cashflow|ratios)$"),
    refresh: bool = Query(default=False, description="Force refresh financial report from vnstock"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    normalized = _validate_vn30_symbol(symbol)

    cached_rows, cached_synced_at = await _load_financial_report_cache(
        normalized,
        report_type,
        max_age_seconds=None,
    )
    rows = cached_rows or []

    return {
        "symbol": normalized,
        "type": report_type,
        "count": len(rows),
        "data": rows,
        "source": "mysql-financial-cache",
        "last_synced_at": cached_synced_at,
        "data_status": DATA_AVAILABLE if rows else NO_DATA_IN_SNAPSHOT,
    }
