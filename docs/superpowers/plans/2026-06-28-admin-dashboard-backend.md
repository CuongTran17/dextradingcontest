# Admin Dashboard Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend APIs for the admin dashboard to monitor users, roles, contest accounts, balances, positions, orders, and high-level contest system status.

**Architecture:** Keep MySQL as the source of truth for users, contests, participants, accounts, balances, positions, orders, and fills. Extend the existing `/api/admin` router with read-focused dashboard endpoints, backed by a focused `CryptoAdminDashboardService` and repository methods in `CryptoTradingRepository`. Do not allow admins to edit balances or trades; only user role/lock, contest creation/status, and participant moderation remain mutable.

**Tech Stack:** FastAPI, SQLAlchemy ORM, MySQL in development, SQLite-backed unit tests, Pydantic response models where useful, existing JWT admin dependency `require_role("admin")`.

---

## File Structure

- Modify: `backend_v2/src/repositories/crypto_trading.py`
  - Add eager-loaded account list/detail queries and aggregate count helpers.
- Create: `backend_v2/src/services/crypto_admin_dashboard.py`
  - Serialize overview, account rows, account details, balances, positions, orders, and fills.
- Modify: `backend_v2/src/api/admin.py`
  - Add dashboard endpoints and enhance user list filters.
- Modify: `backend_v2/src/schemas/crypto_trading.py`
  - Add admin dashboard response schemas if route annotations become too large.
- Modify: `backend_v2/tests/test_admin_users.py`
  - Cover route surface and user query/filter behavior.
- Create: `backend_v2/tests/test_crypto_admin_dashboard.py`
  - Cover service serialization, account detail, and overview aggregation.
- Modify: `README.md`
  - Document backend admin dashboard endpoints after implementation.

No Alembic migration is required because this phase only reads existing tables.

---

### Task 1: Lock Backend API Contract With Route Surface Tests

**Files:**
- Modify: `backend_v2/tests/test_admin_users.py`

- [ ] **Step 1: Add failing API surface assertions**

Append the new dashboard endpoints to `test_admin_router_exposes_users_and_crypto_contests_only`:

```python
def test_admin_router_exposes_users_and_crypto_contests_only():
    client = make_client()
    paths = set(client.app.openapi()["paths"])

    assert "/api/admin/users" in paths
    assert "/api/admin/users/{user_id}/role" in paths
    assert "/api/admin/users/{user_id}/lock" in paths
    assert "/api/admin/users/{user_id}/unlock" in paths
    assert "/api/admin/crypto/overview" in paths
    assert "/api/admin/crypto/accounts" in paths
    assert "/api/admin/crypto/accounts/{account_id}" in paths
    assert "/api/admin/crypto/contests" in paths
    assert "/api/admin/crypto/contests/{contest_id}" in paths
    assert "/api/admin/crypto/contests/{contest_id}/status" in paths
    assert "/api/admin/crypto/contests/{contest_id}/participants" in paths
    assert "/api/admin/crypto/contests/{contest_id}/participants/{user_id}/status" in paths
    assert not any("/promotions" in path for path in paths)
    assert not any("/flash-sales" in path for path in paths)
    assert not any("/sales-stats" in path for path in paths)
    assert not any("/user-portfolios" in path for path in paths)
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py::test_admin_router_exposes_users_and_crypto_contests_only
```

Expected: FAIL because `/api/admin/crypto/overview`, `/api/admin/crypto/accounts`, and `/api/admin/crypto/accounts/{account_id}` do not exist yet.

- [ ] **Step 3: Add minimal route signatures only after RED**

Modify `backend_v2/src/api/admin.py` with route functions that still return simple values while later tasks fill them:

```python
@router.get("/crypto/overview")
def admin_crypto_overview(current_user: User = Depends(_require_admin)):
    del current_user
    return {"status": "not_implemented"}


@router.get("/crypto/accounts")
def admin_list_crypto_accounts(current_user: User = Depends(_require_admin)):
    del current_user
    return {"total": 0, "page": 1, "per_page": 20, "accounts": []}


@router.get("/crypto/accounts/{account_id}")
def admin_get_crypto_account(account_id: int, current_user: User = Depends(_require_admin)):
    del current_user, account_id
    return {"status": "not_implemented"}
```

- [ ] **Step 4: Run test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py::test_admin_router_exposes_users_and_crypto_contests_only
```

Expected: PASS.

---

### Task 2: Add Repository Queries for Admin Accounts

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Create: `backend_v2/tests/test_crypto_admin_dashboard.py`

- [ ] **Step 1: Write failing repository tests**

Create `backend_v2/tests/test_crypto_admin_dashboard.py` with a SQLite fixture mirroring `test_crypto_contests.py`, then add:

```python
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradingAccount,
    TradingOrder,
)
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_for_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def seed_account(db_session):
    user = User(id=1, email="student@example.com", password_hash="hash", fullname="Student One", role="user")
    btc = CryptoAsset(
        id=1,
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=6,
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        is_active=True,
    )
    contest = Contest(
        id=1,
        slug="practice-arena",
        title="Practice Arena",
        mode="practice",
        status="active",
        initial_balance=Decimal("10000"),
        quote_asset="USDT_TEST",
        fee_rate=Decimal("0.001"),
        rules_json="{}",
    )
    participant = ContestParticipant(id=1, contest_id=1, user_id=1, status="active")
    account = TradingAccount(
        id=1,
        contest_participant_id=1,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10100"),
        realized_pnl=Decimal("100"),
        unrealized_pnl=Decimal("0"),
    )
    account.balances.append(AccountBalance(asset="USDT_TEST", available=Decimal("9500"), locked=Decimal("100")))
    account.positions.append(
        Position(
            asset=btc,
            quantity=Decimal("0.01"),
            average_entry_price=Decimal("50000"),
            cost_basis=Decimal("500"),
            realized_pnl=Decimal("0"),
        )
    )
    account.orders.append(
        TradingOrder(
            id=1,
            client_order_id="web-1",
            asset=btc,
            side="buy",
            order_type="market",
            status="filled",
            requested_quantity=Decimal("0.01"),
            filled_quantity=Decimal("0.01"),
            average_fill_price=Decimal("50000"),
            estimated_notional=Decimal("500"),
            executed_notional=Decimal("500"),
            fee_amount=Decimal("0.5"),
            fee_asset="USDT_TEST",
            market_price_at_submission=Decimal("50000"),
            submitted_at=datetime(2026, 6, 28, tzinfo=timezone.utc),
        )
    )
    db_session.add_all([user, btc, contest, participant, account])
    db_session.commit()
    return account.id


def test_repository_lists_admin_accounts_with_user_and_contest(db_session):
    seed_account(db_session)
    repo = CryptoTradingRepository(db_session)

    rows, total = repo.list_admin_accounts(contest_slug="practice-arena", page=1, per_page=20)

    assert total == 1
    assert rows[0].id == 1
    assert rows[0].participant.user.email == "student@example.com"
    assert rows[0].participant.contest.slug == "practice-arena"


def test_repository_loads_admin_account_detail(db_session):
    account_id = seed_account(db_session)
    repo = CryptoTradingRepository(db_session)

    account = repo.get_admin_account_detail(account_id)

    assert account.id == account_id
    assert account.balances[0].asset == "USDT_TEST"
    assert account.positions[0].asset.symbol == "BTCUSDT"
    assert account.orders[0].client_order_id == "web-1"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py
```

Expected: FAIL with missing `list_admin_accounts` and `get_admin_account_detail`.

- [ ] **Step 3: Implement repository methods**

Modify `backend_v2/src/repositories/crypto_trading.py` imports:

```python
from src.database.user_models import User
```

Add relationships needed for eager loading in models if not already present:

```python
# In ContestParticipant
contest = relationship("Contest")
user = relationship("User")
```

Add repository methods:

```python
def list_admin_accounts(
    self,
    *,
    contest_slug: str | None = None,
    q: str | None = None,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[TradingAccount], int]:
    query = (
        self.db.query(TradingAccount)
        .join(ContestParticipant)
        .join(Contest)
        .join(User, User.id == ContestParticipant.user_id)
        .options(
            selectinload(TradingAccount.participant).selectinload(ContestParticipant.contest),
            selectinload(TradingAccount.participant).selectinload(ContestParticipant.user),
            selectinload(TradingAccount.balances),
            selectinload(TradingAccount.positions).selectinload(Position.asset),
            selectinload(TradingAccount.orders).selectinload(TradingOrder.asset),
        )
    )
    if contest_slug:
        query = query.filter(Contest.slug == contest_slug)
    if status:
        query = query.filter(TradingAccount.status == status)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.email.ilike(like)) | (User.fullname.ilike(like)))
    total = query.count()
    rows = (
        query.order_by(TradingAccount.updated_at.desc(), TradingAccount.id.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return rows, total


def get_admin_account_detail(self, account_id: int) -> TradingAccount | None:
    return (
        self.db.query(TradingAccount)
        .options(
            selectinload(TradingAccount.participant).selectinload(ContestParticipant.contest),
            selectinload(TradingAccount.participant).selectinload(ContestParticipant.user),
            selectinload(TradingAccount.balances),
            selectinload(TradingAccount.positions).selectinload(Position.asset),
            selectinload(TradingAccount.orders)
            .selectinload(TradingOrder.fills),
            selectinload(TradingAccount.orders).selectinload(TradingOrder.asset),
        )
        .filter(TradingAccount.id == account_id)
        .first()
    )
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py
```

Expected: PASS.

---

### Task 3: Add Admin Dashboard Service Serializers

**Files:**
- Create: `backend_v2/src/services/crypto_admin_dashboard.py`
- Modify: `backend_v2/tests/test_crypto_admin_dashboard.py`

- [ ] **Step 1: Write failing service serialization tests**

Append:

```python
from src.services.crypto_admin_dashboard import CryptoAdminDashboardService


def test_service_serializes_admin_account_rows(db_session):
    seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    result = service.list_accounts(contest_id="practice-arena", page=1, per_page=20)

    assert result["total"] == 1
    row = result["accounts"][0]
    assert row["user"]["email"] == "student@example.com"
    assert row["contest"]["id"] == "practice-arena"
    assert row["cash"] == 9500.0
    assert row["locked_cash"] == 100.0
    assert row["position_count"] == 1
    assert row["order_count"] == 1


def test_service_serializes_admin_account_detail(db_session):
    account_id = seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    result = service.get_account(account_id)

    assert result["account_id"] == account_id
    assert result["balances"] == [{"asset": "USDT_TEST", "available": 9500.0, "locked": 100.0}]
    assert result["positions"][0]["symbol"] == "BTCUSDT"
    assert result["orders"][0]["client_order_id"] == "web-1"
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py
```

Expected: FAIL because `CryptoAdminDashboardService` does not exist.

- [ ] **Step 3: Create service**

Create `backend_v2/src/services/crypto_admin_dashboard.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.repositories.crypto_trading import CryptoTradingRepository


class AdminAccountNotFoundError(Exception):
    pass


class CryptoAdminDashboardService:
    def __init__(self, repository: CryptoTradingRepository):
        self.repository = repository

    def list_accounts(
        self,
        *,
        contest_id: str | None = None,
        q: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        rows, total = self.repository.list_admin_accounts(
            contest_slug=contest_id,
            q=q,
            status=status,
            page=page,
            per_page=per_page,
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "accounts": [self._account_row(account) for account in rows],
        }

    def get_account(self, account_id: int) -> dict[str, Any]:
        account = self.repository.get_admin_account_detail(account_id)
        if account is None:
            raise AdminAccountNotFoundError("Trading account not found")
        return self._account_detail(account)

    def _account_row(self, account) -> dict[str, Any]:
        participant = account.participant
        contest = participant.contest
        user = participant.user
        cash = sum(float(balance.available) for balance in account.balances if balance.asset == contest.quote_asset)
        locked_cash = sum(float(balance.locked) for balance in account.balances if balance.asset == contest.quote_asset)
        initial = float(account.initial_equity)
        equity = float(account.current_equity)
        pnl = equity - initial
        return {
            "account_id": account.id,
            "status": account.status,
            "participant_status": participant.status,
            "user": self._user(user),
            "contest": {"id": contest.slug, "title": contest.title, "status": contest.status},
            "cash": round(cash, 2),
            "locked_cash": round(locked_cash, 2),
            "initial_equity": round(initial, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(float(account.realized_pnl), 2),
            "unrealized_pnl": round(float(account.unrealized_pnl), 2),
            "roi": round((pnl / initial) * 100, 4) if initial else 0,
            "position_count": len(account.positions),
            "order_count": len(account.orders),
            "updated_at": _iso(account.updated_at),
        }

    def _account_detail(self, account) -> dict[str, Any]:
        row = self._account_row(account)
        return {
            **row,
            "balances": [
                {
                    "asset": balance.asset,
                    "available": float(balance.available),
                    "locked": float(balance.locked),
                }
                for balance in account.balances
            ],
            "positions": [
                {
                    "symbol": position.asset.symbol,
                    "quantity": float(position.quantity),
                    "average_entry_price": float(position.average_entry_price),
                    "cost_basis": float(position.cost_basis),
                    "realized_pnl": float(position.realized_pnl),
                    "updated_at": _iso(position.updated_at),
                }
                for position in account.positions
            ],
            "orders": [
                {
                    "order_id": order.id,
                    "client_order_id": order.client_order_id,
                    "symbol": order.asset.symbol,
                    "side": order.side,
                    "order_type": order.order_type,
                    "status": order.status,
                    "requested_quantity": float(order.requested_quantity),
                    "filled_quantity": float(order.filled_quantity),
                    "average_fill_price": float(order.average_fill_price or 0),
                    "executed_notional": float(order.executed_notional),
                    "fee_amount": float(order.fee_amount),
                    "fee_asset": order.fee_asset,
                    "submitted_at": _iso(order.submitted_at),
                    "completed_at": _iso(order.completed_at),
                    "fills": [
                        {
                            "fill_sequence": fill.fill_sequence,
                            "price": float(fill.price),
                            "quantity": float(fill.quantity),
                            "notional": float(fill.notional),
                            "fee_amount": float(fill.fee_amount),
                            "fee_asset": fill.fee_asset,
                            "executed_at": _iso(fill.executed_at),
                        }
                        for fill in order.fills
                    ],
                }
                for order in sorted(account.orders, key=lambda item: item.submitted_at, reverse=True)
            ],
        }

    def _user(self, user) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "role": user.role,
            "is_locked": user.is_locked,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
```

- [ ] **Step 4: Run tests and verify they pass**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py
```

Expected: PASS.

---

### Task 4: Wire Account Endpoints Into Admin Router

**Files:**
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_crypto_admin_dashboard.py`

- [ ] **Step 1: Write failing route tests for account list/detail**

Append route tests using dependency overrides:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import admin


class FakeAdminDashboardService:
    def list_accounts(self, **kwargs):
        return {
            "total": 1,
            "page": kwargs["page"],
            "per_page": kwargs["per_page"],
            "accounts": [{"account_id": 1, "status": "active"}],
        }

    def get_account(self, account_id):
        return {"account_id": account_id, "status": "active", "balances": []}


def test_admin_account_routes_call_dashboard_service():
    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[admin._require_admin] = lambda: User(
        id=99,
        email="admin@example.com",
        password_hash="hash",
        fullname="Admin",
        role="admin",
    )
    app.dependency_overrides[admin.get_crypto_admin_dashboard_service] = lambda: FakeAdminDashboardService()
    client = TestClient(app)

    list_response = client.get("/api/admin/crypto/accounts?contest_id=practice-arena&page=1&per_page=20")
    detail_response = client.get("/api/admin/crypto/accounts/1")

    assert list_response.status_code == 200
    assert list_response.json()["accounts"][0]["account_id"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["account_id"] == 1
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py::test_admin_account_routes_call_dashboard_service
```

Expected: FAIL because dependency `get_crypto_admin_dashboard_service` or real route implementation is missing.

- [ ] **Step 3: Implement admin route dependency and endpoints**

Modify `backend_v2/src/api/admin.py`:

```python
from src.services.crypto_admin_dashboard import (
    AdminAccountNotFoundError,
    CryptoAdminDashboardService,
)


def get_crypto_admin_dashboard_service(db: Session = Depends(get_db)) -> CryptoAdminDashboardService:
    return CryptoAdminDashboardService(CryptoTradingRepository(db))


@router.get("/crypto/accounts")
def admin_list_crypto_accounts(
    contest_id: str | None = Query(default=None),
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    return service.list_accounts(
        contest_id=contest_id,
        q=q,
        status=status,
        page=page,
        per_page=per_page,
    )


@router.get("/crypto/accounts/{account_id}")
def admin_get_crypto_account(
    account_id: int,
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    try:
        return service.get_account(account_id)
    except AdminAccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 4: Run route test and verify it passes**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py::test_admin_account_routes_call_dashboard_service
```

Expected: PASS.

---

### Task 5: Add Overview Aggregation Endpoint

**Files:**
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/services/crypto_admin_dashboard.py`
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_crypto_admin_dashboard.py`

- [ ] **Step 1: Write failing overview service test**

Append:

```python
def test_service_builds_admin_overview(db_session):
    seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    overview = service.overview()

    assert overview["users"]["total"] == 1
    assert overview["users"]["admins"] == 0
    assert overview["contests"]["total"] == 1
    assert overview["contests"]["active"] == 1
    assert overview["accounts"]["total"] == 1
    assert overview["accounts"]["active"] == 1
    assert overview["accounts"]["total_equity"] == 10100.0
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py::test_service_builds_admin_overview
```

Expected: FAIL because `overview` does not exist.

- [ ] **Step 3: Add repository count helper**

Add to `CryptoTradingRepository`:

```python
def admin_overview_counts(self) -> dict:
    users_total = self.db.query(User).count()
    users_locked = self.db.query(User).filter(User.is_locked.is_(True)).count()
    users_admins = self.db.query(User).filter(User.role == "admin").count()
    contests_total = self.db.query(Contest).count()
    contests_active = self.db.query(Contest).filter(Contest.status == "active").count()
    participants_total = self.db.query(ContestParticipant).count()
    accounts_total = self.db.query(TradingAccount).count()
    accounts_active = self.db.query(TradingAccount).filter(TradingAccount.status == "active").count()
    total_equity = sum(float(row[0] or 0) for row in self.db.query(TradingAccount.current_equity).all())
    return {
        "users_total": users_total,
        "users_locked": users_locked,
        "users_admins": users_admins,
        "contests_total": contests_total,
        "contests_active": contests_active,
        "participants_total": participants_total,
        "accounts_total": accounts_total,
        "accounts_active": accounts_active,
        "total_equity": round(total_equity, 2),
    }
```

- [ ] **Step 4: Add service overview serializer**

Add to `CryptoAdminDashboardService`:

```python
def overview(self) -> dict[str, Any]:
    counts = self.repository.admin_overview_counts()
    return {
        "users": {
            "total": counts["users_total"],
            "locked": counts["users_locked"],
            "admins": counts["users_admins"],
        },
        "contests": {
            "total": counts["contests_total"],
            "active": counts["contests_active"],
            "participants": counts["participants_total"],
        },
        "accounts": {
            "total": counts["accounts_total"],
            "active": counts["accounts_active"],
            "total_equity": counts["total_equity"],
        },
    }
```

- [ ] **Step 5: Wire route**

Modify `backend_v2/src/api/admin.py`:

```python
@router.get("/crypto/overview")
def admin_crypto_overview(
    current_user: User = Depends(_require_admin),
    service: CryptoAdminDashboardService = Depends(get_crypto_admin_dashboard_service),
):
    del current_user
    return service.overview()
```

- [ ] **Step 6: Run overview test and route surface test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_admin_dashboard.py::test_service_builds_admin_overview backend_v2\tests\test_admin_users.py::test_admin_router_exposes_users_and_crypto_contests_only
```

Expected: PASS.

---

### Task 6: Improve User Listing for Admin Dashboard

**Files:**
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_admin_users.py`

- [ ] **Step 1: Write failing tests for search and locked filters**

Add tests with a SQLite session or direct route dependency override:

```python
def test_list_users_supports_search_and_locked_filters():
    paths = set(make_client().app.openapi()["paths"])
    assert "/api/admin/users" in paths
```

Then add a DB-backed test in the same style as existing admin tests once a fixture is available:

```python
def test_list_users_query_accepts_q_and_is_locked_parameters():
    schema = make_client().app.openapi()
    params = schema["paths"]["/api/admin/users"]["get"]["parameters"]
    names = {param["name"] for param in params}
    assert {"page", "per_page", "role", "q", "is_locked"} <= names
```

- [ ] **Step 2: Run test and verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py
```

Expected: FAIL because `q` and `is_locked` are not exposed.

- [ ] **Step 3: Add query filters**

Modify `list_users` in `backend_v2/src/api/admin.py`:

```python
def list_users(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    role: Optional[str] = Query(default=None),
    q: Optional[str] = Query(default=None),
    is_locked: Optional[bool] = Query(default=None),
    current_user: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    del current_user
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if is_locked is not None:
        query = query.filter(User.is_locked.is_(is_locked))
    if q:
        like = f"%{q.strip()}%"
        query = query.filter((User.email.ilike(like)) | (User.fullname.ilike(like)))
```

- [ ] **Step 4: Run admin user tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py
```

Expected: PASS.

---

### Task 7: Document Backend Admin API

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add backend API docs**

Add a short section:

```markdown
### Admin dashboard backend

Admin JWT required:

- `GET /api/admin/users?page=1&per_page=20&role=user&q=email&is_locked=false`
- `PUT /api/admin/users/{user_id}/role?role=admin`
- `PUT /api/admin/users/{user_id}/lock?reason=...`
- `PUT /api/admin/users/{user_id}/unlock`
- `GET /api/admin/crypto/overview`
- `GET /api/admin/crypto/accounts?contest_id=practice-arena&page=1&per_page=20`
- `GET /api/admin/crypto/accounts/{account_id}`
- `POST /api/admin/crypto/contests`
- `PUT /api/admin/crypto/contests/{contest_id}/status?status=active`
- `GET /api/admin/crypto/contests/{contest_id}/participants`
- `PUT /api/admin/crypto/contests/{contest_id}/participants/{user_id}/status?status=locked`

Admin APIs are for observing and moderating virtual contests. They must not edit account balances, positions, orders, fills, PnL, or leaderboard results directly.
```

- [ ] **Step 2: Run documentation-adjacent checks**

Run:

```powershell
git diff --check
```

Expected: no whitespace errors.

---

### Task 8: Final Verification and Commit

**Files:**
- All touched files from previous tasks.

- [ ] **Step 1: Run focused backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py backend_v2\tests\test_crypto_admin_dashboard.py backend_v2\tests\test_crypto_contests.py backend_v2\tests\test_crypto_routes.py
```

Expected: PASS.

- [ ] **Step 2: Run API surface smoke test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_app_surface.py
```

Expected: PASS and no legacy admin routes reappear.

- [ ] **Step 3: Note full-suite limitation**

Run full suite only if legacy tests have been removed or marked skipped:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests
```

Expected in current repo: collection errors remain for old removed modules such as analysis, vnstock, and market_duckdb. Do not treat those as caused by this feature unless new admin-dashboard tests fail.

- [ ] **Step 4: Commit**

Run:

```powershell
git add backend_v2/src/api/admin.py backend_v2/src/repositories/crypto_trading.py backend_v2/src/services/crypto_admin_dashboard.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_admin_users.py backend_v2/tests/test_crypto_admin_dashboard.py README.md
git commit -m "feat: add admin dashboard backend APIs"
```

---

## Self-Review

- Spec coverage: The plan covers user monitoring/search, role/lock APIs, account balances, account details, contest creation/status through existing APIs, participant moderation through existing APIs, and dashboard overview.
- Placeholder scan: No deferred implementation placeholders are required for backend MVP. The only intentionally temporary route signatures are in Task 1 and are replaced by later tasks before final verification.
- Type consistency: Endpoint names use `/api/admin/crypto/overview`, `/api/admin/crypto/accounts`, and `/api/admin/crypto/accounts/{account_id}` consistently across tests, service, router, and docs.
- Scope check: This is backend-only. Frontend tabs, tables, forms, and modals should be planned separately after these APIs exist.
