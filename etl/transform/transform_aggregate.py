"""Aggregate intraday ticks into end-of-day OHLCV rows for ETL."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from etl.config import EtlConfig
from etl.logging_setup import get_logger

log = get_logger(__name__)
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _to_float(value: Any) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(parsed) else float(parsed)


def _to_int(value: Any) -> int:
    parsed = pd.to_numeric(value, errors="coerce")
    return 0 if pd.isna(parsed) else int(parsed)


def _tick_time(value: Any) -> pd.Timestamp | None:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return None
    ts = pd.Timestamp(parsed)
    if ts.tzinfo is None:
        ts = ts.tz_localize(VN_TZ)
    return ts.tz_convert(VN_TZ)


def _is_regular_session(ts: pd.Timestamp) -> bool:
    minutes = ts.hour * 60 + ts.minute
    morning = 9 * 60 <= minutes <= 11 * 60 + 30
    afternoon = 13 * 60 <= minutes <= 15 * 60
    return morning or afternoon


def _candidate_tick_files(cfg: EtlConfig, target_date: date, symbol: str) -> list[Path]:
    date_part = target_date.isoformat()
    return [
        cfg.lake_dir / "data_lake" / "ticks" / date_part / f"{symbol.upper()}.parquet",
        Path("backend_v2") / "data_lake" / "ticks" / date_part / f"{symbol.upper()}.parquet",
    ]


def _load_ticks_from_lake(cfg: EtlConfig, target_date: date, symbol: str) -> list[dict[str, Any]]:
    for path in _candidate_tick_files(cfg, target_date, symbol):
        if path.exists():
            frame = pd.read_parquet(path)
            return frame.to_dict(orient="records")
    return []


def _load_ticks_from_redis(symbol: str) -> list[dict[str, Any]]:
    try:
        from backend_v2.src.redis_db import redis_client
    except Exception:
        try:
            from src.redis_db import redis_client  # type: ignore
        except Exception:
            return []

    if redis_client is None:
        return []
    raw = redis_client.lrange(f"intraday:{symbol.upper()}", 0, -1)
    ticks: list[dict[str, Any]] = []
    for item in raw:
        try:
            if isinstance(item, bytes):
                item = item.decode("utf-8")
            parsed = json.loads(item)
            if isinstance(parsed, dict):
                ticks.append(parsed)
        except (TypeError, json.JSONDecodeError):
            continue
    return ticks


def aggregate_ticks_to_eod(
    symbol: str,
    cfg: EtlConfig,
    target_date: date | None = None,
    source: str = "lake",
) -> dict[str, Any] | None:
    """Aggregate one symbol's intraday ticks into an OHLCV row.

    ``source`` can be ``lake``, ``redis``, or ``auto``. ETL defaults to the data
    lake because Redis is an operational cache, not durable storage.
    """
    target_date = target_date or datetime.now(tz=VN_TZ).date()
    source = source.lower()
    ticks = _load_ticks_from_lake(cfg, target_date, symbol) if source in {"lake", "auto"} else []
    if not ticks and source in {"redis", "auto"}:
        ticks = _load_ticks_from_redis(symbol)
    if not ticks:
        return None

    filtered = []
    for tick in ticks:
        ts = _tick_time(tick.get("time") or tick.get("timestamp") or tick.get("datetime"))
        if ts is None or ts.date() != target_date or not _is_regular_session(ts):
            continue
        price = _to_float(tick.get("price") or tick.get("close"))
        if price <= 0:
            continue
        filtered.append((ts, price, _to_int(tick.get("volume"))))

    if not filtered:
        return None

    filtered.sort(key=lambda item: item[0])
    prices = [item[1] for item in filtered]
    return {
        "symbol": symbol.upper(),
        "date": target_date,
        "open": prices[0],
        "high": max(prices),
        "low": min(prices),
        "close": prices[-1],
        "volume": sum(item[2] for item in filtered),
    }


def aggregate_all_ticks_to_eod(
    symbols: list[str],
    cfg: EtlConfig,
    target_date: date | None = None,
    source: str = "lake",
) -> list[dict[str, Any]]:
    rows = []
    for symbol in symbols:
        row = aggregate_ticks_to_eod(symbol, cfg, target_date=target_date, source=source)
        if row:
            rows.append(row)
    log.info("Aggregated %d EOD rows from intraday ticks", len(rows))
    return rows
