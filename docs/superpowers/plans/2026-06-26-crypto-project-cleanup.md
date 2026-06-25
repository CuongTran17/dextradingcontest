# Crypto Project Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the reused stock/payment backend from the production runtime, move unused frontend features to a reference-only legacy directory, and preserve the existing crypto application and MySQL data.

**Architecture:** Keep one FastAPI application containing authentication, health, crypto market data, crypto trading, and minimal user administration. Keep the existing Alembic chain and physical MySQL tables unchanged, but define production SQLAlchemy metadata using only `users` and crypto tables. Move unused Vue feature code outside `src` so Vite and TypeScript compile only the crypto product.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, DuckDB, HTTPX, Vue 3, TypeScript, Vite, Vitest

---

## File Structure

### Production Backend

- `backend_v2/src/database/base.py`: shared SQLAlchemy declarative base.
- `backend_v2/src/database/user_models.py`: retained `users` table mapping only.
- `backend_v2/src/database/crypto_models.py`: crypto contest and trading models using the shared base.
- `backend_v2/src/database/db.py`: MySQL engines, sessions, Alembic startup, and no legacy auto-DDL.
- `backend_v2/src/api/auth.py`: authentication and profile endpoints.
- `backend_v2/src/api/admin.py`: minimal user list, role, lock, and unlock endpoints.
- `backend_v2/src/routes/health.py`: MySQL and migration health only.
- `backend_v2/src/routes/crypto.py`: Binance/DuckDB market data.
- `backend_v2/src/routes/crypto_trading.py`: authenticated simulated trading.
- `backend_v2/src/main.py`: crypto-only application assembly.
- `backend_v2/src/settings.py`: crypto-only environment settings.

### Reference Frontend

- `legacy/frontend/views/`: stock, DNSE, AI, premium, and old portfolio views.
- `legacy/frontend/services/`: stock/DNSE services.
- `legacy/frontend/realtime/`: old stock realtime manager.
- `legacy/frontend/stores/`: old stock stores.
- `legacy/frontend/composables/`: stock-only composables.
- `legacy/frontend/constants/`: stock-only constants.
- `legacy/frontend/README.md`: explains that files are reference-only and not buildable in place.

### Production Frontend

- `src/router/index.ts`: crypto/auth/profile/admin routes only.
- `src/services/authApi.ts`: authentication and retained user-admin methods only.
- `src/components/layout/AppSidebar.vue`: no premium navigation.
- `src/views/Admin/AdminDashboard.vue`: crypto contest admin foundation.

## Guardrails

- Do not run `DROP DATABASE`, `DROP TABLE`, `alembic downgrade`, or destructive SQL.
- Do not modify the revision identifiers or `down_revision` values of existing migrations.
- Do not delete unrelated untracked workspace files.
- Use `git mv` for tracked frontend reference files.
- Run targeted tests after every deletion group.

### Task 1: Lock the Crypto-Only Baseline

**Files:**
- Create: `backend_v2/tests/test_crypto_app_surface.py`
- Modify: `src/router/__tests__/index.test.ts`
- Test: `backend_v2/tests/test_crypto_app_surface.py`
- Test: `src/router/__tests__/index.test.ts`

- [ ] **Step 1: Write backend surface tests**

Create `backend_v2/tests/test_crypto_app_surface.py`:

```python
from src.main import app


def test_application_exposes_only_retained_router_prefixes():
    paths = {route.path for route in app.routes}

    assert "/api/auth/login" in paths
    assert "/api/crypto/assets" in paths
    assert "/api/crypto/orders/market" in paths
    assert "/api/health" in paths


def test_application_does_not_expose_legacy_routes():
    paths = {route.path for route in app.routes}
    forbidden_prefixes = (
        "/api/payment",
        "/api/portfolio",
        "/api/stocks",
        "/api/analysis",
        "/api/dnse",
        "/api/etl",
        "/api/market-indices",
        "/api/news",
        "/api/events",
        "/api/ws",
    )

    assert not any(
        path.startswith(prefix)
        for path in paths
        for prefix in forbidden_prefixes
    )
```

- [ ] **Step 2: Update router expectations before implementation**

In `src/router/__tests__/index.test.ts`, remove `'/premium'` from the authenticated-route cases and add:

```typescript
it.each(['/premium', '/premium/checkout', '/premium/sepay-return'])(
  'removes legacy premium route %s',
  async (path) => {
    const route = await navigateAsGuest(path)

    expect(route.name).toBe('CryptoDashboard')
  },
)
```

- [ ] **Step 3: Run tests to verify the new expectations fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_app_surface.py -q
npm.cmd run test:unit -- src/router/__tests__/index.test.ts
```

Expected: backend fails because legacy routes are still registered; frontend fails because premium routes still exist.

- [ ] **Step 4: Record the current retained baseline**

Run:

```powershell
$tests = git ls-files 'backend_v2/tests/*.py' | Where-Object { $_ -notmatch '__init__' }
.\.venv\Scripts\python.exe -m pytest $tests -q
npm.cmd run test:unit
npm.cmd run build
```

Expected before cleanup: existing tracked backend tests pass except the intentionally failing surface test; existing frontend tests and build pass except the new router expectation.

- [ ] **Step 5: Commit the baseline tests**

```powershell
git add backend_v2/tests/test_crypto_app_surface.py src/router/__tests__/index.test.ts
git commit -m "test: define crypto-only application surface"
```

### Task 2: Move Legacy Frontend Features Out of Production

**Files:**
- Create: `legacy/frontend/README.md`
- Move: stock/DNSE/AI/premium frontend files listed below
- Modify: `src/App.vue`
- Modify: `src/main.ts`
- Modify: `src/router/index.ts`
- Modify: `src/components/layout/AppSidebar.vue`
- Test: `src/router/__tests__/index.test.ts`
- Test: `src/components/layout/__tests__/AppSidebar.test.ts`

- [ ] **Step 1: Add a sidebar regression test**

Add to `src/components/layout/__tests__/AppSidebar.test.ts`:

```typescript
it('does not render premium or stock navigation', () => {
  const wrapper = mount(AppSidebar)

  expect(wrapper.text()).not.toContain('Premium')
  expect(wrapper.text()).not.toContain('Stocks')
  expect(wrapper.text()).not.toContain('DNSE')
})
```

- [ ] **Step 2: Run the sidebar test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/components/layout/__tests__/AppSidebar.test.ts
```

Expected: FAIL because `Premium` is still rendered for authenticated non-premium users.

- [ ] **Step 3: Move view files with `git mv`**

Create directories and move these tracked files:

```powershell
New-Item -ItemType Directory -Force legacy\frontend\views | Out-Null
git mv src/views/DnseTickSandbox.vue legacy/frontend/views/
git mv src/views/MarketOverview.vue legacy/frontend/views/
git mv src/views/MyPortfolio.vue legacy/frontend/views/
git mv src/views/NewsEvents.vue legacy/frontend/views/
git mv src/views/PortfolioAlerts.vue legacy/frontend/views/
git mv src/views/PremiumCheckout.vue legacy/frontend/views/
git mv src/views/PremiumSePayReturn.vue legacy/frontend/views/
git mv src/views/PremiumUpgrade.vue legacy/frontend/views/
git mv src/views/StockAIAnalysis.vue legacy/frontend/views/
git mv src/views/StockDashboard.vue legacy/frontend/views/
git mv src/views/StockDetail.vue legacy/frontend/views/
git mv src/views/StockScreener.vue legacy/frontend/views/

New-Item -ItemType Directory -Force legacy\frontend\admin | Out-Null
git mv src/views/Admin/components/TabEtlMonitor.vue legacy/frontend/admin/
git mv src/views/Admin/components/TabFlashSales.vue legacy/frontend/admin/
git mv src/views/Admin/components/TabPortfolios.vue legacy/frontend/admin/
git mv src/views/Admin/components/TabPromotions.vue legacy/frontend/admin/
git mv src/views/Admin/components/TabRevenue.vue legacy/frontend/admin/
git mv src/views/Admin/components/TabUsers.vue legacy/frontend/admin/

git mv src/components/stock legacy/frontend/
```

Also move legacy-only tests:

```powershell
New-Item -ItemType Directory -Force legacy\frontend\tests | Out-Null
git mv src/views/__tests__/PortfolioAlerts.test.ts legacy/frontend/tests/
git mv src/views/__tests__/StockDetail.test.ts legacy/frontend/tests/
```

- [ ] **Step 4: Move feature-specific modules**

Move tracked stock-only modules:

```powershell
New-Item -ItemType Directory -Force legacy\frontend\services | Out-Null
git mv src/services/dnseApi.ts legacy/frontend/services/
git mv src/services/dnseTickSandboxApi.ts legacy/frontend/services/
git mv src/services/dnseWebSocket.ts legacy/frontend/services/
git mv src/services/marketIndexTechnical.ts legacy/frontend/services/
git mv src/services/stockBackendApi.ts legacy/frontend/services/

git mv src/realtime legacy/frontend/

git mv src/stores legacy/frontend/

New-Item -ItemType Directory -Force legacy\frontend\composables | Out-Null
git mv src/composables/usePriceSubscription.ts legacy/frontend/composables/
git mv src/composables/useStockData.ts legacy/frontend/composables/

New-Item -ItemType Directory -Force legacy\frontend\constants | Out-Null
git mv src/constants/marketSectors.ts legacy/frontend/constants/
git mv src/constants/stockAiAnalysis.ts legacy/frontend/constants/
git mv src/constants/__tests__/marketSectors.test.ts legacy/frontend/tests/
git mv src/constants/__tests__/stockAiAnalysis.test.ts legacy/frontend/tests/

New-Item -ItemType Directory -Force legacy\frontend\service-tests | Out-Null
git mv src/services/__tests__/dnseTickSandboxApi.test.ts legacy/frontend/service-tests/
git mv src/services/__tests__/dnseWebSocket.test.ts legacy/frontend/service-tests/
git mv src/services/__tests__/marketIndexTechnical.test.ts legacy/frontend/service-tests/
git mv src/services/__tests__/stockBackendApi.test.ts legacy/frontend/service-tests/
```

- [ ] **Step 5: Remove premium routes and guards**

Delete the three premium route objects from `src/router/index.ts`.

Change:

```typescript
import { isAdmin, isLoggedIn, isPremium } from '@/services/authApi'
```

to:

```typescript
import { isAdmin, isLoggedIn } from '@/services/authApi'
```

Delete:

```typescript
if (to.meta.requiresPremium && !isPremium()) {
  return next({ name: 'PremiumUpgrade' })
}
```

- [ ] **Step 6: Remove stock realtime and ApexCharts bootstrapping**

Replace the script in `src/App.vue` with:

```vue
<script setup lang="ts">
import ThemeProvider from './components/layout/ThemeProvider.vue'
import SidebarProvider from './components/layout/SidebarProvider.vue'
</script>
```

In `src/main.ts`, remove:

```typescript
import VueApexCharts from 'vue3-apexcharts'
app.use(VueApexCharts)
```

- [ ] **Step 7: Remove premium sidebar behavior**

In `src/components/layout/AppSidebar.vue`:

```typescript
import {
  BarChartIcon,
  BoxCubeIcon,
  HorizontalDots,
  LayoutDashboardIcon,
  ListIcon,
  LogoutIcon,
  UserCircleIcon,
} from '@/icons'
import { isAdmin, isLoggedIn, logout as authLogout } from '@/services/authApi'
```

Remove the `isPremium()` branch that appends the Premium menu item.

- [ ] **Step 8: Add the legacy README**

Create `legacy/frontend/README.md`:

```markdown
# Legacy Frontend Reference

These files came from the earlier Vietnam stock application.

They are retained only for implementation and visual reference. They are outside `src`, are
not registered in the production router, and are not compiled or tested by the crypto
application. Imports inside these files may no longer resolve.
```

- [ ] **Step 9: Verify frontend isolation**

Run:

```powershell
rg -n "Premium|Stock|DNSE|VNStock|realtimeManager|VueApexCharts" src
npm.cmd run test:unit -- src/router/__tests__/index.test.ts src/components/layout/__tests__/AppSidebar.test.ts
npm.cmd run build
```

Expected: `rg` finds no production navigation references; tests and build pass.

- [ ] **Step 10: Commit frontend isolation**

```powershell
git add src legacy/frontend
git commit -m "refactor: isolate legacy frontend features"
```

### Task 3: Separate Retained Database Metadata From Legacy Models

**Files:**
- Create: `backend_v2/src/database/base.py`
- Create: `backend_v2/src/database/user_models.py`
- Modify: `backend_v2/src/database/crypto_models.py`
- Modify: `backend_v2/src/database/db.py`
- Modify: `backend_v2/src/api/auth.py`
- Modify: `backend_v2/src/routes/crypto_trading.py`
- Modify: `backend_v2/alembic/env.py`
- Test: `backend_v2/tests/test_crypto_models.py`
- Test: `backend_v2/tests/test_crypto_app_surface.py`

- [ ] **Step 1: Write metadata isolation tests**

Add to `backend_v2/tests/test_crypto_models.py`:

```python
from src.database.base import Base
from src.database.user_models import User


def test_production_metadata_contains_only_user_and_crypto_tables():
    assert User.__tablename__ == "users"
    assert {
        "users",
        "crypto_assets",
        "contests",
        "contest_assets",
        "contest_participants",
        "trading_accounts",
        "account_balances",
        "crypto_positions",
        "crypto_orders",
        "crypto_trade_fills",
    } == set(Base.metadata.tables)
```

- [ ] **Step 2: Run the metadata test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_models.py -q
```

Expected: FAIL because `base.py` and `user_models.py` do not exist.

- [ ] **Step 3: Create the shared base**

Create `backend_v2/src/database/base.py`:

```python
from sqlalchemy.orm import declarative_base

Base = declarative_base()
```

- [ ] **Step 4: Create the retained user mapping**

Create `backend_v2/src/database/user_models.py` with the existing `User` columns, retaining the
database-compatible role enum:

```python
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Enum, Integer, String
from sqlalchemy.dialects.mysql import LONGTEXT

from src.database.base import Base


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
    created_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
```

Do not add relationships to legacy subscription or stock portfolio tables.

- [ ] **Step 5: Point retained models and APIs to the new modules**

Change `backend_v2/src/database/crypto_models.py`:

```python
from src.database.base import Base
```

Change both `backend_v2/src/api/auth.py` and
`backend_v2/src/routes/crypto_trading.py`:

```python
from src.database.user_models import User
```

Change `backend_v2/alembic/env.py`:

```python
from src.database.base import Base  # noqa: E402
from src.database import crypto_models as _crypto_models  # noqa: E402,F401
from src.database import user_models as _user_models  # noqa: E402,F401
```

- [ ] **Step 6: Reduce database initialization**

In `backend_v2/src/database/db.py`, import:

```python
from src.database.base import Base
from src.database import crypto_models as _crypto_models  # noqa: F401
from src.database import user_models as _user_models  # noqa: F401
```

Delete `_ensure_payload_columns_longtext`, `_ensure_subscription_columns`,
`_ensure_user_portfolio_columns`, and their calls. Keep migration startup and session
factories. Keep `_ensure_user_profile_columns` only inside the disabled compatibility
`DB_LEGACY_AUTO_DDL` path until Task 6 removes that setting.

- [ ] **Step 7: Verify metadata and existing MySQL compatibility**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_models.py backend_v2\tests\test_crypto_accounts.py backend_v2\tests\test_crypto_trading_routes.py -q
Set-Location backend_v2
..\.venv\Scripts\python.exe -m alembic current
Set-Location ..
```

Expected: tests pass and Alembic reports `20260625_0003 (head)` without applying destructive SQL.

- [ ] **Step 8: Commit metadata separation**

```powershell
git add backend_v2/src/database backend_v2/src/api/auth.py backend_v2/src/routes/crypto_trading.py backend_v2/alembic/env.py backend_v2/tests/test_crypto_models.py
git commit -m "refactor: isolate crypto database metadata"
```

### Task 4: Replace Legacy Admin API With Minimal User Administration

**Files:**
- Replace: `backend_v2/src/api/admin.py`
- Create: `backend_v2/tests/test_admin_users.py`
- Modify: `src/services/authApi.ts`
- Test: `backend_v2/tests/test_admin_users.py`

- [ ] **Step 1: Write admin endpoint tests**

Create `backend_v2/tests/test_admin_users.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import router


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_admin_router_has_only_user_management_paths():
    client = make_client()
    paths = {route.path for route in client.app.routes}

    assert "/api/admin/users" in paths
    assert "/api/admin/users/{user_id}/role" in paths
    assert "/api/admin/users/{user_id}/lock" in paths
    assert "/api/admin/users/{user_id}/unlock" in paths
    assert not any("/promotions" in path for path in paths)
    assert not any("/flash-sales" in path for path in paths)
    assert not any("/sales-stats" in path for path in paths)
    assert not any("/user-portfolios" in path for path in paths)
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py -q
```

Expected: FAIL because legacy paths remain.

- [ ] **Step 3: Replace `admin.py` with user-only endpoints**

Retain `list_users`, `update_user_role`, `lock_user`, and `unlock_user`. Import only:

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from src.api.auth import require_role
from src.database.db import get_db
from src.database.user_models import User
```

Allow role values `user` and `admin` for future changes while continuing to read existing
`premium` rows:

```python
if role not in {"user", "admin"}:
    raise HTTPException(status_code=400, detail="Role must be user or admin")
```

- [ ] **Step 4: Reduce frontend auth service**

In `src/services/authApi.ts`:

- Keep `UserInfo`, `AuthResponse`, token helpers, auth/profile calls, `isAdmin`,
  `getAdminUsers`, `updateUserRole`, `lockUser`, and `unlockUser`.
- Keep `'premium'` in the `UserInfo.role` union for compatibility with existing rows.
- Delete payment, subscription, stock portfolio, promotion, flash sale, sales statistics, and
  ETL interfaces and methods.
- Delete `isPremium`.
- Change the file header to:

```typescript
/**
 * JWT authentication, user profile, and user administration API.
 */
```

- [ ] **Step 5: Verify retained auth and admin behavior**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_admin_users.py backend_v2\tests\test_crypto_trading_routes.py -q
npm.cmd run type-check
```

Expected: tests and type check pass.

- [ ] **Step 6: Commit admin cleanup**

```powershell
git add backend_v2/src/api/admin.py backend_v2/tests/test_admin_users.py src/services/authApi.ts
git commit -m "refactor: keep crypto user administration only"
```

### Task 5: Assemble a Crypto-Only FastAPI Application

**Files:**
- Replace: `backend_v2/src/jobs.py`
- Replace: `backend_v2/src/main.py`
- Modify: `backend_v2/src/routes/health.py`
- Test: `backend_v2/tests/test_crypto_app_surface.py`

- [ ] **Step 1: Simplify the lifespan**

Replace `backend_v2/src/jobs.py` with:

```python
from contextlib import asynccontextmanager
from typing import Any, Callable


def build_lifespan(*, init_db: Callable[[], None]):
    @asynccontextmanager
    async def lifespan(app: Any):
        del app
        init_db()
        yield

    return lifespan
```

- [ ] **Step 2: Replace `main.py` imports and router assembly**

Use only:

```python
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.admin import router as admin_router
from src.api.auth import router as auth_router
from src.api_errors import register_error_handlers
from src.database.db import init_db
from src.jobs import build_lifespan
from src.observability import RequestIdMiddleware
from src.routes.crypto import router as crypto_router
from src.routes.crypto_trading import router as crypto_trading_router
from src.routes.health import router as health_router
from src.settings import get_settings
```

Create the app as:

```python
lifespan = build_lifespan(init_db=init_db)
app = FastAPI(
    title="Crypto Trading Contest API",
    lifespan=lifespan,
    version="1.0.0",
)
```

Register only `auth_router`, `admin_router`, `health_router`, `crypto_router`, and
`crypto_trading_router`.

- [ ] **Step 3: Remove Redis from readiness**

In `backend_v2/src/routes/health.py`, delete the Redis import and `_check_redis`.

Use:

```python
checks = {
    "database": await _check_database(),
    "migrations": await _check_migrations(),
}
```

Set the liveness service to `"crypto-trading-contest-api"`.

- [ ] **Step 4: Run application surface and startup tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_app_surface.py backend_v2\tests\test_crypto_routes.py backend_v2\tests\test_crypto_trading_routes.py -q
.\.venv\Scripts\python.exe -c "from backend_v2.src.main import app; print(app.title)"
```

Expected: tests pass and output is `Crypto Trading Contest API`.

- [ ] **Step 5: Commit application assembly**

```powershell
git add backend_v2/src/main.py backend_v2/src/jobs.py backend_v2/src/routes/health.py backend_v2/tests/test_crypto_app_surface.py
git commit -m "refactor: assemble crypto-only backend"
```

### Task 6: Delete Legacy Backend Modules and Tests

**Files:**
- Delete: legacy backend API, routes, services, database modules, and tests
- Modify: `backend_v2/src/database/db.py`

- [ ] **Step 1: Prove retained code has no legacy imports**

Run:

```powershell
rg -n "src\.(cache|market_data_status|redis_db)|src\.api\.(payment|portfolio)|src\.routes\.(analysis|dnse_ticks|etl_status|internal|market|stocks|websocket)|src\.services\.(ai_|dnse_|etl_|fundamental|kaggle|last_known|market_session|mock_intraday|technical|vnstock)|market_duckdb|data_lake|database\.models" backend_v2/src
```

Expected: no matches in retained production modules. Fix retained imports before deleting files.

- [ ] **Step 2: Delete legacy API and routes**

Delete with `apply_patch`:

```text
backend_v2/src/api/payment.py
backend_v2/src/api/portfolio.py
backend_v2/src/routes/analysis.py
backend_v2/src/routes/dnse_ticks.py
backend_v2/src/routes/etl_status.py
backend_v2/src/routes/internal.py
backend_v2/src/routes/market.py
backend_v2/src/routes/stocks.py
backend_v2/src/routes/websocket.py
```

- [ ] **Step 3: Delete legacy services**

Delete:

```text
backend_v2/src/services/ai_analysis.py
backend_v2/src/services/ai_context.py
backend_v2/src/services/ai_jobs.py
backend_v2/src/services/ai_response.py
backend_v2/src/services/dnse_market_data.py
backend_v2/src/services/dnse_realtime_provider.py
backend_v2/src/services/etl_marker.py
backend_v2/src/services/fundamental_fetcher.py
backend_v2/src/services/kaggle_client.py
backend_v2/src/services/last_known_tick_reader.py
backend_v2/src/services/market_session.py
backend_v2/src/services/mock_intraday_streamer.py
backend_v2/src/services/technical_indicators.py
backend_v2/src/services/vnstock_error_utils.py
backend_v2/src/services/vnstock_fetcher.py
backend_v2/src/services/vnstock_rate_limiter.py
```

- [ ] **Step 4: Delete legacy database and helper modules**

Delete:

```text
backend_v2/src/cache.py
backend_v2/src/market_data_status.py
backend_v2/src/redis_db.py
backend_v2/src/utils.py
backend_v2/src/database/data_lake.py
backend_v2/src/database/market_duckdb.py
backend_v2/src/database/models.py
backend_v2/src/database/redis_db.py
```

- [ ] **Step 5: Remove legacy auto-DDL**

In `backend_v2/src/database/db.py`, delete:

- `Base.metadata.create_all` retry helpers.
- information-schema column/index helpers.
- `_ensure_user_profile_columns`.
- `_run_legacy_auto_ddl`.
- all `DB_LEGACY_AUTO_DDL` branches.

Keep `init_db()` as:

```python
def init_db():
    if not settings.db_migrations_enabled:
        logger.warning("DB_MIGRATIONS_ENABLED=false; database migrations were not applied.")
        return
    _run_migrations()
```

- [ ] **Step 6: Delete legacy tests**

Delete:

```text
backend_v2/tests/test_dnse_market_data.py
backend_v2/tests/test_dnse_realtime_provider.py
backend_v2/tests/test_stocks_dnse_integration.py
```

Do not touch untracked `backend_v2/tests/test_admin_reports.py`; it is outside tracked cleanup
scope unless it becomes intentionally added later.

- [ ] **Step 7: Verify imports and retained tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend_v2\src
$tests = git ls-files 'backend_v2/tests/*.py' | Where-Object { $_ -notmatch '__init__' }
.\.venv\Scripts\python.exe -m pytest $tests -q
```

Expected: compile succeeds and all tracked retained tests pass.

- [ ] **Step 8: Commit backend deletion**

```powershell
git add -A backend_v2/src backend_v2/tests
git commit -m "refactor: remove legacy stock backend"
```

### Task 7: Reduce Settings, Environment, Dependencies, and Scripts

**Files:**
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Modify: `backend_v2/requirements.txt`
- Modify: `package.json`
- Modify: `package-lock.json`
- Modify: `vite.config.ts`
- Test: `backend_v2/tests/test_crypto_app_surface.py`

- [ ] **Step 1: Add a settings-surface test**

Add to `backend_v2/tests/test_crypto_app_surface.py`:

```python
from src.settings import Settings


def test_settings_expose_only_crypto_runtime_configuration():
    fields = set(Settings.model_fields)

    assert {"mysql_url", "mysql_async_url", "crypto_duckdb_path", "jwt_secret"} <= fields
    assert "dnse_market_base_url" not in fields
    assert "kaggle_api_url" not in fields
    assert "sepay_secret_key" not in fields
    assert "etl_symbols" not in fields
    assert "duckdb_path" not in fields
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_app_surface.py::test_settings_expose_only_crypto_runtime_configuration -q
```

Expected: FAIL because legacy settings remain.

- [ ] **Step 3: Reduce `Settings`**

Keep only:

```python
mysql_url: str = "mysql+mysqlconnector://root:@localhost/crypto_dex"
mysql_async_url: str | None = None
crypto_duckdb_path: str = "lake/warehouse/crypto_market.duckdb"
db_migrations_enabled: bool = True
jwt_secret: str = "change_me_to_a_long_random_string_at_least_32_chars"
jwt_algorithm: str = "HS256"
jwt_expire_hours: int = Field(default=24, ge=1, le=24 * 30)
frontend_url: str = "http://localhost:5174"
backend_url: str = "http://localhost:8000"
```

Keep `resolved_mysql_async_url`, `allowed_cors_origins`, `warn_if_insecure`, and
`get_settings`. Delete all ETL, stock, DNSE, AI, Redis, payment, premium, callback, and legacy
DuckDB settings.

- [ ] **Step 4: Update `.env.example`**

Use:

```dotenv
# MySQL
MYSQL_URL=mysql+mysqlconnector://root:YOUR_PASSWORD@localhost/crypto_dex
MYSQL_ASYNC_URL=mysql+aiomysql://root:YOUR_PASSWORD@localhost/crypto_dex
DB_MIGRATIONS_ENABLED=true

# Crypto market warehouse
CRYPTO_DUCKDB_PATH=lake/warehouse/crypto_market.duckdb

# Authentication
JWT_SECRET=replace_with_a_long_random_secret_before_running
JWT_EXPIRE_HOURS=24

# Application URLs
FRONTEND_URL=http://localhost:5174
BACKEND_URL=http://localhost:8000
```

- [ ] **Step 5: Reduce Python dependencies**

Set `backend_v2/requirements.txt` to:

```text
fastapi>=0.116.0
uvicorn[standard]>=0.34.0
sqlalchemy>=2.0.0
alembic>=1.13.0
mysql-connector-python>=8.0.0
aiomysql>=0.2.0
python-dotenv>=1.0.0
pydantic-settings>=2.4.0
PyJWT>=2.8.0
passlib[bcrypt]>=1.7.4
email-validator>=2.2.0
httpx>=0.24.0
pandas>=2.2.0
pyarrow>=15.0.0
duckdb>=1.1.0
```

- [ ] **Step 6: Remove obsolete package scripts**

From `package.json`, delete:

```json
"backend:ngrok": "...",
"etl:update": "...",
"dev:after-etl": "..."
```

Keep `backend:dev` and `crypto:backfill`.

- [ ] **Step 7: Remove stock-only chart dependencies**

Run:

```powershell
npm.cmd uninstall apexcharts vue3-apexcharts
```

This updates both `package.json` and `package-lock.json`.

In `vite.config.ts`, delete:

```typescript
apexcharts: ['apexcharts', 'vue3-apexcharts'],
```

from `manualChunks`.

- [ ] **Step 8: Verify configuration and dependency references**

Run:

```powershell
rg -n "VNSTOCK|DNSE|ETL_|KAGGLE|SEPAY|PREMIUM|REDIS_URL|DUCKDB_PATH=" backend_v2/src backend_v2/.env.example package.json
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_app_surface.py -q
npm.cmd run build
```

Expected: no legacy configuration matches; tests and build pass.

- [ ] **Step 9: Commit configuration cleanup**

```powershell
git add backend_v2/src/settings.py backend_v2/.env.example backend_v2/requirements.txt package.json package-lock.json vite.config.ts backend_v2/tests/test_crypto_app_surface.py
git commit -m "chore: reduce crypto runtime configuration"
```

### Task 8: Refresh Documentation and Verify Existing Data

**Files:**
- Modify: `README.md`
- Create: `docs/legacy-cleanup.md`

- [ ] **Step 1: Document the cleaned architecture**

Update `README.md` so it states:

- The backend is crypto-only.
- MySQL legacy tables may still physically exist but are not used.
- `legacy/frontend/` is reference-only.
- Payment, premium, stock, DNSE, ETL, AI, and real exchange execution are not supported.
- The next phase is Binance WebSocket realtime ingestion.

- [ ] **Step 2: Add a cleanup inventory**

Create `docs/legacy-cleanup.md`:

```markdown
# Legacy Cleanup Inventory

## Removed From Runtime

- Vietnam stock and DNSE market data
- VNStock ingestion and ETL
- Stock AI and Kaggle integration
- News, events, and stock technical analysis
- Payment, premium subscriptions, promotions, and flash sales
- Stock portfolio APIs and stock realtime WebSockets

## Retained

- Existing MySQL database and Alembic history
- Authentication and user profiles
- Crypto contest and virtual trading tables
- Binance REST market data
- DuckDB crypto candle warehouse
- Shared frontend layout and CSS

## Reference Code

Old frontend feature files are stored under `legacy/frontend/` and are excluded from the
production build.
```

- [ ] **Step 3: Verify the database was not modified destructively**

Run:

```powershell
Set-Location backend_v2
..\.venv\Scripts\python.exe -m alembic current
Set-Location ..
```

Expected: `20260625_0003 (head)`.

Run a read-only query:

```powershell
Set-Location backend_v2
@'
from src.database.db import SessionLocal
from src.database.crypto_models import Contest, CryptoAsset

with SessionLocal() as db:
    print({
        "contests": db.query(Contest).count(),
        "crypto_assets": db.query(CryptoAsset).count(),
    })
'@ | ..\.venv\Scripts\python.exe -
Set-Location ..
```

Expected: at least one contest and five crypto assets.

- [ ] **Step 4: Run the full retained verification suite**

Run:

```powershell
$tests = git ls-files 'backend_v2/tests/*.py' | Where-Object { $_ -notmatch '__init__' }
.\.venv\Scripts\python.exe -m pytest $tests -q
npm.cmd run test:unit
npm.cmd run build
git diff --check
```

Expected: all retained backend tests pass, all frontend tests pass, build succeeds, and diff
check is clean.

- [ ] **Step 5: Run crypto API smoke checks**

With the backend running:

```powershell
Invoke-RestMethod http://localhost:8000/api/health/live
Invoke-RestMethod http://localhost:8000/api/crypto/prices/latest
Invoke-RestMethod "http://localhost:8000/api/crypto/candles?symbol=BTCUSDT&timeframe=1h&limit=3"
Invoke-RestMethod "http://localhost:8000/api/crypto/orderbook?symbol=ETHUSDT&limit=20"
```

Expected: health is `ok`, prices are positive, candles contain three chronological rows, and
the order book source is `binance`.

- [ ] **Step 6: Commit documentation**

```powershell
git add README.md docs/legacy-cleanup.md
git commit -m "docs: document crypto-only project structure"
```

### Task 9: Final Browser Verification

**Files:**
- No production changes expected

- [ ] **Step 1: Start the development services**

Run backend:

```powershell
npm.cmd run backend:dev
```

Run frontend in another terminal:

```powershell
npm.cmd run dev
```

- [ ] **Step 2: Verify production routes**

Using the in-app browser, verify:

```text
/
/trade/ETHUSDT
/contests
/portfolio
/profile
/admin
```

Expected:

- Crypto navigation is visible.
- No stock, DNSE, premium, or payment navigation appears.
- ETH price and order book use live Binance data.
- Existing authenticated account and contest data load from MySQL.

- [ ] **Step 3: Verify removed routes**

Open:

```text
/premium
/premium/checkout
/stock/FPT
```

Expected: each resolves through the catch-all route to the crypto dashboard.

- [ ] **Step 4: Check browser console and responsive layout**

Verify desktop and mobile viewports contain no import errors, failed legacy API requests, text
overlaps, or blank crypto panels.

- [ ] **Step 5: Commit any verification-only fixes separately**

If verification exposes a defect, reproduce it with a failing test, fix only that defect, and
commit:

```powershell
git add <affected-files>
git commit -m "fix: complete crypto cleanup verification"
```

If no fix is required, do not create an empty commit.
