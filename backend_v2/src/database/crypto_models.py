from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.database.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CryptoAsset(Base):
    __tablename__ = "crypto_assets"
    __table_args__ = (
        UniqueConstraint(
            "exchange",
            "market_type",
            "symbol",
            name="uq_crypto_asset_market_symbol",
        ),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    exchange = Column(String(32), nullable=False, default="binance")
    market_type = Column(String(16), nullable=False, default="spot")
    symbol = Column(String(32), nullable=False, index=True)
    base_asset = Column(String(16), nullable=False)
    quote_asset = Column(String(16), nullable=False)
    price_precision = Column(Integer, nullable=False)
    quantity_precision = Column(Integer, nullable=False)
    min_quantity = Column(Numeric(36, 18), nullable=False)
    min_notional = Column(Numeric(36, 18), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class Contest(Base):
    __tablename__ = "contests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    mode = Column(
        Enum("practice", "contest", name="contest_mode_enum"),
        nullable=False,
    )
    status = Column(
        Enum(
            "draft",
            "scheduled",
            "active",
            "settling",
            "completed",
            "cancelled",
            name="contest_status_enum",
        ),
        nullable=False,
    )
    initial_balance = Column(Numeric(36, 18), nullable=False)
    quote_asset = Column(String(16), nullable=False, default="USDT_TEST")
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    fee_rate = Column(Numeric(12, 10), nullable=False, default=0.001)
    rules_json = Column(Text, nullable=False, default="{}")
    created_by = Column(
        Integer,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    assets = relationship("ContestAsset", cascade="all, delete-orphan")
    participants = relationship("ContestParticipant", cascade="all, delete-orphan")


class ContestAsset(Base):
    __tablename__ = "contest_assets"
    __table_args__ = (
        UniqueConstraint("contest_id", "asset_id", name="uq_contest_asset"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(
        BigInteger,
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        BigInteger,
        ForeignKey("crypto_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_enabled = Column(Boolean, nullable=False, default=True)

    asset = relationship("CryptoAsset")


class ContestParticipant(Base):
    __tablename__ = "contest_participants"
    __table_args__ = (
        UniqueConstraint("contest_id", "user_id", name="uq_contest_participant"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(
        BigInteger,
        ForeignKey("contests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(
            "active",
            "locked",
            "disqualified",
            "withdrawn",
            "completed",
            name="participant_status_enum",
        ),
        nullable=False,
        default="active",
    )
    joined_at = Column(DateTime, nullable=False, default=_utcnow)
    final_rank = Column(Integer, nullable=True)
    final_equity = Column(Numeric(36, 18), nullable=True)
    final_roi = Column(Numeric(18, 8), nullable=True)

    account = relationship(
        "TradingAccount",
        back_populates="participant",
        cascade="all, delete-orphan",
        uselist=False,
    )


class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_participant_id = Column(
        BigInteger,
        ForeignKey("contest_participants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status = Column(
        Enum("active", "frozen", "closed", name="trading_account_status_enum"),
        nullable=False,
        default="active",
    )
    initial_equity = Column(Numeric(36, 18), nullable=False)
    current_equity = Column(Numeric(36, 18), nullable=False)
    realized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    unrealized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=_utcnow)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    participant = relationship("ContestParticipant", back_populates="account")
    balances = relationship("AccountBalance", cascade="all, delete-orphan")
    positions = relationship("Position", cascade="all, delete-orphan")
    orders = relationship("TradingOrder", cascade="all, delete-orphan")


class AccountBalance(Base):
    __tablename__ = "account_balances"
    __table_args__ = (
        UniqueConstraint("account_id", "asset", name="uq_account_balance_asset"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(
        BigInteger,
        ForeignKey("trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset = Column(String(16), nullable=False)
    available = Column(Numeric(36, 18), nullable=False, default=0)
    locked = Column(Numeric(36, 18), nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class Position(Base):
    __tablename__ = "crypto_positions"
    __table_args__ = (
        UniqueConstraint("account_id", "asset_id", name="uq_position_account_asset"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(
        BigInteger,
        ForeignKey("trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        BigInteger,
        ForeignKey("crypto_assets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    quantity = Column(Numeric(36, 18), nullable=False, default=0)
    average_entry_price = Column(Numeric(36, 18), nullable=False, default=0)
    cost_basis = Column(Numeric(36, 18), nullable=False, default=0)
    realized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    asset = relationship("CryptoAsset")


class TradingOrder(Base):
    __tablename__ = "crypto_orders"
    __table_args__ = (
        UniqueConstraint("account_id", "client_order_id", name="uq_order_client_id"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_order_id = Column(String(64), nullable=False)
    account_id = Column(
        BigInteger,
        ForeignKey("trading_accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    asset_id = Column(
        BigInteger,
        ForeignKey("crypto_assets.id"),
        nullable=False,
        index=True,
    )
    side = Column(
        Enum("buy", "sell", name="crypto_order_side_enum"),
        nullable=False,
    )
    order_type = Column(String(16), nullable=False, default="market")
    status = Column(
        Enum(
            "pending",
            "filled",
            "rejected",
            "cancelled",
            name="crypto_order_status_enum",
        ),
        nullable=False,
    )
    requested_quantity = Column(Numeric(36, 18), nullable=False)
    filled_quantity = Column(Numeric(36, 18), nullable=False, default=0)
    average_fill_price = Column(Numeric(36, 18), nullable=True)
    estimated_notional = Column(Numeric(36, 18), nullable=False)
    executed_notional = Column(Numeric(36, 18), nullable=False, default=0)
    fee_amount = Column(Numeric(36, 18), nullable=False, default=0)
    fee_asset = Column(String(16), nullable=False)
    rejection_reason = Column(String(500), nullable=True)
    market_price_at_submission = Column(Numeric(36, 18), nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=_utcnow)
    completed_at = Column(DateTime, nullable=True)

    asset = relationship("CryptoAsset")
    fills = relationship("TradeFill", cascade="all, delete-orphan")


class TradeFill(Base):
    __tablename__ = "crypto_trade_fills"
    __table_args__ = (
        UniqueConstraint("order_id", "fill_sequence", name="uq_fill_sequence"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(
        BigInteger,
        ForeignKey("crypto_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fill_sequence = Column(Integer, nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    quantity = Column(Numeric(36, 18), nullable=False)
    notional = Column(Numeric(36, 18), nullable=False)
    fee_amount = Column(Numeric(36, 18), nullable=False)
    fee_asset = Column(String(16), nullable=False)
    liquidity_source = Column(
        String(32),
        nullable=False,
        default="simulated_orderbook",
    )
    executed_at = Column(DateTime, nullable=False, default=_utcnow)
