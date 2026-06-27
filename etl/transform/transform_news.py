"""Chuẩn hoá news / events: gom theo ngày, ffill tuỳ chế độ text_mode.

Raw input là JSON record-oriented (DataFrame.to_dict(orient="records")).
Không có ``bfill`` – tránh look-ahead bias.
"""
from __future__ import annotations

import pandas as pd

from etl.config import NO_EVENT_FALLBACK, NO_NEWS_FALLBACK


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _parse_public_date_to_day(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    dt = pd.to_datetime(numeric, unit="ms", errors="coerce")
    fallback = pd.to_datetime(series, errors="coerce")
    dt = dt.fillna(fallback)
    return dt.dt.strftime("%Y-%m-%d")


def _aggregate_daily(
    raw: pd.DataFrame,
    text_col: str,
    out_col: str,
    max_per_day: int,
) -> pd.DataFrame:
    if raw.empty or text_col not in raw.columns or "public_date" not in raw.columns:
        return pd.DataFrame(columns=["data_date", out_col])

    df = raw.copy()
    df["data_date"] = _parse_public_date_to_day(df["public_date"])
    df[text_col] = df[text_col].map(_safe_text)
    df = df[df[text_col] != ""]
    if df.empty:
        return pd.DataFrame(columns=["data_date", out_col])

    grouped = (
        df.groupby("data_date", dropna=True)[text_col]
        .apply(lambda s: " | ".join(s.head(max_per_day)))
        .reset_index()
        .rename(columns={text_col: out_col})
    )
    return grouped


def merge_news(base: pd.DataFrame, news_raw: pd.DataFrame, text_mode: str = "dense") -> pd.DataFrame:
    """Gắn cột ``news_headlines`` vào ``base``. KHÔNG dùng bfill."""
    aggregated = _aggregate_daily(news_raw, "news_title", "news_headlines", max_per_day=5)

    out = base.merge(aggregated, on="data_date", how="left").sort_values("data_date")

    if text_mode == "dense":
        # Chỉ ffill (quá khứ -> hiện tại). Không bfill.
        out["news_headlines"] = out["news_headlines"].ffill().fillna(NO_NEWS_FALLBACK)
    else:
        out["news_headlines"] = out["news_headlines"].fillna("")

    return out.reset_index(drop=True)


def merge_events(base: pd.DataFrame, events_raw: pd.DataFrame, text_mode: str = "dense") -> pd.DataFrame:
    """Gắn cột ``event_headlines`` vào ``base``. KHÔNG dùng bfill."""
    aggregated = _aggregate_daily(events_raw, "event_title", "event_headlines", max_per_day=3)

    out = base.merge(aggregated, on="data_date", how="left").sort_values("data_date")

    if text_mode == "dense":
        out["event_headlines"] = out["event_headlines"].ffill().fillna(NO_EVENT_FALLBACK)
    else:
        out["event_headlines"] = out["event_headlines"].fillna("")

    return out.reset_index(drop=True)
