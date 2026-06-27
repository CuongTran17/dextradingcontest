"""Merge quarterly fundamental data into daily symbol rows."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from typing import Any

import pandas as pd

from etl.config import FUNDAMENTAL_METRIC_COLUMNS, EtlConfig
from etl.extract.extract_fundamental import load_fundamental


def _normalize(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _to_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace(",", "").replace("%", "").strip()
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def _period_key(row: dict[str, Any]) -> tuple[int, int]:
    year = _to_number(row.get("yearReport") or row.get("year") or row.get("Year") or row.get("nam"))
    quarter = _to_number(row.get("lengthReport") or row.get("quarter") or row.get("Quarter") or row.get("quy"))
    return int(year or 0), int(quarter or 0)


def _available_date(row: dict[str, Any]) -> pd.Timestamp | None:
    for key in ("publish_date", "public_date", "reportDate", "date", "period"):
        if key in row:
            parsed = pd.to_datetime(row.get(key), errors="coerce")
            if pd.notna(parsed):
                return pd.Timestamp(parsed).normalize()

    year, quarter = _period_key(row)
    if year <= 0:
        return None
    if 1 <= quarter <= 4:
        period_end = pd.Timestamp(date(year, quarter * 3, 1)) + pd.offsets.MonthEnd(0)
        return period_end + pd.Timedelta(days=45)
    return pd.Timestamp(date(year, 12, 31)) + pd.Timedelta(days=90)


def _extract_metric(row: dict[str, Any], keywords: list[str]) -> float | None:
    normalized_keywords = [_normalize(k) for k in keywords]
    for key, value in row.items():
        nkey = _normalize(key)
        if any(keyword and keyword in nkey for keyword in normalized_keywords):
            parsed = _to_number(value)
            if parsed is not None:
                return parsed
    return None


def _build_fundamental_frame(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    income_rows = load_fundamental(symbol, "income", cfg)
    balance_rows = load_fundamental(symbol, "balance", cfg)

    by_period: dict[tuple[int, int], dict[str, Any]] = {}
    for row in income_rows:
        key = _period_key(row)
        if key == (0, 0):
            continue
        entry = by_period.setdefault(key, {"available_date": _available_date(row)})
        entry["fund_revenue"] = _extract_metric(row, ["revenue", "doanh thu thuan", "doanh thu"])
        entry["fund_net_profit"] = _extract_metric(row, ["net profit", "profit after tax", "loi nhuan sau thue"])

    for row in balance_rows:
        key = _period_key(row)
        if key == (0, 0):
            continue
        entry = by_period.setdefault(key, {"available_date": _available_date(row)})
        if entry.get("available_date") is None:
            entry["available_date"] = _available_date(row)
        entry["fund_total_assets"] = _extract_metric(row, ["total assets", "tong tai san"])
        entry["fund_total_equity"] = _extract_metric(row, ["total equity", "owner equity", "von chu so huu"])

    records = []
    for (year, quarter), values in by_period.items():
        available = values.get("available_date")
        if available is None:
            continue
        record = {"year": year, "quarter": quarter, "available_date": pd.Timestamp(available)}
        for col in FUNDAMENTAL_METRIC_COLUMNS:
            if col != "fund_revenue_growth":
                record[col] = values.get(col)
        records.append(record)

    if not records:
        return pd.DataFrame(columns=["available_date", *FUNDAMENTAL_METRIC_COLUMNS])

    frame = pd.DataFrame(records).sort_values(["year", "quarter"]).reset_index(drop=True)
    frame["fund_revenue_growth"] = pd.to_numeric(frame["fund_revenue"], errors="coerce").pct_change()
    return frame[["available_date", *FUNDAMENTAL_METRIC_COLUMNS]].sort_values("available_date")


def merge_fundamental(base: pd.DataFrame, symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    out = base.copy()
    for col in FUNDAMENTAL_METRIC_COLUMNS:
        if col not in out.columns:
            out[col] = pd.NA

    fundamental = _build_fundamental_frame(symbol, cfg)
    if fundamental.empty:
        return out

    left = out.copy()
    left["_merge_date"] = pd.to_datetime(left["data_date"], errors="coerce")
    merged = pd.merge_asof(
        left.sort_values("_merge_date"),
        fundamental.sort_values("available_date"),
        left_on="_merge_date",
        right_on="available_date",
        direction="backward",
        suffixes=("", "_fund"),
    )
    for col in FUNDAMENTAL_METRIC_COLUMNS:
        fund_col = f"{col}_fund"
        if fund_col in merged.columns:
            merged[col] = merged[fund_col]
            merged = merged.drop(columns=[fund_col])
    return merged.drop(columns=[c for c in ("_merge_date", "available_date") if c in merged.columns]).sort_values("data_date").reset_index(drop=True)
