"""Small vnstock adapter layer for ETL-owned data contracts."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd
from vnstock import Vnstock

from etl.retry import _acquire_rate_slot

RATIO_ITEM_MAP = {
    "trailing_eps": "eps",
    "pe_ratio": "pe",
    "pb_ratio": "pb",
    "roe": "roe",
    "roa": "roa",
}


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
        if not value:
            return None
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def _period_sort_key(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})-Q([1-4])(?:_\d+)?", str(period))
    if not match:
        return (0, 0)
    return int(match.group(1)), int(match.group(2))


def _quarter_columns(frame: pd.DataFrame) -> list[str]:
    columns = [str(column) for column in frame.columns]
    return sorted(
        [column for column in columns if _period_sort_key(column) != (0, 0)],
        key=_period_sort_key,
        reverse=True,
    )


def normalize_kbs_ratio_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty or "item_id" not in frame.columns:
        return []

    periods = _quarter_columns(frame)
    if not periods:
        return []

    latest_period = periods[0]
    by_item = {
        str(row.get("item_id") or "").strip(): row
        for row in frame.to_dict("records")
    }

    record: dict[str, Any] = {
        "period": latest_period,
        "source": "vnstock-kbs-ratio",
    }
    for upstream_key, normalized_key in RATIO_ITEM_MAP.items():
        row = by_item.get(upstream_key)
        record[normalized_key] = _to_number(row.get(latest_period)) if row else None

    return [record]


def fetch_ratio_summary(symbol: str) -> list[dict[str, Any]]:
    for source in ("KBS", "VCI"):
        try:
            _acquire_rate_slot()
            stock = Vnstock().stock(symbol=symbol, source=source)
            try:
                frame = stock.finance.ratio(period="quarter")
            except TypeError:
                frame = stock.finance.ratio()

            if not isinstance(frame, pd.DataFrame) or frame.empty:
                continue

            if source.upper() == "KBS":
                records = normalize_kbs_ratio_frame(frame)
                if records:
                    return records

            records = frame.to_dict(orient="records")
            if records:
                return records
        except Exception:
            continue

    return []
