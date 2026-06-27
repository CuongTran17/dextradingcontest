"""Ghép toàn bộ raw layer thành dataset sạch (processed layer).

Pipeline transform cho từng mã:
    1. Đọc raw giá      -> chuẩn hoá cột OHLCV, sort theo ngày.
    2. Tính indicator   -> SMA7, EMA21, RSI14, MACD (trên dữ liệu đã warm-up).
    3. Gắn overview     -> sector, industry.
    4. Gắn ratio_summary-> các cột micro_*.
    5. Gắn macro index  -> VNINDEX/VN30/HNXINDEX/UPCOMINDEX (ffill, không bfill).
    6. Gắn news/events  -> text_mode dense hoặc raw.
    7. Cắt warm-up      -> chỉ giữ ``[user_start, user_end]``.
    8. Chọn cột chuẩn   -> đảm bảo thứ tự & presence.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from etl.config import (
    FUNDAMENTAL_METRIC_COLUMNS,
    GOOGLE_NEWS_COLUMNS,
    MACRO_NUMERIC_COLUMNS,
    MACRO_SYMBOLS,
    MICRO_COLUMNS,
    NO_EVENT_FALLBACK,
    NO_GOOGLE_NEWS_FALLBACK,
    NO_NEWS_FALLBACK,
    QUALITY_COLUMNS,
    TECHNICAL_INDICATOR_COLUMNS,
    EtlConfig,
)
from etl.extract.extract_company import (
    load_events,
    load_listing,
    load_news,
    load_overview,
    load_ratio_summary,
)
from etl.extract.extract_prices import load_raw_index, load_raw_prices
from etl.extract.extract_googlenews import load_google_news
from etl.logging_setup import get_logger
from etl.transform.transform_fundamental import merge_fundamental
from etl.transform.transform_googlenews import merge_google_news
from etl.transform.transform_indicators import add_price_indicators
from etl.transform.transform_news import merge_events, merge_news
from etl.transform.transform_validate import (
    enforce_quality_contract,
    enforce_schema,
    report_quality_metrics,
    validate_and_clean,
)

log = get_logger(__name__)

FINAL_COLUMNS: list[str] = [
    "symbol",
    "company_name",
    "sector",
    "industry",
    "data_date",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    *QUALITY_COLUMNS,
    *TECHNICAL_INDICATOR_COLUMNS,
    *[f"micro_{c}" for c in MICRO_COLUMNS],
    *FUNDAMENTAL_METRIC_COLUMNS,
    *MACRO_NUMERIC_COLUMNS,
    "news_headlines",
    "event_headlines",
    *GOOGLE_NEWS_COLUMNS,
]


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


# ---------------------------------------------------------------------------
# Macro frame từ các chỉ số
# ---------------------------------------------------------------------------
def build_macro_frame(cfg: EtlConfig) -> pd.DataFrame:
    """Gộp giá chỉ số (VNINDEX/VN30/...) thành khung theo ngày."""
    base: pd.DataFrame | None = None

    for idx in MACRO_SYMBOLS:
        raw = load_raw_index(idx, cfg)
        if raw.empty:
            log.warning("Macro index %s empty, skip", idx)
            continue

        df = raw.copy()
        df["data_date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
        prefix = idx.lower()
        df = df.rename(
            columns={
                "open": f"macro_{prefix}_open",
                "high": f"macro_{prefix}_high",
                "low": f"macro_{prefix}_low",
                "close": f"macro_{prefix}_close",
                "volume": f"macro_{prefix}_volume",
            }
        )

        keep = [
            "data_date",
            f"macro_{prefix}_open",
            f"macro_{prefix}_high",
            f"macro_{prefix}_low",
            f"macro_{prefix}_close",
            f"macro_{prefix}_volume",
        ]
        df = df[keep].drop_duplicates("data_date", keep="last")

        base = df if base is None else base.merge(df, on="data_date", how="outer")

    if base is None:
        return pd.DataFrame(columns=["data_date"])

    return base.sort_values("data_date").drop_duplicates("data_date", keep="last").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Company metadata
# ---------------------------------------------------------------------------
def build_company_meta(cfg: EtlConfig) -> pd.DataFrame:
    listing = load_listing(cfg)
    if listing.empty:
        return pd.DataFrame(columns=["symbol", "company_name"])
    listing = listing.rename(columns={"organ_name": "company_name"})
    listing["symbol"] = listing["symbol"].astype(str).str.upper()
    if "company_name" not in listing.columns:
        listing["company_name"] = ""
    return listing[["symbol", "company_name"]].drop_duplicates("symbol", keep="last")


# ---------------------------------------------------------------------------
# Per-symbol transform
# ---------------------------------------------------------------------------
def build_symbol_dataset(
    symbol: str,
    cfg: EtlConfig,
    company_meta: pd.DataFrame,
    macro_frame: pd.DataFrame,
) -> pd.DataFrame:
    """Dựng 1 DataFrame sạch cho 1 mã từ các raw file đã ghi."""
    prices = load_raw_prices(symbol, cfg)
    if prices.empty:
        log.warning("No raw prices for %s, skip", symbol)
        return pd.DataFrame()

    prices = prices.copy()
    prices["symbol"] = symbol
    prices["data_date"] = pd.to_datetime(prices["time"]).dt.strftime("%Y-%m-%d")
    prices = prices.rename(
        columns={
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "volume",
        }
    )
    prices = prices.sort_values("data_date").reset_index(drop=True)

    # 1b. Data-quality gate before indicators.
    prices = validate_and_clean(prices, symbol=symbol)
    if prices.empty:
        log.warning("No valid prices after quality clean for %s, skip", symbol)
        return pd.DataFrame()

    # 2. Indicators — tính trên TOÀN BỘ cửa sổ fetch (đã warm-up).
    prices = add_price_indicators(prices, close_col="close_price")

    # 3. Overview -> sector/industry
    overview = load_overview(symbol, cfg)
    sector = ""
    industry = ""
    if not overview.empty:
        row = overview.iloc[0]
        sector = _safe_text(row.get("icb_name2"))
        industry = _safe_text(row.get("icb_name3"))
    prices["sector"] = sector
    prices["industry"] = industry

    # 4. Ratio summary -> micro_*
    ratio = load_ratio_summary(symbol, cfg)
    for col in MICRO_COLUMNS:
        prices[f"micro_{col}"] = pd.NA
    if not ratio.empty:
        row = ratio.iloc[0]
        for col in MICRO_COLUMNS:
            if col in row.index:
                prices[f"micro_{col}"] = row.get(col, pd.NA)

    # 4b. Fundamental quarterly reports -> daily aligned columns.
    prices = merge_fundamental(prices, symbol, cfg)

    # 5. News & events — KHÔNG bfill
    news_raw = load_news(symbol, cfg)
    events_raw = load_events(symbol, cfg)
    prices = merge_news(prices, news_raw, text_mode=cfg.text_mode)
    prices = merge_events(prices, events_raw, text_mode=cfg.text_mode)

    # 5b. Google News — same anti-lookahead behavior as local news.
    google_news_raw = pd.DataFrame(load_google_news(symbol, cfg))
    prices = merge_google_news(prices, google_news_raw, text_mode=cfg.text_mode)

    # 6. Company metadata
    prices = prices.merge(company_meta, on="symbol", how="left")

    # 7. Macro
    if not macro_frame.empty:
        prices = prices.merge(macro_frame, on="data_date", how="left")

    for col in MACRO_NUMERIC_COLUMNS:
        if col in prices.columns:
            prices[col] = pd.to_numeric(prices[col], errors="coerce")

    prices = prices.sort_values("data_date").reset_index(drop=True)

    # Anti look-ahead: only carry past macro values forward.
    # Remaining leading nulls are filled with 0.0 instead of bfill, so we do not
    # leak future macro prices into the first rows of the dataset.
    macro_present = [c for c in MACRO_NUMERIC_COLUMNS if c in prices.columns]
    if macro_present:
        prices[macro_present] = prices[macro_present].ffill().fillna(0.0)

    # 8. Đảm bảo đủ cột chuẩn
    for col in FINAL_COLUMNS:
        if col not in prices.columns:
            prices[col] = pd.NA

    prices = prices[FINAL_COLUMNS]

    # Fallback text cho dense mode
    if cfg.text_mode == "dense":
        prices["news_headlines"] = prices["news_headlines"].fillna(NO_NEWS_FALLBACK)
        prices["event_headlines"] = prices["event_headlines"].fillna(NO_EVENT_FALLBACK)
        prices["google_news_headlines"] = prices["google_news_headlines"].fillna(NO_GOOGLE_NEWS_FALLBACK)
    else:
        prices["news_headlines"] = prices["news_headlines"].fillna("")
        prices["event_headlines"] = prices["event_headlines"].fillna("")
        prices["google_news_headlines"] = prices["google_news_headlines"].fillna("")

    # 9. Cắt warm-up -> đúng [user_start, user_end]
    user_start_ts = pd.Timestamp(cfg.user_start)
    user_end_ts = pd.Timestamp(cfg.user_end)
    ts = pd.to_datetime(prices["data_date"])
    prices = prices[(ts >= user_start_ts) & (ts <= user_end_ts)].reset_index(drop=True)

    prices = enforce_schema(
        prices,
        {
            "data_date": "str",
            "open_price": "float64",
            "high_price": "float64",
            "low_price": "float64",
            "close_price": "float64",
            "volume": "int64",
            "is_outlier": "bool",
        },
    )
    report_quality_metrics(prices, symbol)

    log.info(
        "Built dataset %s rows=%d range=%s..%s",
        symbol,
        len(prices),
        prices["data_date"].min() if not prices.empty else "-",
        prices["data_date"].max() if not prices.empty else "-",
    )
    return prices


# ---------------------------------------------------------------------------
# Orchestrator-friendly entry
# ---------------------------------------------------------------------------
def build_full_dataset(symbols: Iterable[str], cfg: EtlConfig) -> pd.DataFrame:
    company_meta = build_company_meta(cfg)
    macro_frame = build_macro_frame(cfg)

    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        df = build_symbol_dataset(symbol, cfg, company_meta, macro_frame)
        if not df.empty:
            frames.append(df)

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    combined = combined.sort_values(["symbol", "data_date"]).reset_index(drop=True)
    return combined


# ---------------------------------------------------------------------------
# Data quality gate
# ---------------------------------------------------------------------------
def validate_dataset(df: pd.DataFrame, expected_symbols: Iterable[str] | None = None) -> dict[str, object]:
    if df.empty:
        raise RuntimeError("Processed dataset is empty")

    missing = [c for c in FINAL_COLUMNS if c not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns: {missing}")

    quality_report = enforce_quality_contract(
        df,
        expected_symbols=[str(symbol).upper() for symbol in expected_symbols] if expected_symbols else None,
    )

    # Mỗi mã phải có >= 80% số phiên so với mã có nhiều phiên nhất
    per_symbol = df.groupby("symbol")["data_date"].nunique()
    threshold = per_symbol.max() * 0.8
    thin = per_symbol[per_symbol < threshold]
    if not thin.empty:
        log.warning("Thin symbols (<80%% sessions): %s", thin.to_dict())

    return quality_report
