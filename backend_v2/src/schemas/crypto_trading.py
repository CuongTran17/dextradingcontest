from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


CryptoSymbol = Literal[
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
]


class MarketOrderCreate(BaseModel):
    contest_id: str = Field(min_length=1, max_length=100)
    client_order_id: str = Field(min_length=1, max_length=64)
    symbol: CryptoSymbol
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0)


class PositionResponse(BaseModel):
    symbol: str
    quantity: float
    average_entry: float
    realized_pnl: float


class OrderResponse(BaseModel):
    order_id: int
    client_order_id: str
    symbol: str
    side: str
    status: str
    filled_quantity: float
    average_fill_price: float
    executed_notional: float
    fee: float
    created_at: str


class TradingAccountResponse(BaseModel):
    account_id: int
    contest_id: str
    status: str
    cash: float
    initial_equity: float
    equity: float
    realized_pnl: float
    unrealized_pnl: float
    positions: list[PositionResponse]
    orders: list[OrderResponse]
