"""Tính toán chỉ báo kỹ thuật (SMA, EMA, RSI, MACD).

Các hàm trong module này **không biết** về warm-up: chúng chỉ tính trên
chuỗi đầu vào. Việc lùi ``fetch_start`` và cắt lại về ``user_start`` được
thực hiện ở ``build_dataset``.
"""
from __future__ import annotations

import pandas as pd


def calculate_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def add_price_indicators(
    df: pd.DataFrame,
    close_col: str = "close_price",
    high_col: str = "high_price",
    low_col: str = "low_price",
    volume_col: str = "volume",
) -> pd.DataFrame:
    """Thêm các chỉ báo kỹ thuật vào ``df`` (đã sort theo ngày)."""
    if df.empty or close_col not in df.columns:
        return df

    out = df.copy()
    close = pd.to_numeric(out[close_col], errors="coerce")

    out["sma_7"] = close.rolling(window=7, min_periods=7).mean()
    out["ema_21"] = close.ewm(span=21, adjust=False).mean()
    out["rsi_14"] = calculate_rsi(close, period=14)

    ema_fast = close.ewm(span=12, adjust=False).mean()
    ema_slow = close.ewm(span=26, adjust=False).mean()
    out["macd"] = ema_fast - ema_slow
    out["macd_signal"] = out["macd"].ewm(span=9, adjust=False).mean()
    out["macd_histogram"] = out["macd"] - out["macd_signal"]

    bb_middle = close.rolling(window=20, min_periods=20).mean()
    bb_std = close.rolling(window=20, min_periods=20).std()
    out["bb_upper"] = bb_middle + (2 * bb_std)
    out["bb_lower"] = bb_middle - (2 * bb_std)

    if volume_col in out.columns:
        volume = pd.to_numeric(out[volume_col], errors="coerce")
        out["vol_sma_20"] = volume.rolling(window=20, min_periods=20).mean()
    else:
        out["vol_sma_20"] = pd.NA

    if high_col in out.columns and low_col in out.columns:
        high = pd.to_numeric(out[high_col], errors="coerce")
        low = pd.to_numeric(out[low_col], errors="coerce")
        prev_close = close.shift(1)
        true_range = pd.concat(
            [
                high - low,
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        out["atr_14"] = true_range.rolling(window=14, min_periods=14).mean()
    else:
        out["atr_14"] = pd.NA

    return out
