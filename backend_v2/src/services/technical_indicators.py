from __future__ import annotations

from typing import Any

import pandas as pd


def _float_series(values: pd.Series) -> list[float]:
    cleaned = pd.to_numeric(values, errors="coerce").fillna(0.0)
    return [float(round(item, 4)) for item in cleaned.tolist()]


def _latest_float(values: pd.Series, fallback: float = 0.0) -> float:
    if values.empty:
        return fallback
    parsed = pd.to_numeric(values.iloc[-1], errors="coerce")
    return fallback if pd.isna(parsed) else float(parsed)


def build_technical_payload(
    symbol: str,
    frame: pd.DataFrame,
    *,
    time_col: str,
    open_col: str,
    high_col: str,
    low_col: str,
    close_col: str,
    volume_col: str,
) -> dict[str, Any]:
    if frame.empty:
        return {
            "symbol": symbol,
            "count": 0,
            "ohlcv": {"time": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
            "indicators": {
                "sma_7": [], "sma_21": [], "sma_20": [], "sma_50": [], "sma_200": [],
                "ema_12": [], "ema_26": [], "rsi_14": [], "macd": [], "macd_line": [],
                "signal": [], "macd_signal": [], "macd_histogram": [], "bb_upper": [],
                "bb_middle": [], "bb_lower": [], "stoch_k": [], "stoch_d": [],
                "atr_14": [], "obv": [],
            },
            "signals": {
                "rsi": "neutral",
                "macd": "bearish",
                "golden_cross": False,
                "price_vs_sma200": "below",
                "summary": "neutral",
            },
        }

    frame = frame.copy().reset_index(drop=True)
    close = pd.to_numeric(frame[close_col], errors="coerce").fillna(0.0)
    high = pd.to_numeric(frame[high_col], errors="coerce").fillna(0.0)
    low = pd.to_numeric(frame[low_col], errors="coerce").fillna(0.0)
    volume = pd.to_numeric(frame[volume_col], errors="coerce").fillna(0.0)

    sma_7 = close.rolling(window=7, min_periods=1).mean()
    sma_20 = close.rolling(window=20, min_periods=1).mean()
    sma_21 = close.rolling(window=21, min_periods=1).mean()
    sma_50 = close.rolling(window=50, min_periods=1).mean()
    sma_200 = close.rolling(window=200, min_periods=1).mean()
    ema_12 = close.ewm(span=12, adjust=False, min_periods=1).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=1).mean()

    delta = close.diff().fillna(0.0)
    gains = delta.clip(lower=0)
    losses = (-delta).clip(lower=0)
    avg_gain = gains.rolling(window=14, min_periods=14).mean()
    avg_loss = losses.rolling(window=14, min_periods=14).mean().replace(0, pd.NA)
    rsi = (100 - (100 / (1 + (avg_gain / avg_loss)))).fillna(50.0)

    macd_line = ema_12 - ema_26
    macd_signal = macd_line.ewm(span=9, adjust=False, min_periods=1).mean()
    macd_histogram = macd_line - macd_signal

    bb_middle = sma_20
    bb_std = close.rolling(window=20, min_periods=1).std().fillna(0.0)
    bb_upper = bb_middle + 2 * bb_std
    bb_lower = bb_middle - 2 * bb_std

    lowest_low = low.rolling(window=14, min_periods=1).min()
    highest_high = high.rolling(window=14, min_periods=1).max()
    stoch_range = (highest_high - lowest_low).replace(0, pd.NA)
    stoch_k = (((close - lowest_low) / stoch_range) * 100).fillna(50.0)
    stoch_d = stoch_k.rolling(window=3, min_periods=1).mean()

    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr_14 = tr.rolling(window=14, min_periods=1).mean().fillna(0.0)

    direction = pd.Series(0, index=close.index, dtype=float)
    direction[close > close.shift(1)] = 1.0
    direction[close < close.shift(1)] = -1.0
    obv = (direction * volume).cumsum()
    if not obv.empty:
        obv.iloc[0] = 0.0

    latest_rsi = _latest_float(rsi, fallback=50.0)
    rsi_signal = "oversold" if latest_rsi < 30 else "overbought" if latest_rsi > 70 else "neutral"
    macd_bias = "bullish" if _latest_float(macd_line) >= _latest_float(macd_signal) else "bearish"
    latest_close = _latest_float(close)
    latest_sma200 = _latest_float(sma_200, fallback=latest_close)
    price_vs_sma200 = "above" if latest_close >= latest_sma200 else "below"

    golden_cross = False
    if len(sma_50) > 1 and len(sma_200) > 1:
        previous = _latest_float(sma_50.iloc[:-1]) >= _latest_float(sma_200.iloc[:-1])
        current = _latest_float(sma_50) >= _latest_float(sma_200)
        golden_cross = current and not previous

    score = 0
    score += 1 if rsi_signal == "oversold" else -1 if rsi_signal == "overbought" else 0
    score += 1 if macd_bias == "bullish" else -1
    score += 1 if price_vs_sma200 == "above" else -1
    score += 1 if golden_cross else 0
    summary = "strong_buy" if score >= 3 else "buy" if score == 2 else "strong_sell" if score <= -3 else "sell" if score <= -2 else "neutral"

    indicators = {
        "sma_7": _float_series(sma_7),
        "sma_21": _float_series(sma_21),
        "sma_20": _float_series(sma_20),
        "sma_50": _float_series(sma_50),
        "sma_200": _float_series(sma_200),
        "ema_12": _float_series(ema_12),
        "ema_26": _float_series(ema_26),
        "rsi_14": _float_series(rsi),
        "macd": _float_series(macd_line),
        "macd_line": _float_series(macd_line),
        "signal": _float_series(macd_signal),
        "macd_signal": _float_series(macd_signal),
        "macd_histogram": _float_series(macd_histogram),
        "bb_upper": _float_series(bb_upper),
        "bb_middle": _float_series(bb_middle),
        "bb_lower": _float_series(bb_lower),
        "stoch_k": _float_series(stoch_k),
        "stoch_d": _float_series(stoch_d),
        "atr_14": _float_series(atr_14),
        "obv": _float_series(obv),
    }

    return {
        "symbol": symbol,
        "count": int(len(frame)),
        "ohlcv": {
            "time": frame[time_col].astype(str).tolist(),
            "open": _float_series(frame[open_col]),
            "high": _float_series(frame[high_col]),
            "low": _float_series(frame[low_col]),
            "close": _float_series(frame[close_col]),
            "volume": _float_series(frame[volume_col]),
        },
        "indicators": indicators,
        "signals": {
            "rsi": rsi_signal,
            "macd": macd_bias,
            "golden_cross": bool(golden_cross),
            "price_vs_sma200": price_vs_sma200,
            "summary": summary,
        },
    }
