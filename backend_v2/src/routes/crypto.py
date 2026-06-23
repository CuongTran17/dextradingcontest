from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.binance_market_data import (
    get_candles as get_binance_candles,
    get_latest_prices as get_binance_latest_prices,
    get_order_book as get_binance_order_book,
)
from src.services.crypto_simulator import execute_market_order, portfolio_metrics

router = APIRouter(prefix="/api/crypto", tags=["crypto"])

ASSETS = [
    {"symbol": "BTCUSDT", "base_asset": "BTC", "quote_asset": "USDT_TEST", "display_name": "Bitcoin / USDT_TEST"},
    {"symbol": "ETHUSDT", "base_asset": "ETH", "quote_asset": "USDT_TEST", "display_name": "Ethereum / USDT_TEST"},
    {"symbol": "SOLUSDT", "base_asset": "SOL", "quote_asset": "USDT_TEST", "display_name": "Solana / USDT_TEST"},
]
LATEST_PRICES = {"BTCUSDT": 64250.0, "ETHUSDT": 3420.0, "SOLUSDT": 148.0}


class MarketOrderRequest(BaseModel):
    portfolio: dict[str, Any]
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    side: Literal["buy", "sell"]
    quantity: float = Field(gt=0)


@router.get("/assets")
def get_assets() -> list[dict[str, str]]:
    return ASSETS


@router.get("/prices/latest")
def get_latest_prices() -> dict[str, float]:
    try:
        return get_binance_latest_prices(list(LATEST_PRICES.keys()))
    except RuntimeError:
        return LATEST_PRICES


@router.get("/candles")
def get_candles(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    timeframe: Literal["1m", "5m", "15m", "1h", "4h", "1D"] = "1h",
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[dict[str, float]]:
    try:
        return get_binance_candles(symbol, timeframe, limit)
    except RuntimeError:
        return _mock_candles(symbol, timeframe, limit)


@router.get("/orderbook")
def get_orderbook(
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT"],
    limit: int = Query(default=100, ge=5, le=5000),
) -> dict[str, Any]:
    try:
        return get_binance_order_book(symbol, limit)
    except RuntimeError:
        return _mock_order_book(symbol, limit)


@router.post("/orders/market")
def create_market_order(payload: MarketOrderRequest) -> dict[str, Any]:
    try:
        latest_prices = get_latest_prices()
        portfolio = execute_market_order(
            payload.portfolio,
            payload.symbol,
            payload.side,
            payload.quantity,
            latest_prices[payload.symbol],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "portfolio": portfolio,
        "metrics": portfolio_metrics(portfolio, latest_prices),
    }


def _mock_candles(symbol: str, timeframe: str, limit: int) -> list[dict[str, float]]:
    step_seconds = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600, "4h": 14400, "1D": 86400}[timeframe]
    base_price = LATEST_PRICES[symbol]
    return [
        {
            "time": index * step_seconds,
            "open": base_price,
            "high": base_price * 1.002,
            "low": base_price * 0.998,
            "close": base_price,
            "volume": 1000.0 + index,
        }
        for index in range(limit)
    ]


def _mock_order_book(symbol: str, limit: int) -> dict[str, Any]:
    count = min(limit, 100)
    mid_price = LATEST_PRICES[symbol]
    bids = [
        {
            "price": mid_price - index - 0.5,
            "quantity": 1.0 + index / 10,
            "total": (mid_price - index - 0.5) * (1.0 + index / 10),
        }
        for index in range(count)
    ]
    asks = [
        {
            "price": mid_price + index + 0.5,
            "quantity": 1.0 + index / 10,
            "total": (mid_price + index + 0.5) * (1.0 + index / 10),
        }
        for index in range(count)
    ]
    return {
        "symbol": symbol,
        "last_update_id": None,
        "bids": bids,
        "asks": asks,
        "spread": asks[0]["price"] - bids[0]["price"],
        "mid_price": mid_price,
        "source": "mock",
    }
