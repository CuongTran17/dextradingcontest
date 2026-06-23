from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

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
    return LATEST_PRICES


@router.post("/orders/market")
def create_market_order(payload: MarketOrderRequest) -> dict[str, Any]:
    try:
        portfolio = execute_market_order(
            payload.portfolio,
            payload.symbol,
            payload.side,
            payload.quantity,
            LATEST_PRICES[payload.symbol],
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "portfolio": portfolio,
        "metrics": portfolio_metrics(portfolio, LATEST_PRICES),
    }
