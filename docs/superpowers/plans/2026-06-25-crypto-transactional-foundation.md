# Crypto Transactional Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace frontend-owned virtual portfolios with authenticated, contest-isolated MySQL accounts whose balances, positions, market orders, and fills persist across reloads and backend restarts.

**Architecture:** Keep public Binance market endpoints in `src/routes/crypto.py`, and add a separate authenticated trading router backed by focused repository and service modules. MySQL is authoritative for contest membership and account state; Phase 1 executes market orders from a fresh Binance REST order-book snapshot through an injectable liquidity provider so the later realtime cache can replace it without changing account logic.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MySQL, Pydantic, pytest, Vue 3, TypeScript, Vitest.

---

## Scope And File Map

This plan implements Phase 1 only. DuckDB history, one-year backfill, Binance WebSocket streams, Redis, and realtime leaderboard pushes are separate implementation plans.

Backend files:

- Create `backend_v2/src/database/crypto_models.py`: transactional crypto ORM models.
- Modify `backend_v2/src/database/models.py`: register crypto model metadata and user relationships.
- Create `backend_v2/alembic/versions/20260625_0003_crypto_trading_foundation.py`: deterministic schema migration and seed rows.
- Create `backend_v2/src/repositories/crypto_trading.py`: database queries and row-locking operations.
- Create `backend_v2/src/services/crypto_accounts.py`: contest join and account serialization.
- Create `backend_v2/src/services/crypto_execution.py`: pure fill calculation and transactional market-order orchestration.
- Create `backend_v2/src/schemas/crypto_trading.py`: request and response schemas.
- Create `backend_v2/src/routes/crypto_trading.py`: authenticated contest/account/order endpoints.
- Modify `backend_v2/src/routes/crypto.py`: expose all five configured Spot assets and remove portfolio-in-request execution.
- Modify `backend_v2/src/main.py`: register the trading router.
- Create focused backend tests under `backend_v2/tests/`.

Frontend files:

- Modify `src/types/crypto.ts`: add XRP/BNB and backend account response types.
- Modify `src/constants/cryptoAssets.ts`: configure five assets.
- Create `src/services/cryptoTradingApi.ts`: authenticated contest/account/order client.
- Modify `src/views/ContestDetail.vue`: join through backend.
- Modify `src/views/CryptoTrade.vue`: load and mutate backend account state.
- Modify `src/components/crypto/OrderTicket.vue`: submitting/disabled state.
- Modify `src/components/crypto/PortfolioSummary.vue`: render backend account data.
- Delete `src/stores/cryptoContestStore.ts` and its test after all consumers are removed.

## Task 1: Add Transactional Crypto ORM Models

**Files:**

- Create: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/database/models.py`
- Test: `backend_v2/tests/test_crypto_models.py`

- [ ] **Step 1: Write metadata tests for keys, precision, and relationships**

Create `backend_v2/tests/test_crypto_models.py`:

```python
from sqlalchemy import Numeric, UniqueConstraint

from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestAsset,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradeFill,
    TradingAccount,
    TradingOrder,
)


def unique_names(model) -> set[str]:
    return {
        item.name
        for item in model.__table__.constraints
        if isinstance(item, UniqueConstraint) and item.name
    }


def test_crypto_models_define_account_isolation_constraints():
    assert "uq_crypto_asset_market_symbol" in unique_names(CryptoAsset)
    assert "uq_contest_asset" in unique_names(ContestAsset)
    assert "uq_contest_participant" in unique_names(ContestParticipant)
    assert "uq_account_balance_asset" in unique_names(AccountBalance)
    assert "uq_position_account_asset" in unique_names(Position)
    assert "uq_order_client_id" in unique_names(TradingOrder)
    assert "uq_fill_sequence" in unique_names(TradeFill)
    assert TradingAccount.__table__.c.contest_participant_id.unique is True


def test_money_columns_use_fixed_precision():
    columns = [
        Contest.__table__.c.initial_balance,
        AccountBalance.__table__.c.available,
        Position.__table__.c.quantity,
        Position.__table__.c.average_entry_price,
        TradingOrder.__table__.c.executed_notional,
        TradeFill.__table__.c.price,
    ]
    assert all(isinstance(column.type, Numeric) for column in columns)
```

- [ ] **Step 2: Run the tests and confirm missing models**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_models.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'src.database.crypto_models'`.

- [ ] **Step 3: Implement focused ORM models**

Create `backend_v2/src/database/crypto_models.py` with:

```python
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

from src.database.models import Base


def utcnow():
    return datetime.now(timezone.utc)


class CryptoAsset(Base):
    __tablename__ = "crypto_assets"
    __table_args__ = (
        UniqueConstraint("exchange", "market_type", "symbol", name="uq_crypto_asset_market_symbol"),
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
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Contest(Base):
    __tablename__ = "contests"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    slug = Column(String(100), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    mode = Column(Enum("practice", "contest", name="contest_mode_enum"), nullable=False)
    status = Column(
        Enum("draft", "scheduled", "active", "settling", "completed", "cancelled", name="contest_status_enum"),
        nullable=False,
    )
    initial_balance = Column(Numeric(36, 18), nullable=False)
    quote_asset = Column(String(16), nullable=False, default="USDT_TEST")
    starts_at = Column(DateTime, nullable=True)
    ends_at = Column(DateTime, nullable=True)
    fee_rate = Column(Numeric(12, 10), nullable=False, default=0.001)
    rules_json = Column(Text, nullable=False, default="{}")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class ContestAsset(Base):
    __tablename__ = "contest_assets"
    __table_args__ = (UniqueConstraint("contest_id", "asset_id", name="uq_contest_asset"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(BigInteger, ForeignKey("crypto_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    is_enabled = Column(Boolean, nullable=False, default=True)


class ContestParticipant(Base):
    __tablename__ = "contest_participants"
    __table_args__ = (UniqueConstraint("contest_id", "user_id", name="uq_contest_participant"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_id = Column(BigInteger, ForeignKey("contests.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(
        Enum("active", "disqualified", "withdrawn", "completed", name="participant_status_enum"),
        nullable=False,
        default="active",
    )
    joined_at = Column(DateTime, nullable=False, default=utcnow)
    final_rank = Column(Integer, nullable=True)
    final_equity = Column(Numeric(36, 18), nullable=True)
    final_roi = Column(Numeric(18, 8), nullable=True)


class TradingAccount(Base):
    __tablename__ = "trading_accounts"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    contest_participant_id = Column(
        BigInteger,
        ForeignKey("contest_participants.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    status = Column(Enum("active", "frozen", "closed", name="trading_account_status_enum"), nullable=False)
    initial_equity = Column(Numeric(36, 18), nullable=False)
    current_equity = Column(Numeric(36, 18), nullable=False)
    realized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    unrealized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime, nullable=False, default=utcnow)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    balances = relationship("AccountBalance", cascade="all, delete-orphan")
    positions = relationship("Position", cascade="all, delete-orphan")
    orders = relationship("TradingOrder", cascade="all, delete-orphan")


class AccountBalance(Base):
    __tablename__ = "account_balances"
    __table_args__ = (UniqueConstraint("account_id", "asset", name="uq_account_balance_asset"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(BigInteger, ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset = Column(String(16), nullable=False)
    available = Column(Numeric(36, 18), nullable=False, default=0)
    locked = Column(Numeric(36, 18), nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)


class Position(Base):
    __tablename__ = "crypto_positions"
    __table_args__ = (UniqueConstraint("account_id", "asset_id", name="uq_position_account_asset"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    account_id = Column(BigInteger, ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(BigInteger, ForeignKey("crypto_assets.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Numeric(36, 18), nullable=False, default=0)
    average_entry_price = Column(Numeric(36, 18), nullable=False, default=0)
    cost_basis = Column(Numeric(36, 18), nullable=False, default=0)
    realized_pnl = Column(Numeric(36, 18), nullable=False, default=0)
    updated_at = Column(DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    asset = relationship("CryptoAsset")


class TradingOrder(Base):
    __tablename__ = "crypto_orders"
    __table_args__ = (UniqueConstraint("account_id", "client_order_id", name="uq_order_client_id"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_order_id = Column(String(64), nullable=False)
    account_id = Column(BigInteger, ForeignKey("trading_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(BigInteger, ForeignKey("crypto_assets.id"), nullable=False, index=True)
    side = Column(Enum("buy", "sell", name="crypto_order_side_enum"), nullable=False)
    order_type = Column(String(16), nullable=False, default="market")
    status = Column(Enum("pending", "filled", "rejected", "cancelled", name="crypto_order_status_enum"), nullable=False)
    requested_quantity = Column(Numeric(36, 18), nullable=False)
    filled_quantity = Column(Numeric(36, 18), nullable=False, default=0)
    average_fill_price = Column(Numeric(36, 18), nullable=True)
    estimated_notional = Column(Numeric(36, 18), nullable=False)
    executed_notional = Column(Numeric(36, 18), nullable=False, default=0)
    fee_amount = Column(Numeric(36, 18), nullable=False, default=0)
    fee_asset = Column(String(16), nullable=False)
    rejection_reason = Column(String(500), nullable=True)
    market_price_at_submission = Column(Numeric(36, 18), nullable=False)
    submitted_at = Column(DateTime, nullable=False, default=utcnow)
    completed_at = Column(DateTime, nullable=True)
    asset = relationship("CryptoAsset")
    fills = relationship("TradeFill", cascade="all, delete-orphan")


class TradeFill(Base):
    __tablename__ = "crypto_trade_fills"
    __table_args__ = (UniqueConstraint("order_id", "fill_sequence", name="uq_fill_sequence"),)

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey("crypto_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    fill_sequence = Column(Integer, nullable=False)
    price = Column(Numeric(36, 18), nullable=False)
    quantity = Column(Numeric(36, 18), nullable=False)
    notional = Column(Numeric(36, 18), nullable=False)
    fee_amount = Column(Numeric(36, 18), nullable=False)
    fee_asset = Column(String(16), nullable=False)
    liquidity_source = Column(String(32), nullable=False, default="simulated_orderbook")
    executed_at = Column(DateTime, nullable=False, default=utcnow)
```

At the end of `backend_v2/src/database/models.py`, register the model module without re-exporting every class:

```python
from src.database import crypto_models as _crypto_models  # noqa: E402,F401
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_models.py -q
```

Expected: `2 passed`.

- [ ] **Step 5: Commit the model layer**

```powershell
git add backend_v2/src/database/models.py backend_v2/src/database/crypto_models.py backend_v2/tests/test_crypto_models.py
git commit -m "feat: add crypto trading models"
```

## Task 2: Create Alembic Migration And Initial Market Seed

**Files:**

- Create: `backend_v2/alembic/versions/20260625_0003_crypto_trading_foundation.py`
- Test: `backend_v2/tests/test_crypto_migration.py`

- [ ] **Step 1: Write a migration contract test**

Create `backend_v2/tests/test_crypto_migration.py`:

```python
import importlib.util
from pathlib import Path


MIGRATION = Path(__file__).parents[1] / "alembic" / "versions" / "20260625_0003_crypto_trading_foundation.py"


def load_migration():
    spec = importlib.util.spec_from_file_location("crypto_migration", MIGRATION)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_crypto_migration_has_expected_revision_and_seed_symbols():
    migration = load_migration()
    assert migration.revision == "20260625_0003"
    assert migration.down_revision == "20260516_0002"
    assert migration.SPOT_SYMBOLS == ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
```

- [ ] **Step 2: Run the migration test and confirm the file is missing**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_migration.py -q
```

Expected: failure because the migration file does not exist.

- [ ] **Step 3: Implement the migration**

Create `backend_v2/alembic/versions/20260625_0003_crypto_trading_foundation.py`.

Required constants:

```python
revision = "20260625_0003"
down_revision = "20260516_0002"
branch_labels = None
depends_on = None

SPOT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
```

`upgrade()` must:

1. Create all nine tables from Task 1 with named foreign keys and unique constraints.
2. Insert five `crypto_assets` rows using Binance precision defaults:

```python
ASSET_ROWS = [
    ("BTCUSDT", "BTC", 2, 6, "0.000001", "5"),
    ("ETHUSDT", "ETH", 2, 5, "0.00001", "5"),
    ("SOLUSDT", "SOL", 2, 3, "0.001", "5"),
    ("XRPUSDT", "XRP", 4, 1, "0.1", "5"),
    ("BNBUSDT", "BNB", 2, 3, "0.001", "5"),
]
```

3. Insert one active practice contest:

```python
{
    "slug": "practice-arena",
    "title": "Practice Arena",
    "mode": "practice",
    "status": "active",
    "initial_balance": "10000",
    "quote_asset": "USDT_TEST",
    "fee_rate": "0.001",
    "rules_json": '{"long_only":true,"market_orders":true}',
}
```

4. Insert all five contest-asset links with `INSERT ... SELECT`.

`downgrade()` must drop tables in reverse dependency order and leave the existing `users` table intact.

- [ ] **Step 4: Run migration contract tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_migration.py backend_v2\tests\test_crypto_models.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Verify the migration against a configured MySQL database**

Run only when `MYSQL_URL` points to the intended development database:

```powershell
Set-Location backend_v2
..\.venv\Scripts\python.exe -m alembic upgrade head
..\.venv\Scripts\python.exe -m alembic current
Set-Location ..
```

Expected current revision: `20260625_0003 (head)`.

- [ ] **Step 6: Commit migration**

```powershell
git add backend_v2/alembic/versions/20260625_0003_crypto_trading_foundation.py backend_v2/tests/test_crypto_migration.py
git commit -m "feat: migrate crypto trading schema"
```

## Task 3: Add Contest Join And Account Service

**Files:**

- Create: `backend_v2/src/repositories/crypto_trading.py`
- Create: `backend_v2/src/services/crypto_accounts.py`
- Test: `backend_v2/tests/test_crypto_accounts.py`

- [ ] **Step 1: Write service tests with a repository fake**

Create `backend_v2/tests/test_crypto_accounts.py`:

```python
from decimal import Decimal
from types import SimpleNamespace

from src.services.crypto_accounts import CryptoAccountService


class FakeRepository:
    def __init__(self):
        self.participant = None
        self.account = None

    def get_active_contest(self, slug):
        return SimpleNamespace(id=1, slug=slug, title="Practice Arena", initial_balance=Decimal("10000"), quote_asset="USDT_TEST")

    def get_participant(self, contest_id, user_id):
        return self.participant

    def create_participant(self, contest_id, user_id):
        self.participant = SimpleNamespace(id=7, contest_id=contest_id, user_id=user_id, status="active")
        return self.participant

    def get_account_for_participant(self, participant_id):
        return self.account

    def create_account(self, participant_id, initial_balance, quote_asset):
        self.account = SimpleNamespace(
            id=9,
            contest_participant_id=participant_id,
            status="active",
            initial_equity=initial_balance,
            current_equity=initial_balance,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            balances=[SimpleNamespace(asset=quote_asset, available=initial_balance, locked=Decimal("0"))],
            positions=[],
            orders=[],
        )
        return self.account


def test_join_contest_creates_one_isolated_account_and_is_idempotent():
    repo = FakeRepository()
    service = CryptoAccountService(repo)

    first = service.join_contest(user_id=3, contest_slug="practice-arena")
    second = service.join_contest(user_id=3, contest_slug="practice-arena")

    assert first["account_id"] == second["account_id"] == 9
    assert first["cash"] == 10000.0
    assert first["positions"] == []
```

- [ ] **Step 2: Run the test and confirm missing service**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_accounts.py -q
```

Expected: import failure for `CryptoAccountService`.

- [ ] **Step 3: Implement repository operations**

Create `backend_v2/src/repositories/crypto_trading.py` with a `CryptoTradingRepository` that accepts a SQLAlchemy `Session` and implements:

```python
class CryptoTradingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_contest(self, slug: str) -> Contest | None:
        return self.db.query(Contest).filter(
            Contest.slug == slug,
            Contest.status.in_(("active", "scheduled")),
        ).first()

    def get_participant(self, contest_id: int, user_id: int) -> ContestParticipant | None:
        return self.db.query(ContestParticipant).filter_by(
            contest_id=contest_id,
            user_id=user_id,
        ).first()

    def create_participant(self, contest_id: int, user_id: int) -> ContestParticipant:
        participant = ContestParticipant(contest_id=contest_id, user_id=user_id, status="active")
        self.db.add(participant)
        self.db.flush()
        return participant

    def get_account_for_participant(self, participant_id: int) -> TradingAccount | None:
        return self.db.query(TradingAccount).filter_by(
            contest_participant_id=participant_id,
        ).first()

    def create_account(self, participant_id: int, initial_balance: Decimal, quote_asset: str) -> TradingAccount:
        account = TradingAccount(
            contest_participant_id=participant_id,
            status="active",
            initial_equity=initial_balance,
            current_equity=initial_balance,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
        self.db.add(account)
        self.db.flush()
        self.db.add(AccountBalance(
            account_id=account.id,
            asset=quote_asset,
            available=initial_balance,
            locked=Decimal("0"),
        ))
        self.db.flush()
        self.db.refresh(account)
        return account
```

Also implement `list_contest_assets(contest_id)`, `get_account_for_user(contest_slug, user_id)`, and `commit()` using explicit joins through `ContestParticipant`.

- [ ] **Step 4: Implement account orchestration and serialization**

Create `backend_v2/src/services/crypto_accounts.py`:

```python
class ContestNotFoundError(ValueError):
    pass


class AccountNotFoundError(ValueError):
    pass


class CryptoAccountService:
    def __init__(self, repo):
        self.repo = repo

    def join_contest(self, user_id: int, contest_slug: str) -> dict:
        contest = self.repo.get_active_contest(contest_slug)
        if contest is None:
            raise ContestNotFoundError("Contest is not available")

        participant = self.repo.get_participant(contest.id, user_id)
        if participant is None:
            participant = self.repo.create_participant(contest.id, user_id)

        account = self.repo.get_account_for_participant(participant.id)
        if account is None:
            account = self.repo.create_account(
                participant.id,
                Decimal(contest.initial_balance),
                contest.quote_asset,
            )

        self.repo.commit()
        return serialize_account(account, contest.slug)
```

`serialize_account()` must return stable snake_case API fields:

```python
{
    "account_id": account.id,
    "contest_id": contest_slug,
    "status": account.status,
    "cash": float(quote_balance.available),
    "initial_equity": float(account.initial_equity),
    "equity": float(account.current_equity),
    "realized_pnl": float(account.realized_pnl),
    "unrealized_pnl": float(account.unrealized_pnl),
    "positions": [
        {
            "symbol": position.asset.symbol,
            "quantity": float(position.quantity),
            "average_entry": float(position.average_entry_price),
            "realized_pnl": float(position.realized_pnl),
        }
        for position in account.positions
        if position.quantity > 0
    ],
    "orders": [serialize_order(order) for order in sorted(
        account.orders,
        key=lambda item: item.submitted_at,
        reverse=True,
    )[:50]],
}
```

- [ ] **Step 5: Run account tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_accounts.py -q
```

Expected: `1 passed`.

- [ ] **Step 6: Commit account foundation**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/services/crypto_accounts.py backend_v2/tests/test_crypto_accounts.py
git commit -m "feat: add persistent contest accounts"
```

## Task 4: Implement Order-Book Fill Calculation

**Files:**

- Create: `backend_v2/src/services/crypto_execution.py`
- Test: `backend_v2/tests/test_crypto_execution.py`

- [ ] **Step 1: Write pure fill-calculation tests**

Create `backend_v2/tests/test_crypto_execution.py`:

```python
from decimal import Decimal

import pytest

from src.services.crypto_execution import InsufficientDepthError, calculate_market_fill


BOOK = {
    "bids": [
        {"price": 99.0, "quantity": 2.0},
        {"price": 98.0, "quantity": 3.0},
    ],
    "asks": [
        {"price": 101.0, "quantity": 1.0},
        {"price": 102.0, "quantity": 2.0},
    ],
}


def test_buy_walks_asks_and_returns_weighted_average():
    fill = calculate_market_fill("buy", Decimal("2"), BOOK, Decimal("0.001"))
    assert fill.quantity == Decimal("2")
    assert fill.notional == Decimal("203")
    assert fill.average_price == Decimal("101.5")
    assert fill.fee == Decimal("0.203")
    assert [item.price for item in fill.levels] == [Decimal("101"), Decimal("102")]


def test_sell_walks_bids():
    fill = calculate_market_fill("sell", Decimal("3"), BOOK, Decimal("0.001"))
    assert fill.notional == Decimal("296")
    assert fill.average_price == Decimal("98.66666666666666666666666667")


def test_insufficient_depth_rejects_whole_order():
    with pytest.raises(InsufficientDepthError):
        calculate_market_fill("buy", Decimal("4"), BOOK, Decimal("0.001"))
```

- [ ] **Step 2: Run tests and confirm missing implementation**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_execution.py -q
```

Expected: import failure.

- [ ] **Step 3: Implement immutable fill value objects and calculation**

Create `backend_v2/src/services/crypto_execution.py`:

```python
from dataclasses import dataclass
from decimal import Decimal


class InsufficientDepthError(ValueError):
    pass


@dataclass(frozen=True)
class FillLevel:
    price: Decimal
    quantity: Decimal
    notional: Decimal


@dataclass(frozen=True)
class MarketFill:
    quantity: Decimal
    notional: Decimal
    average_price: Decimal
    fee: Decimal
    levels: tuple[FillLevel, ...]


def calculate_market_fill(side: str, quantity: Decimal, book: dict, fee_rate: Decimal) -> MarketFill:
    rows = book["asks"] if side == "buy" else book["bids"]
    remaining = quantity
    levels = []
    for row in rows:
        if remaining <= 0:
            break
        price = Decimal(str(row["price"]))
        available = Decimal(str(row["quantity"]))
        taken = min(remaining, available)
        levels.append(FillLevel(price=price, quantity=taken, notional=price * taken))
        remaining -= taken
    if remaining > 0:
        raise InsufficientDepthError("Insufficient order book depth")
    notional = sum((level.notional for level in levels), Decimal("0"))
    return MarketFill(
        quantity=quantity,
        notional=notional,
        average_price=notional / quantity,
        fee=notional * fee_rate,
        levels=tuple(levels),
    )
```

- [ ] **Step 4: Run fill tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_execution.py -q
```

Expected: `3 passed`.

- [ ] **Step 5: Commit pure execution logic**

```powershell
git add backend_v2/src/services/crypto_execution.py backend_v2/tests/test_crypto_execution.py
git commit -m "feat: calculate crypto order book fills"
```

## Task 5: Add Transactional Market Order Orchestration

**Files:**

- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/services/crypto_execution.py`
- Test: `backend_v2/tests/test_crypto_order_service.py`
- Test: `backend_v2/tests/integration/test_crypto_mysql.py`

- [ ] **Step 1: Write order-service tests using repository and liquidity fakes**

Create `backend_v2/tests/test_crypto_order_service.py` covering:

```python
def test_buy_debits_cash_creates_position_order_and_fills():
    result = service.place_market_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="web-001",
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
    )
    assert result["status"] == "filled"
    assert result["filled_quantity"] == 0.02
    assert repo.balance.available == Decimal("7977.98")
    assert repo.position.quantity == Decimal("0.02")
    assert len(repo.saved_fills) == 2


def test_duplicate_client_order_id_returns_existing_order_without_second_debit():
    arguments = {
        "user_id": 3,
        "contest_slug": "practice-arena",
        "symbol": "BTCUSDT",
        "side": "buy",
        "quantity": Decimal("0.02"),
    }
    first = service.place_market_order(**arguments, client_order_id="web-001")
    second = service.place_market_order(**arguments, client_order_id="web-001")
    assert second["order_id"] == first["order_id"]
    assert repo.debit_count == 1


def test_sell_rejects_when_position_is_too_small():
    with pytest.raises(InsufficientPositionError):
        service.place_market_order(
            user_id=3,
            contest_slug="practice-arena",
            client_order_id="web-002",
            symbol="BTCUSDT",
            side="sell",
            quantity=Decimal("1"),
        )
```

Use an order book with two asks at `100000` and `101000`; configure `fee_rate=0.001`, so buying `0.02` costs `2020 + 2.02 = 2022.02`. Set the expected balance to `7977.98`, not a rounded float.

- [ ] **Step 2: Run tests and confirm orchestration is absent**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_order_service.py -q
```

Expected: failure because `CryptoOrderService` is not defined.

- [ ] **Step 3: Add repository row-locking methods**

Add these methods to `CryptoTradingRepository`:

```python
def lock_account_for_user(self, contest_slug: str, user_id: int) -> TradingAccount | None:
    return (
        self.db.query(TradingAccount)
        .join(ContestParticipant)
        .join(Contest)
        .filter(Contest.slug == contest_slug, ContestParticipant.user_id == user_id)
        .with_for_update()
        .first()
    )

def lock_balance(self, account_id: int, asset: str) -> AccountBalance | None:
    return self.db.query(AccountBalance).filter_by(
        account_id=account_id,
        asset=asset,
    ).with_for_update().first()

def lock_position(self, account_id: int, asset_id: int) -> Position | None:
    return self.db.query(Position).filter_by(
        account_id=account_id,
        asset_id=asset_id,
    ).with_for_update().first()
```

Also add `get_enabled_asset()`, `get_order_by_client_id()`, `add_order()`, `add_position()`, `add_fill()`, `flush()`, `commit()`, and `rollback()`.

- [ ] **Step 4: Implement `CryptoOrderService`**

Add to `crypto_execution.py`:

```python
class CryptoOrderService:
    def __init__(self, repo, liquidity_provider):
        self.repo = repo
        self.liquidity_provider = liquidity_provider

    def place_market_order(self, *, user_id, contest_slug, client_order_id, symbol, side, quantity):
        existing = self.repo.get_order_by_client_id(user_id, contest_slug, client_order_id)
        if existing is not None:
            return serialize_order(existing)

        try:
            account = self.repo.lock_account_for_user(contest_slug, user_id)
            if account is None or account.status != "active":
                raise AccountUnavailableError("Trading account is not active")

            asset, contest = self.repo.get_enabled_asset(contest_slug, symbol)
            book = self.liquidity_provider.get_order_book(symbol, 100)
            fill = calculate_market_fill(side, quantity, book, Decimal(contest.fee_rate))
            cash = self.repo.lock_balance(account.id, contest.quote_asset)
            position = self.repo.lock_position(account.id, asset.id)

            if side == "buy":
                apply_buy(account, cash, position, asset, fill, self.repo)
            else:
                apply_sell(account, cash, position, fill)

            order = persist_order_and_fills(
                repo=self.repo,
                account=account,
                asset=asset,
                contest=contest,
                client_order_id=client_order_id,
                side=side,
                fill=fill,
                market_price=Decimal(str(book["mid_price"])),
            )
            self.repo.commit()
            return serialize_order(order)
        except Exception:
            self.repo.rollback()
            raise
```

Rules:

- Buy debit is `fill.notional + fill.fee`.
- Sell credit is `fill.notional - fill.fee`.
- Buy average entry is `(old_cost_basis + fill.notional + fill.fee) / new_quantity`.
- Sell realized PnL is `sell_notional - fee - average_entry_price * sold_quantity`.
- Zero positions remain as zero rows only until transaction completion, then are deleted.
- `current_equity` is updated from cash plus positions valued at fill price in Phase 1.
- Persist one `TradeFill` per consumed depth level.

- [ ] **Step 5: Add optional MySQL concurrency integration test**

Create `backend_v2/tests/integration/test_crypto_mysql.py` and skip when `TEST_MYSQL_URL` is absent:

```python
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.repositories.crypto_trading import CryptoTradingRepository
from src.services.crypto_execution import CryptoOrderService, InsufficientBalanceError

TEST_MYSQL_URL = os.getenv("TEST_MYSQL_URL")
pytestmark = pytest.mark.skipif(not TEST_MYSQL_URL, reason="TEST_MYSQL_URL is not configured")


class FixedLiquidity:
    def get_order_book(self, symbol, limit):
        return {
            "symbol": symbol,
            "mid_price": 80,
            "bids": [{"price": 79, "quantity": 10}],
            "asks": [{"price": 80, "quantity": 10}],
        }


def test_two_concurrent_buys_cannot_overdraw_balance(seeded_crypto_account):
    engine = create_engine(TEST_MYSQL_URL, pool_pre_ping=True)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def buy(client_order_id):
        with sessions() as db:
            service = CryptoOrderService(CryptoTradingRepository(db), FixedLiquidity())
            try:
                service.place_market_order(
                    user_id=seeded_crypto_account.user_id,
                    contest_slug="practice-arena",
                    client_order_id=client_order_id,
                    symbol="BTCUSDT",
                    side="buy",
                    quantity=Decimal("1"),
                )
                return "filled"
            except InsufficientBalanceError:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(buy, ["concurrent-1", "concurrent-2"]))

    with sessions() as db:
        balance = CryptoTradingRepository(db).lock_balance(
            seeded_crypto_account.account_id,
            "USDT_TEST",
        )
        assert sorted(results) == ["filled", "rejected"]
        assert balance.available >= 0
```

In the same file, implement `seeded_crypto_account` as a pytest fixture that truncates only the crypto test rows, inserts one user, the five seeded assets, `practice-arena`, one participant, one account, and an `AccountBalance(available=Decimal("100"))`. Return a `SimpleNamespace(user_id=user.id, account_id=account.id)`. Use a transaction for setup and explicit row deletion during fixture teardown.

- [ ] **Step 6: Run unit order tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_execution.py backend_v2\tests\test_crypto_order_service.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Run MySQL integration test when configured**

Run:

```powershell
$env:TEST_MYSQL_URL=$env:MYSQL_URL
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\integration\test_crypto_mysql.py -q
```

Expected: concurrency test passes; final balance is never negative.

- [ ] **Step 8: Commit transaction orchestration**

```powershell
git add backend_v2/src/repositories/crypto_trading.py backend_v2/src/services/crypto_execution.py backend_v2/tests/test_crypto_order_service.py backend_v2/tests/integration/test_crypto_mysql.py
git commit -m "feat: persist transactional market orders"
```

## Task 6: Expose Authenticated Trading APIs

**Files:**

- Create: `backend_v2/src/schemas/__init__.py`
- Create: `backend_v2/src/schemas/crypto_trading.py`
- Create: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/routes/crypto.py`
- Modify: `backend_v2/src/main.py`
- Test: `backend_v2/tests/test_crypto_trading_routes.py`
- Modify: `backend_v2/tests/test_crypto_routes.py`

- [ ] **Step 1: Write route tests with dependency overrides**

Create route tests that override `require_auth`, `get_db`, `get_account_service`, and `get_order_service`.

Required cases:

```python
def test_join_contest_requires_auth():
    response = client.post("/api/crypto/contests/practice-arena/join")
    assert response.status_code == 401


def test_join_contest_returns_persistent_account(authenticated_client):
    response = authenticated_client.post("/api/crypto/contests/practice-arena/join")
    assert response.status_code == 200
    assert response.json()["contest_id"] == "practice-arena"
    assert response.json()["cash"] == 10000.0


def test_market_order_body_does_not_accept_client_portfolio(authenticated_client):
    response = authenticated_client.post(
        "/api/crypto/orders/market",
        json={
            "contest_id": "practice-arena",
            "client_order_id": "web-001",
            "symbol": "ETHUSDT",
            "side": "buy",
            "quantity": 1,
            "portfolio": {"cash": 999999},
        },
    )
    assert response.status_code == 200
    assert "portfolio" not in captured_service_arguments
```

- [ ] **Step 2: Run route tests and confirm endpoints are absent**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_trading_routes.py -q
```

Expected: endpoint or import failures.

- [ ] **Step 3: Add Pydantic schemas**

Create `backend_v2/src/schemas/crypto_trading.py`:

```python
class MarketOrderCreate(BaseModel):
    contest_id: str = Field(min_length=1, max_length=100)
    client_order_id: str = Field(min_length=1, max_length=64)
    symbol: Literal["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
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
```

- [ ] **Step 4: Add service dependency factories and routes**

Create `backend_v2/src/routes/crypto_trading.py` with:

```python
router = APIRouter(prefix="/api/crypto", tags=["crypto-trading"])


def get_account_service(db: Session = Depends(get_db)):
    return CryptoAccountService(CryptoTradingRepository(db))


def get_order_service(db: Session = Depends(get_db)):
    return CryptoOrderService(
        CryptoTradingRepository(db),
        BinanceRestLiquidityProvider(),
    )


@router.post("/contests/{contest_id}/join", response_model=TradingAccountResponse)
def join_contest(
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: CryptoAccountService = Depends(get_account_service),
):
    return service.join_contest(current_user.id, contest_id)


@router.get("/accounts/{contest_id}", response_model=TradingAccountResponse)
def get_account(
    contest_id: str,
    current_user: User = Depends(require_auth),
    service: CryptoAccountService = Depends(get_account_service),
):
    return service.get_account(current_user.id, contest_id)


@router.post("/orders/market", response_model=OrderResponse)
def place_market_order(
    body: MarketOrderCreate,
    current_user: User = Depends(require_auth),
    service: CryptoOrderService = Depends(get_order_service),
):
    return service.place_market_order(
        user_id=current_user.id,
        contest_slug=body.contest_id,
        client_order_id=body.client_order_id,
        symbol=body.symbol,
        side=body.side,
        quantity=body.quantity,
    )
```

Map domain exceptions to `404`, `409`, or `422`; do not return raw SQL errors.

Add a small `BinanceRestLiquidityProvider` adapter that calls the existing `get_binance_order_book`.

- [ ] **Step 5: Register router and simplify public route**

In `backend_v2/src/main.py`, include `crypto_trading_router`.

In `backend_v2/src/routes/crypto.py`:

- Expand assets and symbol literals to XRPUSDT and BNBUSDT.
- Remove `MarketOrderRequest`, `create_market_order()`, and imports from `crypto_simulator`.
- Keep market data fallback behavior unchanged for this phase.

- [ ] **Step 6: Run backend crypto tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_models.py backend_v2\tests\test_crypto_migration.py backend_v2\tests\test_crypto_accounts.py backend_v2\tests\test_crypto_execution.py backend_v2\tests\test_crypto_order_service.py backend_v2\tests\test_crypto_routes.py backend_v2\tests\test_crypto_trading_routes.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 7: Commit API layer**

```powershell
git add backend_v2/src/schemas backend_v2/src/routes/crypto.py backend_v2/src/routes/crypto_trading.py backend_v2/src/main.py backend_v2/tests/test_crypto_routes.py backend_v2/tests/test_crypto_trading_routes.py
git commit -m "feat: expose authenticated crypto trading api"
```

## Task 7: Add Frontend Trading API And Five-Asset Types

**Files:**

- Modify: `src/types/crypto.ts`
- Modify: `src/constants/cryptoAssets.ts`
- Create: `src/services/cryptoTradingApi.ts`
- Create: `src/services/__tests__/cryptoTradingApi.test.ts`

- [ ] **Step 1: Write frontend API tests**

Create tests that mock `backendFetch` and token storage:

```typescript
it('joins a contest with the bearer token', async () => {
  localStorage.setItem('crypto_contest_token', 'token-123')
  vi.mocked(backendFetch).mockResolvedValue(accountFixture)

  await joinCryptoContest('practice-arena')

  expect(backendFetch).toHaveBeenCalledWith(
    expect.any(String),
    '/api/crypto/contests/practice-arena/join',
    expect.objectContaining({
      method: 'POST',
      headers: { Authorization: 'Bearer token-123' },
    }),
  )
})

it('sends an idempotency key but never sends a portfolio', async () => {
  await placeCryptoMarketOrder({
    contestId: 'practice-arena',
    clientOrderId: 'web-001',
    symbol: 'BTCUSDT',
    side: 'buy',
    quantity: 0.01,
  })
  const body = JSON.parse(vi.mocked(backendFetch).mock.calls[0][2]?.body as string)
  expect(body.client_order_id).toBe('web-001')
  expect(body.portfolio).toBeUndefined()
})
```

- [ ] **Step 2: Run tests and confirm service is absent**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts
```

Expected: import failure.

- [ ] **Step 3: Expand domain types**

Update:

```typescript
export type CryptoSymbol = 'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT' | 'XRPUSDT' | 'BNBUSDT'
```

Add:

```typescript
export interface TradingAccount {
  accountId: number
  contestId: string
  status: 'active' | 'frozen' | 'closed'
  cash: number
  initialEquity: number
  equity: number
  realizedPnl: number
  unrealizedPnl: number
  positions: Position[]
  orders: SimulatedOrder[]
}
```

Update `CryptoAsset.baseAsset` for XRP and BNB.

- [ ] **Step 4: Configure five frontend assets**

Add these entries to `src/constants/cryptoAssets.ts`:

```typescript
{
  symbol: 'XRPUSDT',
  baseAsset: 'XRP',
  quoteAsset: 'USDT_TEST',
  displayName: 'XRP / USDT_TEST',
  pricePrecision: 4,
  quantityPrecision: 1,
},
{
  symbol: 'BNBUSDT',
  baseAsset: 'BNB',
  quoteAsset: 'USDT_TEST',
  displayName: 'BNB / USDT_TEST',
  pricePrecision: 2,
  quantityPrecision: 3,
},
```

- [ ] **Step 5: Implement authenticated crypto API client**

Create `src/services/cryptoTradingApi.ts` with:

```typescript
async function cryptoAuthFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  if (!token) throw new Error('Please sign in to trade')
  return backendFetch<T>(BACKEND_URL, path, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  })
}

export function joinCryptoContest(contestId: string): Promise<TradingAccount> {
  return cryptoAuthFetch(`/api/crypto/contests/${encodeURIComponent(contestId)}/join`, {
    method: 'POST',
  }).then(mapAccount)
}

export function getCryptoAccount(contestId: string): Promise<TradingAccount> {
  return cryptoAuthFetch(`/api/crypto/accounts/${encodeURIComponent(contestId)}`).then(mapAccount)
}

export function placeCryptoMarketOrder(input: MarketOrderInput): Promise<SimulatedOrder> {
  return cryptoAuthFetch('/api/crypto/orders/market', {
    method: 'POST',
    body: JSON.stringify({
      contest_id: input.contestId,
      client_order_id: input.clientOrderId,
      symbol: input.symbol,
      side: input.side,
      quantity: input.quantity,
    }),
  }).then(mapOrder)
}
```

Use explicit `mapAccount()` and `mapOrder()` functions to convert backend snake_case to frontend camelCase.

- [ ] **Step 6: Run service tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts
```

Expected: tests pass.

- [ ] **Step 7: Commit frontend API**

```powershell
git add src/types/crypto.ts src/constants/cryptoAssets.ts src/services/cryptoTradingApi.ts src/services/__tests__/cryptoTradingApi.test.ts
git commit -m "feat: add persistent crypto trading client"
```

## Task 8: Move Contest Join And Trade UI Off LocalStorage

**Files:**

- Modify: `src/views/ContestDetail.vue`
- Modify: `src/views/CryptoTrade.vue`
- Modify: `src/components/crypto/OrderTicket.vue`
- Modify: `src/components/crypto/PortfolioSummary.vue`
- Delete: `src/stores/cryptoContestStore.ts`
- Delete: `src/stores/__tests__/cryptoContestStore.test.ts`
- Modify: `src/views/__tests__/CryptoTrade.test.ts`
- Create: `src/views/__tests__/ContestDetail.test.ts`

- [ ] **Step 1: Write failing UI tests**

In `ContestDetail.test.ts`, mock `joinCryptoContest()` and assert:

```typescript
await wrapper.get('button').trigger('click')
expect(joinCryptoContest).toHaveBeenCalledWith('practice-arena')
expect(wrapper.text()).toContain('Joined')
```

In `CryptoTrade.test.ts`, mock:

```typescript
getCryptoAccount: vi.fn().mockResolvedValue(accountFixture),
placeCryptoMarketOrder: vi.fn().mockResolvedValue(orderFixture),
```

Assert:

```typescript
expect(getCryptoAccount).toHaveBeenCalledWith('practice-arena')
await orderTicket.vm.$emit('submit', { side: 'buy', quantity: 0.01 })
await flushPromises()
expect(placeCryptoMarketOrder).toHaveBeenCalledWith(expect.objectContaining({
  contestId: 'practice-arena',
  symbol: 'BTCUSDT',
  side: 'buy',
  quantity: 0.01,
}))
expect(getCryptoAccount).toHaveBeenCalledTimes(2)
```

- [ ] **Step 2: Run UI tests and confirm local implementation fails expectations**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/views/__tests__/CryptoTrade.test.ts
```

Expected: tests fail because views do not call backend trading APIs.

- [ ] **Step 3: Replace contest join persistence**

In `ContestDetail.vue`:

- Remove imports from `cryptoContestStore`.
- Add `joining`, `joined`, and `joinError` refs.
- Call `joinCryptoContest(contest.value.id)`.
- Disable the button while joining.
- Display `Joined` after success.
- Preserve the current layout and styling.

- [ ] **Step 4: Replace trade portfolio state**

In `CryptoTrade.vue`:

- Remove `cryptoContestStore` and `tradingSimulator` imports.
- Use `TradingAccount | null`.
- Load account from `getCryptoAccount(DEFAULT_CONTEST_ID)` on mount.
- On `404`, call `joinCryptoContest(DEFAULT_CONTEST_ID)` once and use the returned account.
- Generate `clientOrderId` with `crypto.randomUUID()`.
- Submit through `placeCryptoMarketOrder()`.
- Reload the account after a successful order.
- Prevent duplicate submission with an `orderSubmitting` ref.
- Keep existing market price polling until the realtime phase.

Compute portfolio metrics from backend account fields:

```typescript
const metrics = computed(() => ({
  cash: account.value?.cash ?? 0,
  positionsValue: Math.max((account.value?.equity ?? 0) - (account.value?.cash ?? 0), 0),
  equity: account.value?.equity ?? 0,
  pnl: (account.value?.equity ?? 0) - (account.value?.initialEquity ?? 0),
  roi: account.value?.initialEquity
    ? (((account.value?.equity ?? 0) - account.value.initialEquity) / account.value.initialEquity) * 100
    : 0,
  volume: account.value?.orders.reduce((sum, order) => sum + order.notional, 0) ?? 0,
  tradeCount: account.value?.orders.length ?? 0,
}))
```

- [ ] **Step 5: Add loading and submitting states**

In `OrderTicket.vue`, add:

```typescript
submitting?: boolean
disabled?: boolean
```

Disable the submit button when quantity is non-positive, account is unavailable, or an order is in flight. Use button text `Submitting...` while active.

In `PortfolioSummary.vue`, accept `TradingAccount` instead of `VirtualPortfolio`.

- [ ] **Step 6: Remove authoritative localStorage store**

Delete:

```text
src/stores/cryptoContestStore.ts
src/stores/__tests__/cryptoContestStore.test.ts
```

Run:

```powershell
rg -n "cryptoContestStore|crypto-contest-state-v1|executeMarketOrder" src
```

Expected: no production references remain.

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoTradingApi.test.ts src/views/__tests__/ContestDetail.test.ts src/views/__tests__/CryptoTrade.test.ts
```

Expected: targeted tests pass.

- [ ] **Step 8: Commit UI persistence migration**

```powershell
git add src/views/ContestDetail.vue src/views/CryptoTrade.vue src/components/crypto/OrderTicket.vue src/components/crypto/PortfolioSummary.vue src/views/__tests__/ContestDetail.test.ts src/views/__tests__/CryptoTrade.test.ts
git add -u src/stores
git commit -m "feat: persist crypto portfolios through backend"
```

## Task 9: End-To-End Verification And Documentation

**Files:**

- Modify: `README.md`
- Modify: `backend_v2/.env.example`
- Create: `backend_v2/tests/test_crypto_phase1_contract.py`

- [ ] **Step 1: Add a phase contract test**

Create `backend_v2/tests/test_crypto_phase1_contract.py` that checks:

```python
def test_phase1_contract_rejects_client_owned_portfolio(client):
    response = client.post(
        "/api/crypto/orders/market",
        headers=auth_headers,
        json={
            "contest_id": "practice-arena",
            "client_order_id": "contract-001",
            "symbol": "BTCUSDT",
            "side": "buy",
            "quantity": 0.001,
            "portfolio": {"cash": 999999999},
        },
    )
    assert response.status_code == 200
    assert response.json()["client_order_id"] == "contract-001"
```

The test fixture must use an authenticated user, an isolated test schema, and a stub liquidity provider. After the response, query MySQL and assert account cash came from the seeded `10000` balance rather than request JSON.

- [ ] **Step 2: Document configuration and migration commands**

Update `backend_v2/.env.example`:

```dotenv
MYSQL_URL=mysql+mysqlconnector://root:password@localhost/crypto_dex
MYSQL_ASYNC_URL=mysql+aiomysql://root:password@localhost/crypto_dex
DB_MIGRATIONS_ENABLED=true
DB_LEGACY_AUTO_DDL=false
```

Update `README.md` with:

- MySQL database creation.
- `alembic upgrade head`.
- Five supported Spot symbols.
- Authenticated contest join and order endpoints.
- Statement that frontend portfolio data no longer lives in localStorage.
- A note that DuckDB history and WebSocket realtime are Phase 2 and Phase 3.

- [ ] **Step 3: Run all backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests -q
```

Expected: all non-environmental tests pass; MySQL-only integration tests may be skipped only when `TEST_MYSQL_URL` is absent.

- [ ] **Step 4: Run all frontend checks**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run type-check
npm.cmd run build
```

Expected: all tests, type checking, and production build pass.

- [ ] **Step 5: Run a local smoke test**

Start backend with migrations enabled:

```powershell
$env:DB_MIGRATIONS_ENABLED="true"
$env:DB_LEGACY_AUTO_DDL="false"
.\.venv\Scripts\python.exe -m uvicorn src.main:app --app-dir backend_v2 --host 127.0.0.1 --port 8010
```

Start frontend:

```powershell
$env:VITE_BACKEND_URL="http://127.0.0.1:8010"
npm.cmd run dev -- --port 5175
```

Manual acceptance flow:

1. Register or sign in.
2. Open `/contests/practice-arena`.
3. Join the contest.
4. Open `/trade/BTCUSDT`.
5. Place a small buy.
6. Reload the page and confirm cash, position, and order remain.
7. Attempt an oversized sell and confirm rejection.

- [ ] **Step 6: Commit verification and docs**

```powershell
git add README.md backend_v2/.env.example backend_v2/tests/test_crypto_phase1_contract.py
git commit -m "docs: verify crypto trading foundation"
```

## Phase 1 Completion Criteria

- MySQL contains all five assets and the practice contest.
- Joining is authenticated and idempotent.
- Every user receives a separate account per contest.
- Browser-supplied cash, positions, or order history are ignored.
- Market orders consume Binance order-book levels and persist immutable fills.
- Duplicate `client_order_id` does not debit an account twice.
- Database locking prevents negative balances and positions.
- Reloading the frontend preserves portfolio state.
- Existing chart and order-book UI remains visually unchanged.
- Full tests, type checking, and production build pass.

## Follow-On Plans

After this plan is complete, create and execute these plans in order:

1. `crypto-market-warehouse`: dedicated DuckDB schema, one-year `1m` backfill, derived intervals, retention, and gap repair.
2. `crypto-realtime-market`: Binance WebSocket client, synchronized depth book, current candle cache, reconnect recovery, and frontend WebSocket delivery.
3. `crypto-contest-ranking`: equity snapshots, leaderboard calculation, persisted rankings, and admin contest management.
4. `crypto-production-hardening`: Redis, multi-instance locking, metrics, backup, reconciliation, and load testing.
