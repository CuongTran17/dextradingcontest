from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class CompanyOverviewCache(Base):
    __tablename__ = "company_overview_cache"

    symbol = Column(String(50), primary_key=True)
    payload_json = Column(LONGTEXT, nullable=False)
    source = Column(String(64), nullable=False, default="vnstock")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class FinancialReportCache(Base):
    __tablename__ = "financial_report_cache"
    __table_args__ = (
        UniqueConstraint("symbol", "report_type", name="uq_financial_report_cache_symbol_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(50), nullable=False, index=True)
    report_type = Column(String(20), nullable=False)
    row_count = Column(Integer, nullable=False, default=0)
    payload_json = Column(LONGTEXT, nullable=False)
    source = Column(String(64), nullable=False, default="vnstock")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class NewsCache(Base):
    __tablename__ = "news_cache"

    symbol = Column(String(50), primary_key=True)
    item_count = Column(Integer, nullable=False, default=0)
    payload_json = Column(LONGTEXT, nullable=False)
    source = Column(String(64), nullable=False, default="vnstock")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class EventsCache(Base):
    __tablename__ = "events_cache"

    symbol = Column(String(50), primary_key=True)
    item_count = Column(Integer, nullable=False, default=0)
    payload_json = Column(LONGTEXT, nullable=False)
    source = Column(String(64), nullable=False, default="vnstock")
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False, index=True)


# =====================================================================
# User & Premium Subscription Models
# =====================================================================


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=False)
    password_salt = Column(String(255), nullable=True)
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    fullname = Column(String(255), nullable=False)
    avatar_data = Column(LONGTEXT, nullable=True)
    role = Column(
        Enum("user", "premium", "admin", name="user_role_enum"),
        nullable=False,
        default="user",
        server_default="user",
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    is_locked = Column(Boolean, nullable=False, default=False, server_default="0")
    locked_reason = Column(String(500), nullable=True)
    last_login_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    subscriptions = relationship("UserSubscription", back_populates="user", lazy="dynamic")
    portfolios = relationship("UserPortfolio", back_populates="user", lazy="dynamic")


class UserSubscription(Base):
    """Tracks Premium subscription payments processed via Sepay."""
    __tablename__ = "user_subscriptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_name = Column(String(100), nullable=False, default="premium_monthly")
    original_amount = Column(Numeric(12, 2), nullable=True)
    discount_amount = Column(Numeric(12, 2), nullable=False, default=0)
    amount = Column(Numeric(12, 2), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="VND")
    status = Column(
        Enum("pending", "completed", "cancelled", "expired", name="subscription_status_enum"),
        nullable=False,
        default="pending",
        server_default="pending",
    )
    payment_method = Column(String(50), nullable=False, default="sepay")
    transaction_ref = Column(String(255), nullable=True, comment="Sepay transaction_id or transfer content")
    promo_code = Column(String(50), nullable=True)
    flash_sale_id = Column(Integer, ForeignKey("flash_sales.id", ondelete="SET NULL"), nullable=True)
    started_at = Column(DateTime, nullable=True, comment="When premium access was activated")
    expires_at = Column(DateTime, nullable=True, comment="When premium access expires")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="subscriptions")


class UserPortfolio(Base):
    """Stores a user's watchlist of stock symbols for Admin advisory."""
    __tablename__ = "user_portfolios"
    __table_args__ = (
        UniqueConstraint("user_id", "symbol", name="uq_user_portfolio_symbol"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=0, comment="Number of shares held")
    avg_price = Column(Float, nullable=True, comment="Average purchase price")
    tp_price = Column(Float, nullable=True, comment="Take-profit target price")
    sl_price = Column(Float, nullable=True, comment="Stop-loss target price")
    note = Column(Text, nullable=True, comment="User note for this holding")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    user = relationship("User", back_populates="portfolios")


class AIPrediction(Base):
    """Stores AI inference results from Trading-R1 model for history and backtesting."""
    __tablename__ = "ai_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    symbol = Column(String(50), nullable=False, index=True)
    prediction = Column(Enum("BUY", "SELL", "HOLD", name="prediction_action_enum"), nullable=False)
    confidence = Column(Float, nullable=True, comment="Model confidence score 0-1")
    reasoning = Column(Text, nullable=True, comment="AI reasoning / chain of thought")
    model_version = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class FlashSale(Base):
    """Global time-bound flash sale for Premium checkout."""
    __tablename__ = "flash_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    discount_percentage = Column(Float, nullable=False, default=0.0)
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)


class PromotionCode(Base):
    """Admin-managed promotion/discount codes for premium checkout campaigns."""
    __tablename__ = "promotion_codes"
    __table_args__ = (
        UniqueConstraint("code", name="uq_promotion_codes_code"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    discount_type = Column(
        Enum("percentage", "fixed", name="promotion_discount_type_enum"),
        nullable=False,
        default="percentage",
        server_default="percentage",
    )
    discount_value = Column(Float, nullable=False, default=0.0)
    min_order_amount = Column(Float, nullable=True)
    max_discount_amount = Column(Float, nullable=True)
    usage_limit = Column(Integer, nullable=True)
    used_count = Column(Integer, nullable=False, default=0, server_default="0")
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)
