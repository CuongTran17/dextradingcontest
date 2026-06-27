"""Extract lịch sử giá (OHLCV) cho một mã hoặc một chỉ số.

Raw output:
    lake/raw/prices/<SYMBOL>/<run_id>.csv          – cổ phiếu
    lake/raw/macro_index/<SYMBOL>/<run_id>.csv     – chỉ số (VNINDEX, VN30, ...)

Module KHÔNG tính EMA/RSI/MACD – đó là việc của layer ``transform``.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Optional

import pandas as pd
from vnstock import Vnstock

from etl.config import EtlConfig
from etl.logging_setup import get_logger
from etl.retry import with_retry

log = get_logger(__name__)


@with_retry()
def _fetch_history(symbol: str, start: date, end: date, source: str = "KBS") -> pd.DataFrame:
    """Gọi vnstock để lấy OHLCV. Có retry tự động với backoff.

    Tạo ``Vnstock()`` bên trong hàm để mỗi worker thread có client riêng
    (vnstock <3.x không hoàn toàn thread-safe).
    """
    stock = Vnstock().stock(symbol=symbol, source=source)
    return stock.quote.history(
        start=str(start),
        end=str(end),
        interval="1D",
    )


_REQUIRED_PRICE_COLUMNS = {"time", "open", "high", "low", "close", "volume"}


def _fetch_history_with_fallback(
    symbol: str, start: date, end: date, sources: list[str]
) -> pd.DataFrame:
    """Thử fetch lần lượt từ các source trong danh sách. Trả về kết quả đầu tiên hợp lệ."""
    last_exc: Exception | None = None

    for source in sources:
        try:
            df = _fetch_history(symbol, start, end, source=source)
            if df is None or df.empty:
                log.info("No data from source=%s for %s, trying next...", source, symbol)
                continue

            # Validate schema
            missing = _REQUIRED_PRICE_COLUMNS - set(df.columns)
            if missing:
                log.warning(
                    "Source=%s returned invalid schema for %s (missing: %s), trying next...",
                    source, symbol, missing,
                )
                continue

            log.info("Fetched prices %s from source=%s (%d rows)", symbol, source, len(df))
            return df
        except Exception as exc:
            log.info("Source=%s failed for %s: %s — trying next...", source, symbol, exc)
            last_exc = exc
            continue

    if last_exc:
        log.warning("All sources failed for %s, last error: %s", symbol, last_exc)
    return pd.DataFrame()


def extract_symbol_prices(symbol: str, cfg: EtlConfig) -> Optional[Path]:
    """Fetch giá 1 mã cổ phiếu, ghi raw CSV. Trả về đường dẫn file đã ghi."""
    df = _fetch_history_with_fallback(symbol, cfg.fetch_start, cfg.user_end, cfg.extract_sources)
    if df is None or df.empty:
        log.warning("No price data returned for %s", symbol)
        return None

    out = cfg.raw_path("prices", symbol=symbol, suffix="csv")
    df.to_csv(out, index=False, encoding="utf-8")
    log.info("Saved raw prices %s -> %s (%d rows)", symbol, out, len(df))
    return out


def extract_index_prices(index_symbol: str, cfg: EtlConfig) -> Optional[Path]:
    """Fetch giá chỉ số (VNINDEX/VN30/...)."""
    df = _fetch_history_with_fallback(index_symbol, cfg.fetch_start, cfg.user_end, cfg.extract_sources)
    if df is None or df.empty:
        log.warning("No macro index data returned for %s", index_symbol)
        return None

    out = cfg.raw_path("macro_index", symbol=index_symbol, suffix="csv")
    df.to_csv(out, index=False, encoding="utf-8")
    log.info("Saved raw index %s -> %s (%d rows)", index_symbol, out, len(df))
    return out


def load_raw_prices(symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    """Đọc lại file raw giá cổ phiếu đã ghi ở lần chạy hiện tại."""
    path = cfg.raw_dir / "prices" / symbol.upper() / f"{cfg.run_id}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_raw_index(index_symbol: str, cfg: EtlConfig) -> pd.DataFrame:
    path = cfg.raw_dir / "macro_index" / index_symbol.upper() / f"{cfg.run_id}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)
