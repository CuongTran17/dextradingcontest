from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, WebSocket

from src.database.crypto_market_duckdb import crypto_market_repo
from src.services.binance_market_data import (
    get_candles as get_binance_candles,
    get_latest_prices as get_binance_latest_prices,
    get_order_book as get_binance_order_book,
)

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

ASSETS = [
    {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT_TEST", "display_name": "Bitcoin / USDT_TEST"},
    {"symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT_TEST", "display_name": "Ethereum / USDT_TEST"},
    {"symbol": "SOLUSDT", "base_asset": "SOL", "quote_asset": "USDT_TEST", "display_name": "Solana / USDT_TEST"},
    {"symbol": "XRPUSDT", "base_asset": "XRP", "quote_asset": "USDT_TEST", "display_name": "XRP / USDT_TEST"},
    {"symbol": "BNBUSDT", "base_asset": "BNB", "quote_asset": "USDT_TEST", "display_name": "BNB / USDT_TEST"},
]
SUPPORTED_SYMBOLS = [asset["symbol"] for asset in ASSETS]
WAREHOUSE_TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 5 * 60,
    "15m": 15 * 60,
    "1h": 60 * 60,
    "4h": 4 * 60 * 60,
}

CryptoSymbol = Literal[
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
]


@router.get("/assets")
def get_assets() -> list[dict[str, str]]:
    return ASSETS


def _get_realtime_cache(request: Request):
    service = getattr(request.app.state, "crypto_realtime", None)
    return getattr(service, "cache", None)


def _is_usable_warehouse_window(
    rows: list[dict[str, float]],
    timeframe: str,
    requested_limit: int,
    *,
    now: datetime | None = None,
) -> bool:
    if not rows:
        return False

    step_seconds = WAREHOUSE_TIMEFRAME_SECONDS.get(timeframe)
    if step_seconds is None:
        return True

    if len(rows) < min(requested_limit, 2):
        return False

    timestamps = [int(row["time"]) for row in rows]
    if any(right - left != step_seconds for left, right in zip(timestamps, timestamps[1:])):
        return False

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    freshness_budget = step_seconds * 2 + 120
    return int(current_time.timestamp()) - timestamps[-1] <= freshness_budget


@router.get("/prices/latest")
def get_latest_prices(request: Request) -> dict[str, float]:
    realtime_cache = _get_realtime_cache(request)
    if realtime_cache is not None:
        prices = realtime_cache.get_prices()
        if prices:
            return prices

    try:
        return get_binance_latest_prices(SUPPORTED_SYMBOLS)
    except RuntimeError:
        prices: dict[str, float] = {}
        for symbol in SUPPORTED_SYMBOLS:
            try:
                rows = crypto_market_repo.load_candles(symbol, "1m", limit=1)
            except Exception:
                rows = []
            if rows:
                prices[symbol] = float(rows[-1]["close"])
        if prices:
            return prices
        raise HTTPException(status_code=503, detail="Crypto prices are temporarily unavailable")


@router.get("/candles")
def get_candles(
    symbol: CryptoSymbol,
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1D"] = "1h",
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, float]]:
    if timeframe in {"1m", "5m", "15m", "1h", "4h"}:
        try:
            warehouse_rows = crypto_market_repo.load_candles(
                symbol,
                timeframe,
                limit=limit,
            )
            if _is_usable_warehouse_window(warehouse_rows, timeframe, limit):
                return warehouse_rows
        except Exception:
            pass

    try:
        return get_binance_candles(symbol, timeframe, limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Crypto candles are temporarily unavailable") from exc


@router.get("/indicators")
def get_indicator(
    symbol: CryptoSymbol,
    timeframe: Literal["1m", "5m", "15m", "1h", "4h"] = "1m",
    indicator: Literal["MACD"] = "MACD",
    limit: int = Query(default=300, ge=1, le=1000),
) -> dict[str, Any]:
    try:
        result = crypto_market_repo.load_indicator(symbol, timeframe, indicator, limit=limit)
        if not result["points"]:
            crypto_market_repo.materialize_macd(symbol, timeframe, source_limit=max(limit + 200, 300))
            result = crypto_market_repo.load_indicator(symbol, timeframe, indicator, limit=limit)
        return result
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Crypto indicator data is temporarily unavailable") from exc


@router.get("/orderbook")
def get_orderbook(
    request: Request,
    symbol: CryptoSymbol,
    limit: int = Query(default=100, ge=5, le=5000),
) -> dict[str, Any]:
    realtime_cache = _get_realtime_cache(request)
    if realtime_cache is not None:
        orderbook = realtime_cache.get_orderbook(symbol)
        if orderbook is not None:
            return {
                **orderbook,
                "bids": orderbook["bids"][:limit],
                "asks": orderbook["asks"][:limit],
            }

    try:
        return get_binance_order_book(symbol, limit)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Crypto order book is temporarily unavailable") from exc


@router.websocket("/ws")
async def crypto_websocket(websocket: WebSocket) -> None:
    service = getattr(websocket.app.state, "crypto_realtime", None)
    if service is None:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Crypto realtime service is unavailable"})
        await websocket.close()
        return
    await service.handle_client(websocket)
