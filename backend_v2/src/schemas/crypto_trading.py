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
    order_type: Literal["market", "limit"] = "market"
    limit_price: Decimal | None = Field(default=None, gt=0)
    stop_loss_price: Decimal | None = Field(default=None, gt=0)
    take_profit_price: Decimal | None = Field(default=None, gt=0)


class SolanaJoinConfirmRequest(BaseModel):
    wallet_address: str = Field(min_length=32, max_length=64)
    join_tx_signature: str = Field(min_length=32, max_length=128)


class ContestWalletResponse(BaseModel):
    contest_id: str
    wallet_address: str | None
    wallet_type: str | None
    join_tx_signature: str | None
    joined_onchain_at: str | None


class CertificateClaimStatusResponse(BaseModel):
    contest_id: str
    eligible: bool
    wallet_address: str | None = None
    rank: int | None = None
    recipient_name: str | None = None
    image_uri: str | None = None
    metadata_uri: str | None = None
    snapshot_hash: str | None = None
    proof: list[str] = Field(default_factory=list)
    mint_address: str | None = None
    mint_tx_signature: str | None = None
    claimed_at: str | None = None


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


class LeaderboardRowResponse(BaseModel):
    rank: int
    user: str
    equity: float
    pnl: float
    roi: float
    volume: float
    trade_count: int
    last_trade: str | None


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
    order_type: str = "market"
    status: str
    requested_quantity: float
    filled_quantity: float
    average_fill_price: float
    executed_notional: float
    fee: float
    limit_price: float | None = None
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    exit_trigger_type: str | None = None
    exit_triggered_at: str | None = None
    exit_order_id: int | None = None
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
