"""
Pure helper / utility functions.

No FastAPI imports, no DB access – safe to import anywhere.
"""
from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

import pandas as pd

VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


# ── Environment helpers ──────────────────────────────────────────────


# ── Scalar coercions ─────────────────────────────────────────────────


def _to_float(value: Any, fallback: float = 0.0) -> float:
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return fallback


def _to_number_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, str):
        raw = value.strip().replace(",", "")
        if not raw:
            return None
        try:
            numeric = float(raw)
            return numeric if math.isfinite(numeric) else None
        except ValueError:
            return None
    return None


def _to_float_series(values: pd.Series) -> list[float]:
    cleaned = pd.to_numeric(values, errors="coerce").fillna(0.0)
    return [float(round(item, 4)) for item in cleaned.tolist()]


# ── Datetime helpers ─────────────────────────────────────────────────


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        parsed = value.to_pydatetime()
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc)

    if isinstance(value, (int, float)):
        seconds = float(value)
        if seconds > 1_000_000_000_000:
            seconds /= 1000.0
        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            return None

    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None

        if raw.isdigit():
            return _parse_datetime(int(raw))

        for candidate in (raw, raw.replace("Z", "+00:00"), raw.replace(" ", "T")):
            try:
                parsed = datetime.fromisoformat(candidate)
                if parsed.tzinfo is None:
                    return parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                continue

        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed = datetime.strptime(raw, fmt)
                return parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

    return None


def _to_iso_datetime(value: Any, fallback: Optional[str] = None) -> str:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.isoformat()
    if fallback:
        return fallback
    return _utc_now().isoformat()


def _to_iso_date(value: Any) -> str:
    parsed = _parse_datetime(value)
    if parsed:
        return parsed.date().isoformat()
    return ""


# ── Column / scalar normalisation ────────────────────────────────────


def _normalize_column_name(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [str(part).strip() for part in column if str(part).strip()]
        return " | ".join(parts)
    return str(column).strip()


def _normalize_scalar(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().isoformat()

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, bool):
        return value

    if isinstance(value, int):
        return int(value)

    if isinstance(value, float):
        return float(value) if math.isfinite(value) else None

    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None

    if isinstance(value, dict):
        return {str(key): _normalize_scalar(item) for key, item in value.items()}

    if isinstance(value, (list, tuple)):
        return [_normalize_scalar(item) for item in value]

    if hasattr(value, "item"):
        try:
            return _normalize_scalar(value.item())
        except Exception:
            pass

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return str(value)


def _frame_to_records(frame: Optional[pd.DataFrame]) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []

    rows: list[dict[str, Any]] = []
    for row in frame.to_dict("records"):
        normalized_row: dict[str, Any] = {}
        for key, value in row.items():
            normalized_key = _normalize_column_name(key)
            if normalized_key:
                normalized_row[normalized_key] = _normalize_scalar(value)
        if normalized_row:
            rows.append(normalized_row)
    return rows


# ── JSON helpers ─────────────────────────────────────────────────────


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def _json_loads(payload_json: str, fallback: Any) -> Any:
    try:
        return json.loads(payload_json)
    except Exception:
        return fallback


# ── Row timestamp helpers ─────────────────────────────────────────────


def _row_iso_timestamp(value: Any) -> Optional[str]:
    parsed = _parse_datetime(value)
    return parsed.isoformat() if parsed else None


def _row_is_fresh(updated_at: Any, ttl_seconds: int) -> bool:
    parsed = _parse_datetime(updated_at)
    if not parsed:
        return False
    return (_utc_now() - parsed).total_seconds() < ttl_seconds


# ── Impact / cache helpers ────────────────────────────────────────────


def _impact_from_price_change_pct(value: Any) -> str:
    pct = _to_float(value, fallback=0.0)
    if abs(pct) <= 1:
        pct *= 100.0

    abs_pct = abs(pct)
    if abs_pct >= 3.0:
        return "high"
    if abs_pct >= 1.0:
        return "medium"
    return "low"


def _cache_fresh(entry: Optional[dict[str, Any]], ttl_seconds: int) -> bool:
    if not entry:
        return False
    updated_at = entry.get("updated_at")
    if not isinstance(updated_at, datetime):
        return False
    return (_utc_now() - updated_at).total_seconds() < ttl_seconds


# ── Financial metric helpers ─────────────────────────────────────────


def _select_latest_financial_record(records: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    if not records:
        return None

    def _row_sort_key(row: dict[str, Any]) -> tuple[int, int]:
        period = str(row.get("period") or "")
        if "-Q" in period:
            year_text, quarter_text = period.split("-Q", 1)
            return (_to_int(year_text), _to_int(quarter_text.split("_", 1)[0]))
        return (
            _to_int(row.get("yearReport") or row.get("year") or row.get("Year")),
            _to_int(row.get("lengthReport") or row.get("quarter") or row.get("Quarter")),
        )

    return max(records, key=_row_sort_key)


def _extract_metric(row: dict[str, Any], keywords: list[str]) -> Optional[float]:
    normalized_keywords = [item.lower() for item in keywords]
    for key, value in row.items():
        key_text = str(key).lower()
        if any(token in key_text for token in normalized_keywords):
            numeric = _to_number_or_none(value)
            if numeric is not None:
                return numeric
    return None


def _extract_valuation_from_ratios(records: list[dict[str, Any]]) -> dict[str, Optional[float]]:
    row = _select_latest_financial_record(records)
    if not row:
        return {
            "pe": None,
            "pb": None,
            "eps": None,
            "roe": None,
            "roa": None,
            "market_cap": None,
        }

    return {
        "pe": _to_number_or_none(row.get("pe")) or _extract_metric(row, ["p/e", " pe", "pe_ratio"]),
        "pb": _to_number_or_none(row.get("pb")) or _extract_metric(row, ["p/b", " pb", "pb_ratio"]),
        "eps": _to_number_or_none(row.get("eps")) or _extract_metric(row, ["eps", "trailing_eps"]),
        "roe": _to_number_or_none(row.get("roe")) or _extract_metric(row, ["roe"]),
        "roa": _to_number_or_none(row.get("roa")) or _extract_metric(row, ["roa"]),
        "market_cap": _to_number_or_none(row.get("market_cap")) or _extract_metric(row, ["market capital", "market cap"]),
    }


# ── Intraday bar builder ─────────────────────────────────────────────


def _build_intraday_bars_from_ticks(
    ticks: list[dict[str, Any]],
    interval_minutes: int = 1,
) -> list[dict[str, Any]]:
    safe_interval = max(interval_minutes, 1)
    bucket_seconds = safe_interval * 60

    buckets: dict[int, dict[str, Any]] = {}
    ordered_ticks = sorted(ticks, key=lambda item: str(item.get("time") or ""))
    for tick in ordered_ticks:
        price = _to_float(tick.get("price"))
        if price <= 0:
            continue

        parsed_time = _parse_datetime(tick.get("time"))
        if parsed_time is None:
            continue

        local_time = parsed_time.astimezone(VN_TZ)
        bucket_epoch = int(local_time.timestamp()) // bucket_seconds * bucket_seconds
        volume = _to_int(tick.get("volume"))

        candle = buckets.get(bucket_epoch)
        if candle is None:
            bucket_time = datetime.fromtimestamp(bucket_epoch, tz=VN_TZ).replace(second=0, microsecond=0)
            buckets[bucket_epoch] = {
                "time": bucket_time.isoformat(),
                "open": price,
                "high": price,
                "low": price,
                "close": price,
                "volume": volume,
            }
            continue

        candle["high"] = max(_to_float(candle.get("high")), price)
        candle["low"] = min(_to_float(candle.get("low"), fallback=price), price)
        candle["close"] = price
        candle["volume"] = _to_int(candle.get("volume")) + volume

    return [buckets[key] for key in sorted(buckets.keys())]
