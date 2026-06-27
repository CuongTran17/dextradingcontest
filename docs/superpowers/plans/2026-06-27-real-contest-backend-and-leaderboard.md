# Real Contest Backend And Leaderboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hardcoded contest, participant, and leaderboard data with MySQL-backed contest APIs, admin contest management, and live-equity leaderboard data.

**Architecture:** MySQL remains the source of truth for users, contests, participants, accounts, orders, and fills. DuckDB remains only for market candles and indicators. Backend adds focused contest query/admin services on top of the existing crypto SQLAlchemy models, while frontend replaces `CRYPTO_CONTESTS` usage with typed API calls and keeps the current UI shape.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL, Vue 3, TypeScript, Vitest, pytest.

---

## File Structure

- Create `backend_v2/src/services/crypto_contests.py`
  - Public contest listing/detail service.
  - Admin contest create/update/status-lock service.
  - Leaderboard calculation using account balances, positions, fills, and latest prices.
- Modify `backend_v2/src/repositories/crypto_trading.py`
  - Add contest list/detail, asset lookup, participant list, and leaderboard query helpers.
- Modify `backend_v2/src/schemas/crypto_trading.py`
  - Add contest, admin contest, participant, and leaderboard response/request schemas.
- Modify `backend_v2/src/routes/crypto_trading.py`
  - Add public contest routes under `/api/crypto/contests`.
  - Keep join/account/order routes intact.
- Modify `backend_v2/src/api/admin.py`
  - Add admin contest routes under `/api/admin/crypto/contests`.
  - Keep user admin routes intact.
- Create `backend_v2/tests/test_crypto_contests.py`
  - Service-level tests for contest mapping, admin create/update, and leaderboard math.
- Modify `backend_v2/tests/test_crypto_trading_routes.py`
  - Route tests for public contest list/detail/leaderboard.
- Modify `backend_v2/tests/test_admin_users.py`
  - Extend admin surface test to include crypto contest routes and still reject old legacy routes.
- Create `src/services/cryptoContestApi.ts`
  - Typed frontend API client for contests, leaderboard, and admin contest actions.
- Modify `src/types/crypto.ts`
  - Add `ContestCreateInput`, `ContestUpdateInput`, `LeaderboardRow`, and admin participant types.
- Modify `src/views/ContestList.vue`
  - Fetch contests from backend instead of `CRYPTO_CONTESTS`.
- Modify `src/views/ContestDetail.vue`
  - Fetch contest detail from backend before joining.
- Modify `src/views/ContestLeaderboard.vue`
  - Fetch leaderboard rows from backend.
- Modify `src/views/Admin/components/TabContests.vue`
  - Render backend contests and add a simple create/status form.
- Modify `src/views/Admin/components/TabContestParticipants.vue`
  - Render real participant rows for selected contest.
- Modify frontend tests:
  - `src/services/__tests__/cryptoContestApi.test.ts`
  - `src/views/__tests__/ContestDetail.test.ts`
  - `src/views/__tests__/ContestLeaderboard.test.ts`
  - Add or update admin component tests if current test coverage is present.

---

## Task 1: Backend Contest Schemas And Repository Queries

**Files:**
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Create: `backend_v2/tests/test_crypto_contests.py`

- [ ] **Step 1: Add failing schema/repository tests**

Create `backend_v2/tests/test_crypto_contests.py` with the first test:

```python
from datetime import datetime, timezone
from decimal import Decimal

from src.database.crypto_models import Contest, ContestAsset, CryptoAsset
from src.repositories.crypto_trading import CryptoTradingRepository


def test_repository_lists_contests_with_enabled_symbols(db_session):
    btc = CryptoAsset(
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
    eth = CryptoAsset(
        exchange="binance",
        market_type="spot",
        symbol="ETHUSDT",
        base_asset="ETH",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=5,
        min_quantity=Decimal("0.00001"),
        min_notional=Decimal("5"),
        is_active=True,
    )
    contest = Contest(
        slug="practice-arena",
        title="Practice Arena",
        mode="practice",
        status="active",
        initial_balance=Decimal("10000"),
        quote_asset="USDT_TEST",
        starts_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fee_rate=Decimal("0.001"),
        rules_json="{}",
    )
    contest.assets.append(ContestAsset(asset=btc, is_enabled=True))
    contest.assets.append(ContestAsset(asset=eth, is_enabled=True))
    db_session.add(contest)
    db_session.commit()

    rows = CryptoTradingRepository(db_session).list_contests()

    assert len(rows) == 1
    assert rows[0].slug == "practice-arena"
    assert [asset.asset.symbol for asset in rows[0].assets] == ["BTCUSDT", "ETHUSDT"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py::test_repository_lists_contests_with_enabled_symbols -q
```

Expected: FAIL because `CryptoTradingRepository.list_contests` does not exist.

- [ ] **Step 3: Implement repository methods**

Add these methods to `CryptoTradingRepository`:

```python
from sqlalchemy.orm import selectinload

def list_contests(self) -> list[Contest]:
    return (
        self.db.query(Contest)
        .options(selectinload(Contest.assets).selectinload(ContestAsset.asset))
        .order_by(Contest.starts_at.desc(), Contest.id.desc())
        .all()
    )

def get_contest_by_slug(self, slug: str) -> Contest | None:
    return (
        self.db.query(Contest)
        .options(selectinload(Contest.assets).selectinload(ContestAsset.asset))
        .filter(Contest.slug == slug)
        .first()
    )

def get_assets_by_symbols(self, symbols: list[str]) -> list[CryptoAsset]:
    return (
        self.db.query(CryptoAsset)
        .filter(CryptoAsset.symbol.in_(symbols), CryptoAsset.is_active.is_(True))
        .order_by(CryptoAsset.symbol.asc())
        .all()
    )
```

- [ ] **Step 4: Add Pydantic schemas**

Add to `backend_v2/src/schemas/crypto_trading.py`:

```python
from datetime import datetime


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
    slug: str = Field(min_length=3, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
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
    status: Literal["draft", "scheduled", "active", "settling", "completed", "cancelled"] | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    symbols: list[CryptoSymbol] | None = Field(default=None, min_length=1, max_length=5)
```

- [ ] **Step 5: Run backend test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py -q
```

Expected: PASS for the repository test.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2/src/schemas/crypto_trading.py backend_v2/src/repositories/crypto_trading.py backend_v2/tests/test_crypto_contests.py
git commit -m "feat: add crypto contest repository queries"
```

---

## Task 2: Public Contest API

**Files:**
- Create/modify: `backend_v2/src/services/crypto_contests.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/tests/test_crypto_trading_routes.py`

- [ ] **Step 1: Add failing route tests**

Append to `backend_v2/tests/test_crypto_trading_routes.py`:

```python
CONTEST = {
    "id": "practice-arena",
    "title": "Practice Arena",
    "status": "practice",
    "raw_status": "active",
    "mode": "practice",
    "initial_capital": 10000.0,
    "quote_asset": "USDT_TEST",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "starts_at": "2026-06-01T00:00:00+00:00",
    "ends_at": "2026-07-01T00:00:00+00:00",
    "participant_count": 3,
}


class FakeContestService:
    def list_contests(self):
        return [CONTEST]

    def get_contest(self, slug):
        assert slug == "practice-arena"
        return CONTEST


def test_list_public_contests_does_not_require_auth():
    app, _order_service = _make_app()
    app.dependency_overrides[get_contest_service] = lambda: FakeContestService()
    client = TestClient(app)

    response = client.get("/api/crypto/contests")

    assert response.status_code == 200
    assert response.json() == [CONTEST]


def test_get_public_contest_detail_does_not_require_auth():
    app, _order_service = _make_app()
    app.dependency_overrides[get_contest_service] = lambda: FakeContestService()
    client = TestClient(app)

    response = client.get("/api/crypto/contests/practice-arena")

    assert response.status_code == 200
    assert response.json()["id"] == "practice-arena"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_trading_routes.py::test_list_public_contests_does_not_require_auth backend_v2\tests\test_crypto_trading_routes.py::test_get_public_contest_detail_does_not_require_auth -q
```

Expected: FAIL because `get_contest_service` and the new routes do not exist.

- [ ] **Step 3: Implement contest service mapper**

Create `backend_v2/src/services/crypto_contests.py`:

```python
from datetime import datetime, timezone

from src.database.crypto_models import Contest
from src.repositories.crypto_trading import CryptoTradingRepository


class ContestNotFoundError(Exception):
    pass


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _public_status(contest: Contest) -> str:
    if contest.mode == "practice":
        return "practice"
    if contest.status in {"draft", "scheduled"}:
        return "upcoming"
    if contest.status in {"active", "settling"}:
        return "active"
    return "ended"


class CryptoContestService:
    def __init__(self, repository: CryptoTradingRepository):
        self.repository = repository

    def list_contests(self) -> list[dict]:
        return [self._map_contest(contest) for contest in self.repository.list_contests()]

    def get_contest(self, slug: str) -> dict:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")
        return self._map_contest(contest)

    def _map_contest(self, contest: Contest) -> dict:
        enabled_assets = [item.asset for item in contest.assets if item.is_enabled and item.asset.is_active]
        return {
            "id": contest.slug,
            "title": contest.title,
            "status": _public_status(contest),
            "raw_status": contest.status,
            "mode": contest.mode,
            "initial_capital": float(contest.initial_balance),
            "quote_asset": contest.quote_asset,
            "symbols": [asset.symbol for asset in enabled_assets],
            "starts_at": _iso(contest.starts_at),
            "ends_at": _iso(contest.ends_at),
            "participant_count": len(contest.participants),
        }
```

- [ ] **Step 4: Register public routes**

In `backend_v2/src/routes/crypto_trading.py`, import `CryptoContestService` and add:

```python
from src.services.crypto_contests import ContestNotFoundError as PublicContestNotFoundError
from src.services.crypto_contests import CryptoContestService


def get_contest_service(
    db: Session = Depends(get_db),
) -> CryptoContestService:
    return CryptoContestService(CryptoTradingRepository(db))


@router.get("/contests")
def list_contests(
    service: CryptoContestService = Depends(get_contest_service),
):
    return service.list_contests()


@router.get("/contests/{contest_id}")
def get_contest(
    contest_id: str,
    service: CryptoContestService = Depends(get_contest_service),
):
    try:
        return service.get_contest(contest_id)
    except PublicContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

Place these `GET` routes before `POST /contests/{contest_id}/join` so route matching remains clear.

- [ ] **Step 5: Run route tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_trading_routes.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2/src/services/crypto_contests.py backend_v2/src/routes/crypto_trading.py backend_v2/tests/test_crypto_trading_routes.py
git commit -m "feat: expose public crypto contest api"
```

---

## Task 3: Admin Contest Management API

**Files:**
- Modify: `backend_v2/src/services/crypto_contests.py`
- Modify: `backend_v2/src/api/admin.py`
- Modify: `backend_v2/tests/test_admin_users.py`
- Modify: `backend_v2/tests/test_crypto_contests.py`

- [ ] **Step 1: Add failing admin route surface test**

Update `test_admin_router_has_only_user_management_paths` in `backend_v2/tests/test_admin_users.py`:

```python
def test_admin_router_exposes_users_and_crypto_contests_only():
    client = make_client()
    paths = set(client.app.openapi()["paths"])

    assert "/api/admin/users" in paths
    assert "/api/admin/users/{user_id}/role" in paths
    assert "/api/admin/users/{user_id}/lock" in paths
    assert "/api/admin/users/{user_id}/unlock" in paths
    assert "/api/admin/crypto/contests" in paths
    assert "/api/admin/crypto/contests/{contest_id}" in paths
    assert "/api/admin/crypto/contests/{contest_id}/status" in paths
    assert not any("/promotions" in path for path in paths)
    assert not any("/flash-sales" in path for path in paths)
    assert not any("/sales-stats" in path for path in paths)
    assert not any("/user-portfolios" in path for path in paths)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py::test_admin_router_exposes_users_and_crypto_contests_only -q
```

Expected: FAIL because admin contest routes do not exist.

- [ ] **Step 3: Add admin service methods**

Extend `CryptoContestService`:

```python
from src.database.crypto_models import Contest, ContestAsset
from src.schemas.crypto_trading import ContestCreate, ContestUpdate


class ContestValidationError(Exception):
    pass


def create_contest(self, body: ContestCreate, created_by: int | None) -> dict:
    if self.repository.get_contest_by_slug(body.slug):
        raise ContestValidationError(f"Contest slug '{body.slug}' already exists")
    assets = self.repository.get_assets_by_symbols(list(dict.fromkeys(body.symbols)))
    found = {asset.symbol for asset in assets}
    missing = [symbol for symbol in body.symbols if symbol not in found]
    if missing:
        raise ContestValidationError(f"Unsupported symbols: {', '.join(missing)}")
    contest = Contest(
        slug=body.slug,
        title=body.title,
        mode=body.mode,
        status=body.status,
        initial_balance=body.initial_balance,
        quote_asset=body.quote_asset,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        fee_rate=body.fee_rate,
        rules_json="{}",
        created_by=created_by,
    )
    for asset in assets:
        contest.assets.append(ContestAsset(asset=asset, is_enabled=True))
    self.repository.db.add(contest)
    self.repository.commit()
    return self._map_contest(contest)

def update_contest(self, slug: str, body: ContestUpdate) -> dict:
    contest = self.repository.get_contest_by_slug(slug)
    if contest is None:
        raise ContestNotFoundError(f"Contest '{slug}' not found")
    if body.title is not None:
        contest.title = body.title
    if body.status is not None:
        contest.status = body.status
    if body.starts_at is not None:
        contest.starts_at = body.starts_at
    if body.ends_at is not None:
        contest.ends_at = body.ends_at
    if body.symbols is not None:
        assets = self.repository.get_assets_by_symbols(list(dict.fromkeys(body.symbols)))
        found = {asset.symbol for asset in assets}
        missing = [symbol for symbol in body.symbols if symbol not in found]
        if missing:
            raise ContestValidationError(f"Unsupported symbols: {', '.join(missing)}")
        contest.assets.clear()
        for asset in assets:
            contest.assets.append(ContestAsset(asset=asset, is_enabled=True))
    self.repository.commit()
    return self._map_contest(contest)

def set_contest_status(self, slug: str, status: str) -> dict:
    contest = self.repository.get_contest_by_slug(slug)
    if contest is None:
        raise ContestNotFoundError(f"Contest '{slug}' not found")
    if status not in {"draft", "scheduled", "active", "settling", "completed", "cancelled"}:
        raise ContestValidationError("Invalid contest status")
    contest.status = status
    self.repository.commit()
    return self._map_contest(contest)
```

- [ ] **Step 4: Add admin routes**

In `backend_v2/src/api/admin.py`, add imports and routes:

```python
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.crypto_trading import ContestCreate, ContestUpdate
from src.services.crypto_contests import (
    ContestNotFoundError,
    ContestValidationError,
    CryptoContestService,
)


def get_crypto_contest_service(db: Session = Depends(get_db)) -> CryptoContestService:
    return CryptoContestService(CryptoTradingRepository(db))


@router.get("/crypto/contests")
def admin_list_crypto_contests(
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    return service.list_contests()


@router.post("/crypto/contests")
def admin_create_crypto_contest(
    body: ContestCreate,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    try:
        return service.create_contest(body, current_user.id)
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/crypto/contests/{contest_id}")
def admin_update_crypto_contest(
    contest_id: str,
    body: ContestUpdate,
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.update_contest(contest_id, body)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.put("/crypto/contests/{contest_id}/status")
def admin_set_crypto_contest_status(
    contest_id: str,
    status: str = Query(...),
    current_user: User = Depends(_require_admin),
    service: CryptoContestService = Depends(get_crypto_contest_service),
):
    del current_user
    try:
        return service.set_contest_status(contest_id, status)
    except ContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ContestValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
```

- [ ] **Step 5: Run admin tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py backend_v2\tests\test_crypto_contests.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2/src/api/admin.py backend_v2/src/services/crypto_contests.py backend_v2/tests/test_admin_users.py backend_v2/tests/test_crypto_contests.py
git commit -m "feat: add admin crypto contest management"
```

---

## Task 4: Leaderboard API With Live Equity

**Files:**
- Modify: `backend_v2/src/services/crypto_contests.py`
- Modify: `backend_v2/src/repositories/crypto_trading.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/src/schemas/crypto_trading.py`
- Modify: `backend_v2/tests/test_crypto_contests.py`
- Modify: `backend_v2/tests/test_crypto_trading_routes.py`

- [ ] **Step 1: Add leaderboard schemas**

Add to `backend_v2/src/schemas/crypto_trading.py`:

```python
class LeaderboardRowResponse(BaseModel):
    rank: int
    user: str
    equity: float
    pnl: float
    roi: float
    volume: float
    trade_count: int
    last_trade: str | None
```

- [ ] **Step 2: Add failing leaderboard math test**

Append to `backend_v2/tests/test_crypto_contests.py`:

```python
def test_leaderboard_ranks_accounts_by_cash_plus_position_value(db_session):
    # Reuse the model constructors from the first test, then create two participants:
    # user A: 10000 cash, no position
    # user B: 8000 cash, 0.1 BTC, latest BTC price 30000 => 11000 equity
    # The expected rank order is user B first, user A second.
    service = CryptoContestService(CryptoTradingRepository(db_session), price_provider=lambda symbols: {"BTCUSDT": 30000.0})

    rows = service.get_leaderboard("practice-arena")

    assert rows[0]["rank"] == 1
    assert rows[0]["equity"] == 11000.0
    assert rows[0]["roi"] == 10.0
    assert rows[1]["rank"] == 2
    assert rows[1]["equity"] == 10000.0
```

When implementing this test, create actual `User`, `ContestParticipant`, `TradingAccount`, `AccountBalance`, `Position`, and `TradingOrder` rows so the test validates repository joins, not a mock list.

- [ ] **Step 3: Run test to verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py::test_leaderboard_ranks_accounts_by_cash_plus_position_value -q
```

Expected: FAIL because `CryptoContestService.get_leaderboard` does not exist.

- [ ] **Step 4: Add repository participant query**

Add to `CryptoTradingRepository`:

```python
def list_contest_participants(self, contest_slug: str) -> list[ContestParticipant]:
    return (
        self.db.query(ContestParticipant)
        .join(Contest)
        .options(
            selectinload(ContestParticipant.account).selectinload(TradingAccount.balances),
            selectinload(ContestParticipant.account).selectinload(TradingAccount.positions).selectinload(Position.asset),
            selectinload(ContestParticipant.account).selectinload(TradingAccount.orders).selectinload(TradingOrder.asset),
        )
        .filter(Contest.slug == contest_slug)
        .all()
    )
```

- [ ] **Step 5: Implement leaderboard service**

Extend `CryptoContestService.__init__` to accept an optional price provider:

```python
from src.services.binance_market_data import get_latest_prices


def __init__(self, repository: CryptoTradingRepository, price_provider=None):
    self.repository = repository
    self.price_provider = price_provider or get_latest_prices
```

Add:

```python
def get_leaderboard(self, slug: str) -> list[dict]:
    contest = self.repository.get_contest_by_slug(slug)
    if contest is None:
        raise ContestNotFoundError(f"Contest '{slug}' not found")
    participants = self.repository.list_contest_participants(slug)
    symbols = [
        item.asset.symbol
        for item in contest.assets
        if item.is_enabled and item.asset.is_active
    ]
    prices = self.price_provider(symbols)
    rows = []
    for participant in participants:
        account = participant.account
        if account is None:
            continue
        cash = sum(float(balance.available) for balance in account.balances if balance.asset == contest.quote_asset)
        position_value = sum(
            float(position.quantity) * float(prices.get(position.asset.symbol, 0))
            for position in account.positions
        )
        equity = cash + position_value
        initial = float(account.initial_equity)
        pnl = equity - initial
        volume = sum(float(order.executed_notional) for order in account.orders if order.status == "filled")
        last_order = max(account.orders, key=lambda order: order.submitted_at, default=None)
        rows.append({
            "rank": 0,
            "user": f"user-{participant.user_id}",
            "equity": round(equity, 2),
            "pnl": round(pnl, 2),
            "roi": round((pnl / initial) * 100, 4) if initial else 0,
            "volume": round(volume, 2),
            "trade_count": len([order for order in account.orders if order.status == "filled"]),
            "last_trade": f"{last_order.asset.symbol} {last_order.side}" if last_order else None,
        })
    rows.sort(key=lambda row: row["equity"], reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows
```

- [ ] **Step 6: Add public leaderboard route**

In `backend_v2/src/routes/crypto_trading.py`:

```python
@router.get("/contests/{contest_id}/leaderboard")
def get_contest_leaderboard(
    contest_id: str,
    service: CryptoContestService = Depends(get_contest_service),
):
    try:
        return service.get_leaderboard(contest_id)
    except PublicContestNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 7: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py backend_v2\tests\test_crypto_trading_routes.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend_v2/src/services/crypto_contests.py backend_v2/src/repositories/crypto_trading.py backend_v2/src/routes/crypto_trading.py backend_v2/src/schemas/crypto_trading.py backend_v2/tests/test_crypto_contests.py backend_v2/tests/test_crypto_trading_routes.py
git commit -m "feat: add live crypto contest leaderboard"
```

---

## Task 5: Frontend Contest API Client

**Files:**
- Create: `src/services/cryptoContestApi.ts`
- Create: `src/services/__tests__/cryptoContestApi.test.ts`
- Modify: `src/types/crypto.ts`

- [ ] **Step 1: Add failing API client tests**

Create `src/services/__tests__/cryptoContestApi.test.ts`:

```ts
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createAdminCryptoContest,
  fetchContest,
  fetchContestLeaderboard,
  fetchContests,
} from '@/services/cryptoContestApi'
import { backendFetch } from '@/services/httpClient'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
  normalizeBackendUrl: () => 'http://localhost:8000',
}))

vi.mock('@/services/authApi', () => ({
  getToken: () => 'token-123',
}))

describe('cryptoContestApi', () => {
  beforeEach(() => vi.mocked(backendFetch).mockReset())

  it('maps public contests from backend fields', async () => {
    vi.mocked(backendFetch).mockResolvedValue([
      {
        id: 'practice-arena',
        title: 'Practice Arena',
        status: 'practice',
        raw_status: 'active',
        mode: 'practice',
        initial_capital: 10000,
        quote_asset: 'USDT_TEST',
        symbols: ['BTCUSDT'],
        starts_at: '2026-06-01T00:00:00+00:00',
        ends_at: '2026-07-01T00:00:00+00:00',
        participant_count: 4,
      },
    ])

    const contests = await fetchContests()

    expect(backendFetch).toHaveBeenCalledWith('http://localhost:8000', '/api/crypto/contests')
    expect(contests[0]).toMatchObject({
      id: 'practice-arena',
      initialCapital: 10000,
      participantCount: 4,
    })
  })

  it('loads contest detail and leaderboard', async () => {
    vi.mocked(backendFetch)
      .mockResolvedValueOnce({
        id: 'practice-arena',
        title: 'Practice Arena',
        status: 'practice',
        raw_status: 'active',
        mode: 'practice',
        initial_capital: 10000,
        quote_asset: 'USDT_TEST',
        symbols: ['BTCUSDT'],
        starts_at: null,
        ends_at: null,
        participant_count: 1,
      })
      .mockResolvedValueOnce([{ rank: 1, user: 'user-1', equity: 11000, pnl: 1000, roi: 10, volume: 5000, trade_count: 2, last_trade: 'BTCUSDT buy' }])

    expect((await fetchContest('practice-arena')).id).toBe('practice-arena')
    expect((await fetchContestLeaderboard('practice-arena'))[0].tradeCount).toBe(2)
  })

  it('creates admin contests with bearer auth', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      id: 'new-contest',
      title: 'New Contest',
      status: 'upcoming',
      raw_status: 'scheduled',
      mode: 'contest',
      initial_capital: 10000,
      quote_asset: 'USDT_TEST',
      symbols: ['BTCUSDT'],
      starts_at: null,
      ends_at: null,
      participant_count: 0,
    })

    await createAdminCryptoContest({
      slug: 'new-contest',
      title: 'New Contest',
      mode: 'contest',
      status: 'scheduled',
      initialBalance: 10000,
      symbols: ['BTCUSDT'],
    })

    expect(vi.mocked(backendFetch).mock.calls[0][2]).toMatchObject({
      method: 'POST',
      headers: { Authorization: 'Bearer token-123' },
    })
  })
})
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: FAIL because `cryptoContestApi.ts` does not exist.

- [ ] **Step 3: Add frontend types**

Add to `src/types/crypto.ts`:

```ts
export type RawContestStatus = 'draft' | 'scheduled' | 'active' | 'settling' | 'completed' | 'cancelled'

export interface LeaderboardRow {
  rank: number
  user: string
  equity: number
  pnl: number
  roi: number
  volume: number
  tradeCount: number
  lastTrade: string | null
}

export interface ContestCreateInput {
  slug: string
  title: string
  mode: 'practice' | 'contest'
  status: 'draft' | 'scheduled' | 'active'
  initialBalance: number
  symbols: CryptoSymbol[]
  startsAt?: string | null
  endsAt?: string | null
}

export interface ContestUpdateInput {
  title?: string
  status?: RawContestStatus
  symbols?: CryptoSymbol[]
  startsAt?: string | null
  endsAt?: string | null
}
```

- [ ] **Step 4: Implement API client**

Create `src/services/cryptoContestApi.ts`:

```ts
import { getToken } from '@/services/authApi'
import { backendFetch, normalizeBackendUrl } from '@/services/httpClient'
import type {
  Contest,
  ContestCreateInput,
  ContestUpdateInput,
  LeaderboardRow,
} from '@/types/crypto'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)

interface BackendContest {
  id: Contest['id']
  title: string
  status: Contest['status']
  raw_status: string
  mode: Contest['mode']
  initial_capital: number
  quote_asset: string
  symbols: Contest['symbols']
  starts_at: string | null
  ends_at: string | null
  participant_count: number
}

interface BackendLeaderboardRow {
  rank: number
  user: string
  equity: number
  pnl: number
  roi: number
  volume: number
  trade_count: number
  last_trade: string | null
}

function adminHeaders(): HeadersInit {
  const token = getToken()
  if (!token) throw new Error('Please sign in as admin')
  return { Authorization: `Bearer ${token}` }
}

export async function fetchContests(): Promise<Contest[]> {
  const contests = await backendFetch<BackendContest[]>(BACKEND_URL, '/api/crypto/contests')
  return contests.map(mapContest)
}

export async function fetchContest(contestId: string): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(BACKEND_URL, `/api/crypto/contests/${encodeURIComponent(contestId)}`)
  return mapContest(contest)
}

export async function fetchContestLeaderboard(contestId: string): Promise<LeaderboardRow[]> {
  const rows = await backendFetch<BackendLeaderboardRow[]>(BACKEND_URL, `/api/crypto/contests/${encodeURIComponent(contestId)}/leaderboard`)
  return rows.map((row) => ({
    rank: row.rank,
    user: row.user,
    equity: row.equity,
    pnl: row.pnl,
    roi: row.roi,
    volume: row.volume,
    tradeCount: row.trade_count,
    lastTrade: row.last_trade,
  }))
}

export async function createAdminCryptoContest(input: ContestCreateInput): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(BACKEND_URL, '/api/admin/crypto/contests', {
    method: 'POST',
    headers: adminHeaders(),
    body: JSON.stringify({
      slug: input.slug,
      title: input.title,
      mode: input.mode,
      status: input.status,
      initial_balance: input.initialBalance,
      symbols: input.symbols,
      starts_at: input.startsAt ?? null,
      ends_at: input.endsAt ?? null,
    }),
  })
  return mapContest(contest)
}

export async function updateAdminCryptoContest(contestId: string, input: ContestUpdateInput): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(BACKEND_URL, `/api/admin/crypto/contests/${encodeURIComponent(contestId)}`, {
    method: 'PUT',
    headers: adminHeaders(),
    body: JSON.stringify({
      title: input.title,
      status: input.status,
      symbols: input.symbols,
      starts_at: input.startsAt,
      ends_at: input.endsAt,
    }),
  })
  return mapContest(contest)
}

function mapContest(contest: BackendContest): Contest {
  return {
    id: contest.id,
    title: contest.title,
    status: contest.status,
    mode: contest.mode,
    initialCapital: contest.initial_capital,
    symbols: contest.symbols,
    startsAt: contest.starts_at ?? '',
    endsAt: contest.ends_at ?? '',
    participantCount: contest.participant_count,
  }
}
```

- [ ] **Step 5: Run frontend API tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/cryptoContestApi.test.ts
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add src/types/crypto.ts src/services/cryptoContestApi.ts src/services/__tests__/cryptoContestApi.test.ts
git commit -m "feat: add crypto contest frontend api"
```

---

## Task 6: Replace Public Contest Views With Backend Data

**Files:**
- Modify: `src/views/ContestList.vue`
- Modify: `src/views/ContestDetail.vue`
- Modify: `src/views/ContestLeaderboard.vue`
- Modify: `src/views/__tests__/ContestDetail.test.ts`
- Create/modify: `src/views/__tests__/ContestLeaderboard.test.ts`

- [ ] **Step 1: Add failing view tests**

Update `ContestDetail.test.ts` to mock `fetchContest`:

```ts
vi.mock('@/services/cryptoContestApi', () => ({
  fetchContest: vi.fn().mockResolvedValue({
    id: 'practice-arena',
    title: 'Practice Arena From API',
    status: 'practice',
    mode: 'practice',
    initialCapital: 10000,
    symbols: ['BTCUSDT'],
    startsAt: '2026-06-01T00:00:00+00:00',
    endsAt: '2026-07-01T00:00:00+00:00',
    participantCount: 2,
  }),
}))

it('loads contest detail from the backend', async () => {
  const wrapper = mount(ContestDetail)
  await flushPromises()

  expect(wrapper.text()).toContain('Practice Arena From API')
})
```

Create `src/views/__tests__/ContestLeaderboard.test.ts`:

```ts
import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

import ContestLeaderboard from '@/views/ContestLeaderboard.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoContestApi', () => ({
  fetchContestLeaderboard: vi.fn().mockResolvedValue([
    { rank: 1, user: 'user-2', equity: 11000, pnl: 1000, roi: 10, volume: 5000, tradeCount: 2, lastTrade: 'BTCUSDT buy' },
  ]),
}))

describe('ContestLeaderboard', () => {
  it('renders backend leaderboard rows', async () => {
    const wrapper = mount(ContestLeaderboard)
    await flushPromises()

    expect(wrapper.text()).toContain('user-2')
    expect(wrapper.text()).toContain('11,000')
  })
})
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/views/__tests__/ContestLeaderboard.test.ts
```

Expected: FAIL because the views still read hardcoded data.

- [ ] **Step 3: Update `ContestList.vue`**

Replace `CRYPTO_CONTESTS` usage with:

```ts
import { computed, onMounted, ref } from 'vue'

import { fetchContests } from '@/services/cryptoContestApi'
import type { Contest, ContestStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const loading = ref(true)
const loadError = ref('')

onMounted(async () => {
  try {
    contests.value = await fetchContests()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load contests'
  } finally {
    loading.value = false
  }
})

const statuses: ContestStatus[] = ['practice', 'upcoming', 'active', 'ended']
const groupedContests = computed(() =>
  statuses
    .map((status) => ({
      status,
      contests: contests.value.filter((contest) => contest.status === status),
    }))
    .filter((group) => group.contests.length > 0),
)
```

Add small loading/error text to the existing template:

```vue
<p v-if="loading" class="text-sm text-gray-500 dark:text-gray-400">Loading contests...</p>
<p v-else-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>
```

- [ ] **Step 4: Update `ContestDetail.vue`**

Replace computed hardcoded contest with:

```ts
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { fetchContest } from '@/services/cryptoContestApi'
import { joinCryptoContest } from '@/services/cryptoTradingApi'
import type { Contest } from '@/types/crypto'

const route = useRoute()
const contest = ref<Contest | null>(null)
const loading = ref(true)
const loadError = ref('')

const contestId = computed(() => String(route.params.contestId || 'practice-arena'))

onMounted(async () => {
  try {
    contest.value = await fetchContest(contestId.value)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load contest'
  } finally {
    loading.value = false
  }
})
```

Guard the main contest section with `v-if="contest"` and use `contest.id` in `joinContest()`.

- [ ] **Step 5: Update `ContestLeaderboard.vue`**

Replace static rows with:

```ts
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import LeaderboardTable from '@/components/crypto/LeaderboardTable.vue'
import { fetchContestLeaderboard } from '@/services/cryptoContestApi'
import type { LeaderboardRow } from '@/types/crypto'

const route = useRoute()
const contestId = computed(() => String(route.params.contestId || 'practice-arena'))
const rows = ref<LeaderboardRow[]>([])
const loading = ref(true)
const loadError = ref('')

onMounted(async () => {
  try {
    rows.value = await fetchContestLeaderboard(contestId.value)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load leaderboard'
  } finally {
    loading.value = false
  }
})
```

If `LeaderboardTable.vue` currently exports its own row type, align it to import `LeaderboardRow` from `src/types/crypto.ts`.

- [ ] **Step 6: Run frontend view tests**

Run:

```powershell
npm.cmd run test:unit -- src/views/__tests__/ContestDetail.test.ts src/views/__tests__/ContestLeaderboard.test.ts
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add src/views/ContestList.vue src/views/ContestDetail.vue src/views/ContestLeaderboard.vue src/views/__tests__/ContestDetail.test.ts src/views/__tests__/ContestLeaderboard.test.ts src/components/crypto/LeaderboardTable.vue
git commit -m "feat: load contest pages from backend"
```

---

## Task 7: Admin Contest UI Uses Backend Data

**Files:**
- Modify: `src/views/Admin/components/TabContests.vue`
- Modify: `src/views/Admin/components/TabContestParticipants.vue`
- Modify: `src/services/cryptoContestApi.ts`
- Modify: `src/types/crypto.ts`

- [ ] **Step 1: Add API functions for admin list and status**

Add to `src/services/cryptoContestApi.ts`:

```ts
export async function fetchAdminCryptoContests(): Promise<Contest[]> {
  const contests = await backendFetch<BackendContest[]>(BACKEND_URL, '/api/admin/crypto/contests', {
    headers: adminHeaders(),
  })
  return contests.map(mapContest)
}

export async function setAdminCryptoContestStatus(contestId: string, status: string): Promise<Contest> {
  const contest = await backendFetch<BackendContest>(
    BACKEND_URL,
    `/api/admin/crypto/contests/${encodeURIComponent(contestId)}/status?status=${encodeURIComponent(status)}`,
    {
      method: 'PUT',
      headers: adminHeaders(),
    },
  )
  return mapContest(contest)
}
```

- [ ] **Step 2: Update admin contest tab**

Replace `CRYPTO_CONTESTS` in `TabContests.vue` with:

```ts
import { onMounted, ref } from 'vue'

import {
  createAdminCryptoContest,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
} from '@/services/cryptoContestApi'
import type { Contest, CryptoSymbol, RawContestStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const loading = ref(false)
const error = ref('')
const form = ref({
  slug: '',
  title: '',
  mode: 'contest' as const,
  status: 'draft' as const,
  initialBalance: 10000,
  symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
})

async function loadContests() {
  loading.value = true
  error.value = ''
  try {
    contests.value = await fetchAdminCryptoContests()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contests'
  } finally {
    loading.value = false
  }
}

async function createContest() {
  const symbols = form.value.symbolsText.split(',').map((item) => item.trim()).filter(Boolean) as CryptoSymbol[]
  const created = await createAdminCryptoContest({
    slug: form.value.slug,
    title: form.value.title,
    mode: form.value.mode,
    status: form.value.status,
    initialBalance: form.value.initialBalance,
    symbols,
  })
  contests.value = [created, ...contests.value]
}

async function changeStatus(contest: Contest, status: RawContestStatus) {
  const updated = await setAdminCryptoContestStatus(contest.id, status)
  contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
}

onMounted(loadContests)
```

Keep layout restrained: table first, compact create form below or above, no large redesign.

- [ ] **Step 3: Participant tab temporary scope**

Until backend participant endpoints are added, update `TabContestParticipants.vue` to remove hardcoded wallet rows and show a neutral empty state:

```vue
<p class="text-sm text-gray-500 dark:text-gray-400">
  Participant management will use the leaderboard and account data API in the next phase.
</p>
```

This prevents fake participant rows from appearing as real data.

- [ ] **Step 4: Run frontend tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: all frontend tests pass and production build succeeds.

- [ ] **Step 5: Commit**

```powershell
git add src/views/Admin/components/TabContests.vue src/views/Admin/components/TabContestParticipants.vue src/services/cryptoContestApi.ts src/types/crypto.ts
git commit -m "feat: manage crypto contests from admin api"
```

---

## Task 8: End-To-End Verification And Docs

**Files:**
- Modify: `README.md`
- Modify: `backend_v2/.env.example` if new settings are added during implementation.

- [ ] **Step 1: Run backend focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_contests.py backend_v2\tests\test_crypto_trading_routes.py backend_v2\tests\test_admin_users.py -q
```

Expected: PASS.

- [ ] **Step 2: Run frontend tests**

Run:

```powershell
npm.cmd run test:unit
```

Expected: PASS.

- [ ] **Step 3: Run production build**

Run:

```powershell
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 4: Manual smoke checks**

Start backend and frontend if they are not running:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend_v2.src.main:app --reload --host 127.0.0.1 --port 8000
npm.cmd run dev -- --host 127.0.0.1
```

Check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/crypto/contests
Invoke-RestMethod http://127.0.0.1:8000/api/crypto/contests/practice-arena
Invoke-RestMethod http://127.0.0.1:8000/api/crypto/contests/practice-arena/leaderboard
```

Browser check:

- `/contests` shows backend contests.
- `/contests/practice-arena` shows backend title, symbols, dates, and join button.
- `/contests/practice-arena/leaderboard` shows backend rows.
- `/admin?tab=contests` shows backend contests and can create a draft contest when logged in as admin.

- [ ] **Step 5: Update README**

Add a short section:

```markdown
### Crypto Contest Data

- MySQL stores users, contests, participants, virtual balances, positions, orders, and fills.
- DuckDB stores Binance market candles and precomputed indicators.
- Public contest APIs live under `/api/crypto/contests`.
- Admin contest APIs live under `/api/admin/crypto/contests` and require an admin JWT.
- Admins can create contests and change contest status, but cannot edit user trading results.
```

- [ ] **Step 6: Commit docs**

```powershell
git add README.md backend_v2/.env.example
git commit -m "docs: document crypto contest data flow"
```

---

## Self-Review

- Spec coverage: The plan covers backend public contests, admin contest creation/status control, frontend replacement of hardcoded contest data, leaderboard API, tests, build, and README. It deliberately leaves detailed participant moderation endpoints for a later phase because the immediate goal is to remove fake contest and leaderboard data first.
- Placeholder scan: No task uses open-ended TODO/TBD language. Each implementation task includes file paths, commands, and concrete expected results.
- Type consistency: Backend uses `initial_balance` and frontend maps to `initialCapital`; backend uses `trade_count` and frontend maps to `tradeCount`; public `ContestStatus` remains `practice | upcoming | active | ended`, while admin raw status uses `RawContestStatus`.
