from __future__ import annotations

import json
from typing import Any

import httpx

BASE_ENDPOINTS = [
    "https://data-api.binance.vision",
    "https://api.binance.com",
    "https://api-gcp.binance.com",
    "https://api1.binance.com",
    "https://api2.binance.com",
    "https://api3.binance.com",
    "https://api4.binance.com",
]

TIMEFRAME_TO_INTERVAL = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1D": "1d",
}


def get_latest_prices(symbols: list[str]) -> dict[str, float]:
    payload = _request_json(
        "/api/v3/ticker/24hr",
        {"symbols": json.dumps(symbols, separators=(",", ":")), "type": "MINI"},
    )
    rows = payload if isinstance(payload, list) else [payload]
    return {row["symbol"]: float(row["lastPrice"]) for row in rows}


def get_candles(symbol: str, timeframe: str, limit: int) -> list[dict[str, float]]:
    interval = TIMEFRAME_TO_INTERVAL.get(timeframe, "1h")
    safe_limit = min(max(int(limit), 1), 1000)
    payload = _request_json(
        "/api/v3/klines",
        {"symbol": symbol, "interval": interval, "limit": safe_limit},
    )
    return [
        {
            "time": int(row[0]) // 1000,
            "open": float(row[1]),
            "high": float(row[2]),
            "low": float(row[3]),
            "close": float(row[4]),
            "volume": float(row[5]),
        }
        for row in payload
    ]


def get_order_book(symbol: str, limit: int) -> dict[str, Any]:
    safe_limit = _normalize_depth_limit(limit)
    payload = _request_json("/api/v3/depth", {"symbol": symbol, "limit": safe_limit})
    bids = [_map_depth_level(level) for level in payload.get("bids", [])]
    asks = [_map_depth_level(level) for level in payload.get("asks", [])]
    best_bid = bids[0]["price"] if bids else 0.0
    best_ask = asks[0]["price"] if asks else 0.0

    return {
        "symbol": symbol,
        "last_update_id": payload.get("lastUpdateId"),
        "bids": bids,
        "asks": asks,
        "spread": best_ask - best_bid if best_bid and best_ask else 0.0,
        "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0,
        "source": "binance",
    }


def _request_json(path: str, params: dict[str, Any]) -> Any:
    last_error: Exception | None = None
    for base_url in BASE_ENDPOINTS:
        try:
            with httpx.Client(base_url=base_url, timeout=8.0) as client:
                response = client.get(path, params=params)
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            last_error = exc

    raise RuntimeError(f"Binance market data unavailable: {last_error}")


def _map_depth_level(level: list[str]) -> dict[str, float]:
    price = float(level[0])
    quantity = float(level[1])
    return {"price": price, "quantity": quantity, "total": price * quantity}


def _normalize_depth_limit(limit: int) -> int:
    if limit <= 5:
        return 5
    if limit <= 10:
        return 10
    if limit <= 20:
        return 20
    if limit <= 50:
        return 50
    if limit <= 100:
        return 100
    if limit <= 500:
        return 500
    if limit <= 1000:
        return 1000
    return 5000
