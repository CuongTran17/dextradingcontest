from datetime import datetime
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


class ContestResponse(BaseModel):
    id: str
    title: str
    status: Literal["practice", "upcoming", "active", "ended"]
    raw_status: str
    mode: Literal["practice", "contest"]
    initial_capital: float
    quote_asset: str
    symbols: list[CryptoSymbol]
    starts_at: str | None
    ends_at: str | None
    participant_count: int


class ContestCreate(BaseModel):
    slug: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    title: str = Field(min_length=3, max_length=255)
    mode: Literal["practice", "contest"] = "contest"
    status: Literal["draft", "scheduled", "active"] = "draft"
    initial_balance: Decimal = Field(gt=0)
    quote_asset: str = Field(default="USDT_TEST", max_length=16)
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    fee_rate: Decimal = Field(default=Decimal("0.001"), ge=0, le=Decimal("0.01"))
    symbols: list[CryptoSymbol] = Field(min_length=1, max_length=5)


class ContestUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=3, max_length=255)
    status: Literal[
        "draft",
        "scheduled",
        "active",
        "settling",
        "completed",
        "cancelled",
    ] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    symbols: list[CryptoSymbol] | None = Field(default=None, min_length=1, max_length=5)


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
