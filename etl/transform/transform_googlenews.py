"""Merge Google News raw articles into the processed dataset."""
from __future__ import annotations

import pandas as pd

from etl.config import NO_GOOGLE_NEWS_FALLBACK


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _aggregate_google_news(raw: pd.DataFrame, max_per_day: int = 5) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["data_date", "google_news_headlines"])

    df = raw.copy()
    date_source = df["datetime"] if "datetime" in df.columns else df.get("date", pd.Series(dtype=object))
    df["data_date"] = pd.to_datetime(date_source, errors="coerce").dt.strftime("%Y-%m-%d")
    df["title"] = df.get("title", pd.Series(dtype=object)).map(_safe_text)
    desc = df.get("desc", pd.Series("", index=df.index)).map(_safe_text)
    df["headline"] = df["title"]
    df.loc[desc != "", "headline"] = df.loc[desc != "", "title"] + " - " + desc[desc != ""]
    df = df[(df["data_date"].notna()) & (df["headline"] != "")]

    if df.empty:
        return pd.DataFrame(columns=["data_date", "google_news_headlines"])

    return (
        df.groupby("data_date", dropna=True)["headline"]
        .apply(lambda s: " | ".join(s.drop_duplicates().head(max_per_day)))
        .reset_index()
        .rename(columns={"headline": "google_news_headlines"})
    )


def merge_google_news(base: pd.DataFrame, google_news_raw: pd.DataFrame, text_mode: str = "dense") -> pd.DataFrame:
    aggregated = _aggregate_google_news(google_news_raw)
    out = base.merge(aggregated, on="data_date", how="left").sort_values("data_date")

    if text_mode == "dense":
        out["google_news_headlines"] = out["google_news_headlines"].ffill().fillna(NO_GOOGLE_NEWS_FALLBACK)
    else:
        out["google_news_headlines"] = out["google_news_headlines"].fillna("")
    return out.reset_index(drop=True)
