"""
Market routes – /api/market-indices/*, /api/news, /api/events

Covers market index history/quotes, news feed and corporate events.
"""
from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, Query

from src.cache import _load_symbol_payload_cache
from src.database.models import EventsCache, NewsCache
from src.market_data_status import DATA_AVAILABLE, NO_DATA_IN_SNAPSHOT, reject_refresh_in_snapshot_mode
from src.services.vnstock_fetcher import VN30_SYMBOLS, parse_symbols_query
from src.settings import get_settings
from src.utils import (
    _parse_datetime,
    _to_float,
    _to_int,
    _utc_now,
)

logger = logging.getLogger(__name__)

_GOOGLE_NEWS_MOJIBAKE_MARKERS = ("├", "┬", "ß", "╗", "║", "─", "Ī", "Ę", "Ł", "ć", "ō", "░", "┐")


def _repair_google_news_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or not any(marker in text for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS):
        return text

    try:
        repaired = text.encode("cp775").decode("utf-8")
    except UnicodeError:
        return text

    original_marker_count = sum(text.count(marker) for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS)
    repaired_marker_count = sum(repaired.count(marker) for marker in _GOOGLE_NEWS_MOJIBAKE_MARKERS)
    return repaired if repaired_marker_count < original_marker_count else text
REPO_ROOT = Path(__file__).resolve().parents[3]
settings = get_settings()

# ── Market index configuration ────────────────────────────────────────

MARKET_INDEX_HISTORY_TTL_SECONDS = settings.vnstock_market_index_cache_ttl_seconds
MARKET_INDEX_LOOKBACK_DAYS = settings.vnstock_market_index_lookback_days

MARKET_INDEX_DEFINITIONS: dict[str, dict[str, str]] = {
    "VNINDEX": {"name": "VN-Index", "vnstock_symbol": "VNINDEX"},
    "VN30": {"name": "VN30", "vnstock_symbol": "VN30"},
    "HNX": {"name": "HNX-Index", "vnstock_symbol": "HNXINDEX"},
    "UPCOM": {"name": "UPCoM", "vnstock_symbol": "UPCOMINDEX"},
}
MARKET_INDEX_ORDER = ["VNINDEX", "VN30", "HNX", "UPCOM"]
MARKET_INDEX_ALIASES: dict[str, str] = {
    "VNINDEX": "VNINDEX",
    "VN-INDEX": "VNINDEX",
    "VN30": "VN30",
    "HNX": "HNX",
    "HNXINDEX": "HNX",
    "HNX-INDEX": "HNX",
    "UPCOM": "UPCOM",
    "UPCOMINDEX": "UPCOM",
    "UPCOM-INDEX": "UPCOM",
}

# ── In-memory caches ──────────────────────────────────────────────────

router = APIRouter(tags=["Market"])


# ── Private helpers ───────────────────────────────────────────────────


def _normalize_market_index_symbol(symbol: str) -> str:
    normalized = (symbol or "").strip().upper().replace(" ", "")
    canonical = MARKET_INDEX_ALIASES.get(normalized)
    if canonical:
        return canonical

    raise HTTPException(
        status_code=404,
        detail=f"Unsupported market index '{symbol}'. Supported values: VNINDEX, VN30, HNX, UPCOM.",
    )


def _normalize_market_index_price(value: Any) -> float:
    price = _to_float(value)
    if 0 < abs(price) < 10:
        return price * 1000.0
    return price


def _load_market_index_history_from_lake(index_symbol: str, limit: int) -> list[dict[str, Any]]:
    latest = REPO_ROOT / "lake" / "gold" / "market_features" / "latest.parquet"
    if not latest.exists():
        return []

    frame = pd.read_parquet(latest)
    vnstock_symbol = MARKET_INDEX_DEFINITIONS[index_symbol]["vnstock_symbol"].lower()
    close_column = f"macro_{vnstock_symbol}_close"
    volume_column = f"macro_{vnstock_symbol}_volume"
    if "data_date" not in frame.columns or close_column not in frame.columns:
        return []

    columns = ["data_date", close_column]
    if volume_column in frame.columns:
        columns.append(volume_column)

    rows = (
        frame[columns]
        .dropna(subset=["data_date", close_column])
        .drop_duplicates(subset=["data_date"], keep="last")
        .sort_values("data_date")
        .tail(max(limit, 1))
    )

    output: list[dict[str, Any]] = []
    for raw in rows.to_dict("records"):
        close = _normalize_market_index_price(raw.get(close_column))
        volume = _to_int(raw.get(volume_column)) if volume_column in raw else 0
        output.append(
            {
                "time": str(raw.get("data_date")),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": volume,
            }
        )
    return output


async def _get_market_index_history_rows(
    index_symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
    refresh: bool,
) -> tuple[list[dict[str, Any]], Optional[str], str]:
    reject_refresh_in_snapshot_mode(refresh)
    safe_limit = max(2, min(limit, 5000))
    del start_date, end_date
    rows = _load_market_index_history_from_lake(index_symbol, safe_limit)
    if rows:
        return rows, _utc_now().isoformat(), "lake-gold-market-features"
    return [], None, "snapshot-market-index-missing"


def _build_market_index_quote(index_symbol: str, history_rows: list[dict[str, Any]]) -> dict[str, Any]:
    definition = MARKET_INDEX_DEFINITIONS[index_symbol]
    if not history_rows:
        return {
            "symbol": index_symbol,
            "name": definition["name"],
            "price": 0.0,
            "change": 0.0,
            "changePercent": 0.0,
            "volume": 0,
            "time": _utc_now().isoformat(),
        }

    latest = history_rows[-1]
    previous = history_rows[-2] if len(history_rows) > 1 else latest

    latest_close = _normalize_market_index_price(latest.get("close"))
    previous_close = _normalize_market_index_price(previous.get("close"))
    if previous_close <= 0:
        previous_close = latest_close
    change = latest_close - previous_close
    change_percent = (change / previous_close * 100.0) if previous_close > 0 else 0.0

    return {
        "symbol": index_symbol,
        "name": definition["name"],
        "price": round(latest_close, 2),
        "change": round(change, 2),
        "changePercent": round(change_percent, 2),
        "volume": _to_int(latest.get("volume")),
        "time": str(latest.get("time") or _utc_now().isoformat()),
    }


# ── Routes ────────────────────────────────────────────────────────────


@router.get("/api/market-indices")
async def get_market_indices(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
    refresh: bool = Query(default=False, description="Force refresh index prices from vnstock"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    safe_limit = int(limit) if isinstance(limit, int) else 10
    target_symbols = MARKET_INDEX_ORDER[: min(safe_limit, len(MARKET_INDEX_ORDER))]

    index_rows: list[dict[str, Any]] = []
    source_parts: set[str] = set()
    synced_at_values: list[str] = []
    has_data = False
    for index_symbol in target_symbols:
        history_rows, synced_at, data_source = await _get_market_index_history_rows(
            index_symbol=index_symbol,
            start_date=start_date,
            end_date=end_date,
            limit=max(3, min(120, safe_limit * 10)),
            refresh=refresh,
        )
        has_data = has_data or bool(history_rows)
        index_rows.append(_build_market_index_quote(index_symbol=index_symbol, history_rows=history_rows))
        source_parts.add(data_source)
        if synced_at:
            synced_at_values.append(synced_at)

    return {
        "count": len(index_rows),
        "data": index_rows,
        "source": "+".join(sorted(source_parts)) if source_parts else "snapshot-market-index-missing",
        "last_synced_at": max(synced_at_values) if synced_at_values else None,
        "data_status": DATA_AVAILABLE if has_data else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/market-indices/{index_symbol}/history")
async def get_market_index_history(
    index_symbol: str,
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    limit: int = Query(default=365, ge=30, le=5000),
    refresh: bool = Query(default=False, description="Force refresh index history from vnstock"),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    safe_limit = int(limit) if isinstance(limit, int) else 365
    normalized = _normalize_market_index_symbol(index_symbol)
    history_rows, synced_at, source = await _get_market_index_history_rows(
        index_symbol=normalized,
        start_date=start_date,
        end_date=end_date,
        limit=safe_limit,
        refresh=refresh,
    )

    definition = MARKET_INDEX_DEFINITIONS[normalized]
    return {
        "symbol": normalized,
        "name": definition["name"],
        "count": len(history_rows),
        "data": history_rows,
        "source": source,
        "last_synced_at": synced_at,
        "data_status": DATA_AVAILABLE if history_rows else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/news")
async def get_news(
    symbols: Optional[str] = Query(default=None),
    limit: int = Query(default=24, ge=1, le=200),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    safe_limit = int(limit) if isinstance(limit, int) else 24
    target = parse_symbols_query(symbols, fallback=VN30_SYMBOLS[:8])
    merged: list[dict[str, Any]] = []
    synced_at_values: list[str] = []

    for symbol in target:
        items, synced_at = await _load_symbol_payload_cache(NewsCache, symbol, max_age_seconds=None)
        items = items if isinstance(items, list) else []
        merged.extend(items)
        if synced_at:
            synced_at_values.append(synced_at)

    merged.sort(key=lambda item: item.get("publish_time") or "", reverse=True)
    clipped = merged[:safe_limit]

    return {
        "count": len(clipped),
        "symbols": target,
        "data": clipped,
        "cached_at": _utc_now().isoformat(),
        "source": "mysql-news-cache",
        "last_synced_at": max(synced_at_values) if synced_at_values else None,
        "limit": safe_limit,
        "data_status": DATA_AVAILABLE if clipped else NO_DATA_IN_SNAPSHOT,
    }


def _load_latest_google_news(symbol: str, limit: int) -> tuple[list[dict[str, Any]], Optional[str]]:
    symbol = symbol.upper()
    symbol_dir = REPO_ROOT / "lake" / "raw" / "google_news" / symbol
    if not symbol_dir.exists():
        return [], None

    files = sorted(symbol_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("Could not read google news cache %s", path)
            continue

        if not isinstance(raw, list):
            continue

        items: list[dict[str, Any]] = []
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            title = _repair_google_news_text(item.get("title"))
            if not title:
                continue
            published = _repair_google_news_text(item.get("datetime") or item.get("date") or "")
            items.append({
                "id": f"{symbol}-google-{path.stem}-{index}",
                "symbol": symbol,
                "symbols": [symbol],
                "source": _repair_google_news_text(item.get("source") or "Google News"),
                "title": title,
                "summary": _repair_google_news_text(item.get("desc")),
                "publish_time": str(published),
                "time": str(published),
                "url": str(item.get("link") or ""),
                "impact": "medium",
            })

        items.sort(key=lambda entry: entry.get("publish_time") or "", reverse=True)
        return items[:limit], datetime.fromtimestamp(path.stat().st_mtime).isoformat()

    return [], None


@router.get("/api/google-news")
async def get_google_news(
    symbols: Optional[str] = Query(default=None),
    limit: int = Query(default=24, ge=1, le=200),
) -> dict[str, Any]:
    safe_limit = int(limit) if isinstance(limit, int) else 24
    target = parse_symbols_query(symbols, fallback=VN30_SYMBOLS[:8])
    merged: list[dict[str, Any]] = []
    synced_at_values: list[str] = []

    per_symbol_limit = max(safe_limit, 1)
    for symbol in target:
        items, synced_at = _load_latest_google_news(symbol, per_symbol_limit)
        merged.extend(items)
        if synced_at:
            synced_at_values.append(synced_at)

    merged.sort(key=lambda item: item.get("publish_time") or "", reverse=True)
    clipped = merged[:safe_limit]

    return {
        "count": len(clipped),
        "symbols": target,
        "data": clipped,
        "cached_at": _utc_now().isoformat(),
        "source": "lake-raw-google-news",
        "last_synced_at": max(synced_at_values) if synced_at_values else None,
        "limit": safe_limit,
        "data_status": DATA_AVAILABLE if clipped else NO_DATA_IN_SNAPSHOT,
    }


@router.get("/api/events")
async def get_events(
    symbols: Optional[str] = Query(default=None),
    limit: int = Query(default=24, ge=1, le=200),
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    reject_refresh_in_snapshot_mode(refresh)
    safe_limit = int(limit) if isinstance(limit, int) else 24
    target = parse_symbols_query(symbols, fallback=VN30_SYMBOLS[:8])
    merged: list[dict[str, Any]] = []
    synced_at_values: list[str] = []

    for symbol in target:
        items, synced_at = await _load_symbol_payload_cache(EventsCache, symbol, max_age_seconds=None)
        items = items if isinstance(items, list) else []
        merged.extend(items)
        if synced_at:
            synced_at_values.append(synced_at)

    today = _utc_now().date()
    future_events = [item for item in merged if (_parse_datetime(item.get("date")) or _utc_now()).date() >= today]
    past_events = [item for item in merged if (_parse_datetime(item.get("date")) or _utc_now()).date() < today]

    future_events.sort(key=lambda item: item.get("date") or "")
    past_events.sort(key=lambda item: item.get("date") or "", reverse=True)
    clipped = (future_events + past_events)[:safe_limit]

    return {
        "count": len(clipped),
        "symbols": target,
        "data": clipped,
        "cached_at": _utc_now().isoformat(),
        "source": "mysql-events-cache",
        "last_synced_at": max(synced_at_values) if synced_at_values else None,
        "limit": safe_limit,
        "data_status": DATA_AVAILABLE if clipped else NO_DATA_IN_SNAPSHOT,
    }
