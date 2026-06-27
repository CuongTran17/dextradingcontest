# Strict Snapshot Data Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make market data updates manual and reproducible: backend startup and read APIs never create market data, while CLI/admin ETL remain the only market snapshot/cache write paths.

**Architecture:** Add a shared market data status contract, make FastAPI lifespan read-only for market data, and convert stock/market/analysis read routes to return existing snapshot/cache data only. Frontend refresh actions will reload current snapshot data rather than request upstream refreshes, while Admin ETL Monitor remains the explicit write control.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pandas, Vue 3, TypeScript, Vite, existing ETL/parquet/MySQL cache pipeline.

---

## File Structure

- Create `backend_v2/src/market_data_status.py`: shared status constants, response metadata helpers, and refresh-disabled exception helper.
- Create `backend_v2/tests/__init__.py`: make backend tests importable by `python -m unittest`.
- Create `backend_v2/tests/test_snapshot_mode.py`: standard-library `unittest` coverage for status helpers, read-only lifespan, and guarded refresh behavior. The repository does not currently include pytest, so use `python -m unittest`.
- Modify `backend_v2/src/jobs.py`: remove market-data background tasks and embedded scheduler registration from FastAPI lifespan.
- Modify `backend_v2/src/main.py`: stop passing fetcher/fundamental preload dependencies into lifespan after `build_lifespan` is simplified.
- Modify `backend_v2/src/routes/stocks.py`: remove read-path refresh, auto refresh, and history auto-fetch fallback.
- Modify `backend_v2/src/routes/market.py`: remove direct `vnstock.Quote` fetches from read routes and read market index data from existing lake processed output.
- Modify `backend_v2/src/routes/analysis.py`: build AI context from existing cache only, with no fundamentals/news/history refresh.
- Modify `backend_v2/src/routes/internal.py`: disable `/api/debug/intraday/refresh` in snapshot mode; leave authenticated admin quote ingestion unchanged as explicit manual input.
- Modify `backend_v2/src/routes/etl_status.py`: surface shared data status values for ETL state and manual trigger responses.
- Modify `src/services/stockBackendApi.ts`: stop sending `refresh=true` on read methods; expose status metadata type.
- Modify Vue views that pass `forceRefresh` into read methods: `src/views/MarketOverview.vue`, `src/views/StockDetail.vue`, `src/views/NewsEvents.vue`, `src/views/StockAIAnalysis.vue`, and any other call sites found by `rg "forceRefresh|refresh:" src`.
- Modify `src/services/authApi.ts` and `src/views/Admin/components/TabEtlMonitor.vue`: display `ETL_RUNNING`, `ETL_FAILED`, and `STALE_SNAPSHOT` from ETL status metadata.
- Modify `README.md`: document strict snapshot mode, allowed write paths, and status codes.

## Task 1: Status Contract and Tests

**Files:**
- Create: `backend_v2/src/market_data_status.py`
- Create: `backend_v2/tests/__init__.py`
- Create: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Create the test package and failing unit test for status helpers**

Create `backend_v2/tests/__init__.py` as an empty file.

Create `backend_v2/tests/test_snapshot_mode.py` with this initial content:

```python
import unittest

from fastapi import HTTPException

from src.market_data_status import (
    DATA_AVAILABLE,
    REFRESH_DISABLED_IN_SNAPSHOT_MODE,
    MarketDataStatus,
    market_meta,
    reject_refresh_in_snapshot_mode,
)


class MarketDataStatusTests(unittest.TestCase):
    def test_status_constants_are_stable_strings(self):
        self.assertEqual(DATA_AVAILABLE, "DATA_AVAILABLE")
        self.assertEqual(REFRESH_DISABLED_IN_SNAPSHOT_MODE, "REFRESH_DISABLED_IN_SNAPSHOT_MODE")
        self.assertEqual(MarketDataStatus.STALE_SNAPSHOT, "STALE_SNAPSHOT")

    def test_market_meta_uses_stable_shape(self):
        meta = market_meta(
            DATA_AVAILABLE,
            run_id="20260514T230000",
            last_synced_at="2026-05-14T16:00:00+00:00",
            stale=True,
            message="Loaded from MySQL serving cache",
        )

        self.assertEqual(
            meta,
            {
                "data_status": "DATA_AVAILABLE",
                "run_id": "20260514T230000",
                "last_synced_at": "2026-05-14T16:00:00+00:00",
                "stale": True,
                "message": "Loaded from MySQL serving cache",
            },
        )

    def test_reject_refresh_raises_http_409(self):
        with self.assertRaises(HTTPException) as ctx:
            reject_refresh_in_snapshot_mode(True)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], "REFRESH_DISABLED_IN_SNAPSHOT_MODE")

    def test_reject_refresh_allows_false(self):
        self.assertIsNone(reject_refresh_in_snapshot_mode(False))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the test and verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
```

Expected: FAIL or ERROR because `src.market_data_status` does not exist.

- [ ] **Step 3: Add the status helper implementation**

Create `backend_v2/src/market_data_status.py`:

```python
from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import HTTPException


class MarketDataStatus(StrEnum):
    DATA_AVAILABLE = "DATA_AVAILABLE"
    NO_DATA_IN_SNAPSHOT = "NO_DATA_IN_SNAPSHOT"
    SNAPSHOT_NOT_BUILT = "SNAPSHOT_NOT_BUILT"
    REFRESH_DISABLED_IN_SNAPSHOT_MODE = "REFRESH_DISABLED_IN_SNAPSHOT_MODE"
    ETL_RUNNING = "ETL_RUNNING"
    ETL_FAILED = "ETL_FAILED"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"


DATA_AVAILABLE = MarketDataStatus.DATA_AVAILABLE
NO_DATA_IN_SNAPSHOT = MarketDataStatus.NO_DATA_IN_SNAPSHOT
SNAPSHOT_NOT_BUILT = MarketDataStatus.SNAPSHOT_NOT_BUILT
REFRESH_DISABLED_IN_SNAPSHOT_MODE = MarketDataStatus.REFRESH_DISABLED_IN_SNAPSHOT_MODE
ETL_RUNNING = MarketDataStatus.ETL_RUNNING
ETL_FAILED = MarketDataStatus.ETL_FAILED
STALE_SNAPSHOT = MarketDataStatus.STALE_SNAPSHOT


def market_meta(
    status: MarketDataStatus | str,
    *,
    run_id: str | None = None,
    last_synced_at: str | None = None,
    stale: bool = False,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "data_status": str(status),
        "run_id": run_id,
        "last_synced_at": last_synced_at,
        "stale": stale,
        "message": message,
    }


def reject_refresh_in_snapshot_mode(refresh: bool) -> None:
    if not refresh:
        return

    raise HTTPException(
        status_code=409,
        detail={
            "code": REFRESH_DISABLED_IN_SNAPSHOT_MODE,
            "message": "Read APIs cannot refresh upstream market data in snapshot mode. Run CLI/admin ETL instead.",
        },
    )
```

- [ ] **Step 4: Run the test and verify it passes**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Commit Task 1**

Run:

```powershell
git add backend_v2/src/market_data_status.py backend_v2/tests/__init__.py backend_v2/tests/test_snapshot_mode.py
git commit -m "test: add market data status contract"
```

## Task 2: Read-Only FastAPI Startup

**Files:**
- Modify: `backend_v2/src/jobs.py`
- Modify: `backend_v2/src/main.py`
- Modify: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Add a failing lifespan test**

Append this test class to `backend_v2/tests/test_snapshot_mode.py` before the `if __name__ == "__main__":` block:

```python
class ReadOnlyLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_lifespan_initializes_db_without_market_background_work(self):
        from src.jobs import build_lifespan

        calls = []

        def init_db():
            calls.append("init_db")

        class App:
            pass

        lifespan = build_lifespan(init_db=init_db)
        async with lifespan(App()):
            calls.append("inside")

        self.assertEqual(calls, ["init_db", "inside"])
```

- [ ] **Step 2: Run the lifespan test and verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.ReadOnlyLifespanTests -v
```

Expected: FAIL because `build_lifespan` currently requires fetcher/preload arguments and starts background work.

- [ ] **Step 3: Simplify `build_lifespan`**

Replace `backend_v2/src/jobs.py` with this implementation:

```python
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Callable

logger = logging.getLogger(__name__)


def build_lifespan(*, init_db: Callable[[], None]) -> Callable[[Any], Any]:
    @asynccontextmanager
    async def lifespan(app: Any):
        del app
        logger.info("Initializing application schema in strict snapshot mode...")
        init_db()
        logger.info("Market data startup is read-only; no fetch loops, preload jobs, or ETL schedulers were started.")
        yield

    return lifespan
```

- [ ] **Step 4: Simplify `backend_v2/src/main.py` lifespan wiring**

Remove these imports from `backend_v2/src/main.py`:

```python
from src.services.fundamental_fetcher import fundamental_service
from src.services.vnstock_fetcher import VN30_SYMBOLS, fetcher_service
```

Remove the preload configuration block:

```python
PRELOAD_REFERENCE_CACHE_ENABLED = settings.vnstock_preload_reference_cache
PRELOAD_REFERENCE_FORCE_REFRESH = settings.vnstock_preload_force_refresh
PRELOAD_REFERENCE_SYMBOL_LIMIT = max(1, min(len(VN30_SYMBOLS), settings.vnstock_preload_symbol_limit))
```

Replace the `lifespan = build_lifespan(...)` block with:

```python
lifespan = build_lifespan(init_db=init_db)
```

- [ ] **Step 5: Run the lifespan test and compile**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.ReadOnlyLifespanTests -v
cd ..
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: unittest PASS; compileall completes without syntax errors.

- [ ] **Step 6: Commit Task 2**

Run:

```powershell
git add backend_v2/src/jobs.py backend_v2/src/main.py backend_v2/tests/test_snapshot_mode.py
git commit -m "fix: make backend startup read-only for market data"
```

## Task 3: Stock Read APIs Stop Refreshing

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Modify: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Add failing tests for stock refresh guards and missing history**

Append this test class to `backend_v2/tests/test_snapshot_mode.py`:

```python
class StockReadApiSnapshotModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_snapshot_refresh_param_is_rejected(self):
        from src.routes.stocks import get_snapshots

        with self.assertRaises(HTTPException) as ctx:
            await get_snapshots(symbols="FPT", refresh=True)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], "REFRESH_DISABLED_IN_SNAPSHOT_MODE")

    async def test_history_does_not_auto_fetch_when_db_empty(self):
        from src.routes import stocks

        async def empty_history(*args, **kwargs):
            return []

        async def forbidden_refresh(*args, **kwargs):
            raise AssertionError("read API attempted to create market data")

        original_load = stocks.fetcher_service.load_history_from_db_async
        original_refresh = stocks.fetcher_service.refresh_history_for_symbol
        stocks.fetcher_service.load_history_from_db_async = empty_history
        stocks.fetcher_service.refresh_history_for_symbol = forbidden_refresh
        try:
            result = await stocks.get_history("FPT", limit=30)
        finally:
            stocks.fetcher_service.load_history_from_db_async = original_load
            stocks.fetcher_service.refresh_history_for_symbol = original_refresh

        self.assertEqual(result["data_status"], "NO_DATA_IN_SNAPSHOT")
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["data"], [])
```

- [ ] **Step 2: Run the stock tests and verify they fail**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests -v
```

Expected: FAIL because current stock routes accept refresh and `_ensure_history_data` refreshes from source when DB is empty.

- [ ] **Step 3: Update imports in `stocks.py`**

Add:

```python
from src.market_data_status import (
    DATA_AVAILABLE,
    NO_DATA_IN_SNAPSHOT,
    reject_refresh_in_snapshot_mode,
)
```

- [ ] **Step 4: Replace `_ensure_history_data` with read-only loader**

Replace the current `_ensure_history_data` function with:

```python
async def _load_history_data(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> list[dict[str, Any]]:
    return await fetcher_service.load_history_from_db_async(
        symbol,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
    )
```

- [ ] **Step 5: Guard refresh params in stock routes**

At the start of each route that accepts `refresh`, call:

```python
reject_refresh_in_snapshot_mode(refresh)
```

Apply this to:

- `get_snapshots`
- `get_overview`
- `get_history`
- `get_intraday`
- `get_ticks`
- `get_technical`
- `get_financials`

For `get_intraday` and `get_ticks`, keep accepting `force` for API compatibility but do not use it after refresh is rejected.

- [ ] **Step 6: Remove auto refresh logic from stock routes**

In `get_snapshots`, remove:

```python
in_session = fetcher_service.is_intraday_fetch_window()
auto_refresh = in_session and _intraday_cache_is_stale()
should_refresh = refresh or auto_refresh

if should_refresh:
    await _safe_refresh_symbols_once(target_symbols)
```

Set response fields:

```python
"source": "snapshot-mysql-cache",
"refreshed": False,
"auto_refreshed": False,
"is_in_session": fetcher_service.is_intraday_fetch_window(),
"data_status": DATA_AVAILABLE if snapshots else NO_DATA_IN_SNAPSHOT,
```

In `get_history`, remove the `if refresh: await fetcher_service.refresh_history_for_symbol(...)` block and replace the call to `_ensure_history_data(...)` with `_load_history_data(...)`. Add:

```python
"data_status": DATA_AVAILABLE if records else NO_DATA_IN_SNAPSHOT,
"source": "mysql",
```

In `get_ticks`, remove the stale auto refresh and empty-cache retry. Return:

```python
"refreshed": False,
"auto_refreshed": False,
"data_status": DATA_AVAILABLE if ticks_desc else NO_DATA_IN_SNAPSHOT,
```

- [ ] **Step 7: Make overview and financials cache-only**

In `get_overview`, after checking cached overview and ratios, do not call `fundamental_service.refresh_company_overview` or `fundamental_service.refresh_financial_report`. Use empty payloads if caches are missing and include:

```python
"source": "mysql-cache",
"data_status": DATA_AVAILABLE if overview_payload or ratio_records else NO_DATA_IN_SNAPSHOT,
```

In `get_financials`, remove the call to `fundamental_service.refresh_financial_report`. Return cached rows or an empty list:

```python
rows = cached_rows or []
return {
    "symbol": normalized,
    "type": report_type,
    "count": len(rows),
    "data": rows,
    "source": "mysql-financial-cache",
    "last_synced_at": cached_synced_at,
    "data_status": DATA_AVAILABLE if rows else NO_DATA_IN_SNAPSHOT,
}
```

- [ ] **Step 8: Update technical route to use read-only history**

Replace `_ensure_history_data(...)` with `_load_history_data(...)` in `get_technical`. If no records exist, return an empty but stable payload:

```python
if not records:
    return {
        "symbol": normalized,
        "count": 0,
        "ohlcv": {"time": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
        "indicators": {},
        "signals": {},
        "source": "mysql",
        "last_synced_at": None,
        "data_status": NO_DATA_IN_SNAPSHOT,
    }
```

- [ ] **Step 9: Run stock tests and compile**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests -v
cd ..
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: unittest PASS; compileall completes without syntax errors.

- [ ] **Step 10: Commit Task 3**

Run:

```powershell
git add backend_v2/src/routes/stocks.py backend_v2/tests/test_snapshot_mode.py
git commit -m "fix: make stock read APIs snapshot-only"
```

## Task 4: Market, Analysis, and Internal Routes Stop Creating Market Data

**Files:**
- Modify: `backend_v2/src/routes/market.py`
- Modify: `backend_v2/src/routes/analysis.py`
- Modify: `backend_v2/src/routes/internal.py`
- Modify: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Add failing tests for market and internal refresh guards**

Append this test class to `backend_v2/tests/test_snapshot_mode.py`:

```python
class MarketAndInternalSnapshotModeTests(unittest.IsolatedAsyncioTestCase):
    async def test_market_indices_refresh_is_rejected(self):
        from src.routes.market import get_market_indices

        with self.assertRaises(HTTPException) as ctx:
            await get_market_indices(refresh=True)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], "REFRESH_DISABLED_IN_SNAPSHOT_MODE")

    async def test_debug_intraday_refresh_is_rejected(self):
        from src.routes.internal import debug_refresh_intraday

        with self.assertRaises(HTTPException) as ctx:
            await debug_refresh_intraday(symbols="FPT")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], "REFRESH_DISABLED_IN_SNAPSHOT_MODE")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.MarketAndInternalSnapshotModeTests -v
```

Expected: FAIL because these routes currently allow refresh/fetch behavior.

- [ ] **Step 3: Remove direct `vnstock.Quote` serving fetches from `market.py`**

Remove:

```python
from vnstock import Quote
```

Add imports:

```python
import pandas as pd

from src.market_data_status import DATA_AVAILABLE, NO_DATA_IN_SNAPSHOT, reject_refresh_in_snapshot_mode
```

Replace `_fetch_market_index_history_sync` with a lake reader:

```python
def _load_market_index_history_from_lake(index_symbol: str, limit: int) -> list[dict[str, Any]]:
    latest = REPO_ROOT / "lake" / "gold" / "market_features" / "latest.parquet"
    if not latest.exists():
        return []

    frame = pd.read_parquet(latest)
    close_column = f"macro_{MARKET_INDEX_DEFINITIONS[index_symbol]['vnstock_symbol'].lower()}_close"
    volume_column = f"macro_{MARKET_INDEX_DEFINITIONS[index_symbol]['vnstock_symbol'].lower()}_volume"
    if "data_date" not in frame.columns or close_column not in frame.columns:
        return []

    rows = (
        frame[["data_date", close_column] + ([volume_column] if volume_column in frame.columns else [])]
        .dropna(subset=["data_date", close_column])
        .drop_duplicates(subset=["data_date"], keep="last")
        .sort_values("data_date")
        .tail(max(limit, 1))
    )

    output: list[dict[str, Any]] = []
    for item in rows.to_dict("records"):
        close = _to_float(item.get(close_column))
        output.append(
            {
                "time": str(item.get("data_date")),
                "open": close,
                "high": close,
                "low": close,
                "close": close,
                "volume": _to_int(item.get(volume_column)) if volume_column in item else 0,
            }
        )
    return output
```

- [ ] **Step 4: Make market index route cache/lake-only**

In `_get_market_index_history_rows`, call `reject_refresh_in_snapshot_mode(refresh)` first. Remove `await fetcher_service.wait_for_rate_slot()` and `asyncio.to_thread(_fetch_market_index_history_sync, ...)`. Use:

```python
rows = _load_market_index_history_from_lake(index_symbol, safe_limit)
if rows:
    synced_at = _utc_now().isoformat()
    return rows, synced_at, "lake-gold-market-features"
return [], None, "snapshot-market-index-missing"
```

In `get_market_indices` and `get_market_index_history`, add:

```python
"data_status": DATA_AVAILABLE if history_rows else NO_DATA_IN_SNAPSHOT
```

For aggregate `/api/market-indices`, use `DATA_AVAILABLE` if any index has rows, otherwise `NO_DATA_IN_SNAPSHOT`.

- [ ] **Step 5: Make news/events cache-only**

In `backend_v2/src/routes/market.py`, add imports:

```python
from src.cache import _load_symbol_payload_cache
from src.database.models import EventsCache, NewsCache
```

In `get_news`, call `reject_refresh_in_snapshot_mode(refresh)` before reading caches and replace the service call with:

```python
items, synced_at = await _load_symbol_payload_cache(NewsCache, symbol, max_age_seconds=None)
items = items if isinstance(items, list) else []
```

In `get_events`, call `reject_refresh_in_snapshot_mode(refresh)` before reading caches and replace the service call with:

```python
items, synced_at = await _load_symbol_payload_cache(EventsCache, symbol, max_age_seconds=None)
items = items if isinstance(items, list) else []
```

Add `data_status` based on whether clipped items exist.

- [ ] **Step 6: Make analysis use cache-only context**

In `backend_v2/src/routes/analysis.py`, replace:

```python
from src.routes.stocks import _ensure_history_data
```

with:

```python
from src.routes.stocks import _load_history_data
```

Replace the history call with:

```python
history = await _load_history_data(symbol, start_date=None, end_date=None, limit=30)
```

Replace the `asyncio.gather(...)` block that calls `refresh_company_overview` and `refresh_financial_report` with cache-only loads:

```python
from src.cache import _load_financial_report_cache, _load_symbol_payload_cache
from src.database.models import CompanyOverviewCache

overview_payload, _ = await _load_symbol_payload_cache(CompanyOverviewCache, symbol, max_age_seconds=None)
ratio_records, _ = await _load_financial_report_cache(symbol, "ratios", max_age_seconds=None)
news_list, _ = await fundamental_service.get_symbol_news(symbol, refresh=False)
overview_payload = overview_payload if isinstance(overview_payload, dict) else {}
ratio_records = ratio_records if isinstance(ratio_records, list) else []
```

Update the returned analysis metadata string from:

```python
"data_source": "MySQL (history) + vnstock (live) + Kaggle Trading-R1 (analysis)"
```

to:

```python
"data_source": "snapshot/mysql-cache + Kaggle Trading-R1 (analysis)"
```

- [ ] **Step 7: Disable debug intraday refresh**

In `backend_v2/src/routes/internal.py`, import:

```python
from src.market_data_status import reject_refresh_in_snapshot_mode
```

Replace the body of `debug_refresh_intraday` with:

```python
del symbols, force, cache_limit, _
reject_refresh_in_snapshot_mode(True)
return {}
```

Keep `/api/dnse/save-quotes` unchanged for this phase because it is an authenticated admin/manual ingestion endpoint and not a read API. Add a code comment above it:

```python
# Explicit admin/manual ingestion remains allowed; read APIs must not call this path.
```

- [ ] **Step 8: Run tests and compile**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.MarketAndInternalSnapshotModeTests -v
cd ..
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: unittest PASS; compileall completes without syntax errors.

- [ ] **Step 9: Commit Task 4**

Run:

```powershell
git add backend_v2/src/routes/market.py backend_v2/src/routes/analysis.py backend_v2/src/routes/internal.py backend_v2/tests/test_snapshot_mode.py
git commit -m "fix: prevent read routes from creating market data"
```

## Task 5: ETL Status Metadata

**Files:**
- Modify: `backend_v2/src/routes/etl_status.py`
- Modify: `src/services/authApi.ts`
- Modify: `src/views/Admin/components/TabEtlMonitor.vue`

- [ ] **Step 1: Update ETL route imports**

In `backend_v2/src/routes/etl_status.py`, add:

```python
from src.market_data_status import (
    DATA_AVAILABLE,
    ETL_FAILED,
    ETL_RUNNING,
    SNAPSHOT_NOT_BUILT,
    STALE_SNAPSHOT,
)
```

- [ ] **Step 2: Add a local ETL data status resolver**

Add this helper after `_default_cfg`:

```python
def _etl_data_status(health: dict) -> str:
    latest_run = health.get("latest_run") or {}
    latest_snapshot = health.get("latest_snapshot")
    if latest_run.get("status") == "running":
        return ETL_RUNNING
    if latest_run.get("status") == "failed":
        return ETL_FAILED
    if not latest_snapshot:
        return SNAPSHOT_NOT_BUILT
    if health.get("status") == "stale":
        return STALE_SNAPSHOT
    return DATA_AVAILABLE
```

- [ ] **Step 3: Include `data_status` in ETL responses**

In `get_etl_status`, compute:

```python
data_status = _etl_data_status(health)
```

and include:

```python
"data_status": data_status,
```

In `get_etl_health`, wrap the result:

```python
health = check_etl_health(_default_cfg())
health["data_status"] = _etl_data_status(health)
return health
```

In `trigger_etl_run`, return:

```python
return {"run_id": cfg.run_id, "status": "started", "data_status": ETL_RUNNING, "symbols": cfg.symbols}
```

- [ ] **Step 4: Update frontend ETL types**

In `src/services/authApi.ts`, add:

```ts
export type MarketDataStatus =
  | 'DATA_AVAILABLE'
  | 'NO_DATA_IN_SNAPSHOT'
  | 'SNAPSHOT_NOT_BUILT'
  | 'REFRESH_DISABLED_IN_SNAPSHOT_MODE'
  | 'ETL_RUNNING'
  | 'ETL_FAILED'
  | 'STALE_SNAPSHOT'
```

Add `data_status?: MarketDataStatus` to `EtlStatusResponse`, `EtlHealthResponse`, and `EtlTriggerResponse`.

- [ ] **Step 5: Display data status in ETL Monitor**

In `src/views/Admin/components/TabEtlMonitor.vue`, add:

```ts
const dataStatus = computed(() => status.value?.data_status || health.value?.data_status || 'SNAPSHOT_NOT_BUILT')
```

Update the status card secondary text to include:

```vue
<p class="mt-2 font-mono text-xs text-gray-500 dark:text-gray-400">{{ dataStatus }}</p>
```

Update `triggerManualRun()` success notice:

```ts
showNotice(`Da khoi chay ETL ${result.run_id} cho ${result.symbols.length} ma (${result.data_status || 'ETL_RUNNING'}).`, 'success')
```

Use ASCII text if touching this file to avoid worsening existing mojibake.

- [ ] **Step 6: Compile backend and type-check frontend**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall backend_v2\src
npm.cmd run type-check
```

Expected: compileall completes; `vue-tsc` passes.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add backend_v2/src/routes/etl_status.py src/services/authApi.ts src/views/Admin/components/TabEtlMonitor.vue
git commit -m "feat: expose snapshot data status in ETL monitor"
```

## Task 6: Frontend Read Refresh Becomes Snapshot Reload

**Files:**
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/views/MarketOverview.vue`
- Modify: `src/views/StockDetail.vue`
- Modify: `src/views/NewsEvents.vue`
- Modify: `src/views/StockAIAnalysis.vue`
- Modify other files found by `rg -n "forceRefresh|refresh\\)" src`

- [ ] **Step 1: Add status metadata type to `stockBackendApi.ts`**

Add:

```ts
export type MarketDataStatus =
  | 'DATA_AVAILABLE'
  | 'NO_DATA_IN_SNAPSHOT'
  | 'SNAPSHOT_NOT_BUILT'
  | 'REFRESH_DISABLED_IN_SNAPSHOT_MODE'
  | 'ETL_RUNNING'
  | 'ETL_FAILED'
  | 'STALE_SNAPSHOT'
```

Update `ApiMeta`:

```ts
interface ApiMeta {
  source?: string
  last_synced_at?: string
  data_status?: MarketDataStatus
  run_id?: string | null
  stale?: boolean
  message?: string | null
}
```

- [ ] **Step 2: Stop sending refresh query params**

In these methods, remove `refresh` from `buildQuery`:

- `getCompanyOverview`
- `getHistory`
- `getIntraday`
- `getOrderLog`
- `getTechnicalAnalysis`
- `getFinancials`
- `getMarketIndices`
- `getMarketIndexHistory`
- `getSnapshots`
- `getMarketNews`
- `getMarketEvents`

Keep the optional `refresh` parameters in TypeScript method signatures for now to reduce call-site churn, but do not serialize them.

Example replacement:

```ts
async getSnapshots(
  symbols: string[],
  refresh: boolean = false,
): Promise<SnapshotsResponse> {
  void refresh
  const normalized = symbols
    .map((symbol) => symbol.trim().toUpperCase())
    .filter((symbol) => symbol.length > 0)

  const query = this.buildQuery({
    symbols: normalized.length > 0 ? normalized.join(',') : undefined,
  })

  return this.fetch<SnapshotsResponse>(`/api/stocks/snapshots${query}`)
}
```

- [ ] **Step 3: Rename visible refresh actions where practical**

In `src/views/MarketOverview.vue`, `src/views/StockDetail.vue`, `src/views/NewsEvents.vue`, and `src/views/StockAIAnalysis.vue`, keep existing reload functions but treat `forceRefresh` as reload intent only. Add comments only where helpful:

```ts
// Snapshot mode: reload reads the current snapshot; it does not pull upstream data.
```

Do not add user-facing instructional text outside Admin ETL Monitor.

- [ ] **Step 4: Find remaining refresh query serialization**

Run:

```powershell
rg -n "refresh: refresh|refresh \\|\\| undefined|force: force|auto_refreshed" src
```

Expected: no `stockBackendApi.ts` read methods serialize refresh or force into query params. Existing response fields like `auto_refreshed` may remain in interfaces for compatibility.

- [ ] **Step 5: Type-check and build**

Run:

```powershell
npm.cmd run type-check
npm.cmd run build-only
```

Expected: both pass.

- [ ] **Step 6: Commit Task 6**

Run:

```powershell
git add src/services/stockBackendApi.ts src/views/MarketOverview.vue src/views/StockDetail.vue src/views/NewsEvents.vue src/views/StockAIAnalysis.vue
git commit -m "fix: make frontend refresh reload current snapshot"
```

## Task 7: Documentation and Full Verification

**Files:**
- Modify: `README.md`
- Review: `docs/superpowers/specs/2026-05-14-strict-snapshot-data-mode-design.md`

- [ ] **Step 1: Update README strict snapshot mode section**

Add a section near "ETL Pipeline" or "Scheduler":

```markdown
## Strict Snapshot Data Mode

Market data uses a manual, reproducible snapshot model.

Runtime invariants:

- Backend startup is read-only for market data.
- Read APIs never create market data.
- Only CLI ETL and admin ETL trigger can write market snapshots/cache.
- Missing or stale data is reported, not auto-fixed.

Short-term serving:

- MySQL cache tables serve stock/market APIs.
- `lake/processed` and `lake/gold` remain the source of truth and audit trail.
- User/app data remains in MySQL.

Supported write paths:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB --run-mode incremental
```

```text
POST /api/etl/trigger
```

Read API data statuses:

- `DATA_AVAILABLE`
- `NO_DATA_IN_SNAPSHOT`
- `SNAPSHOT_NOT_BUILT`
- `REFRESH_DISABLED_IN_SNAPSHOT_MODE`
- `ETL_RUNNING`
- `ETL_FAILED`
- `STALE_SNAPSHOT`
```

Replace old README language that says APScheduler is the supported backend update mechanism with language that says embedded backend scheduling is disabled in strict snapshot mode.

- [ ] **Step 2: Run full backend tests and compile**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
cd ..
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: unittest PASS; compileall completes without syntax errors.

- [ ] **Step 3: Run frontend verification**

Run:

```powershell
npm.cmd run type-check
npm.cmd run build-only
```

Expected: both pass.

- [ ] **Step 4: Smoke import backend app**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.main import app; print(app.title)"
```

Expected output includes:

```text
VNStock Intraday API V2
```

- [ ] **Step 5: Search for forbidden read-path creation behavior**

Run:

```powershell
rg -n "fetch_loop|preload_historical_data|preload_reference_caches|run_mock_streamer|EtlScheduler|refresh_history_for_symbol|refresh_symbol_intraday|refresh_symbols_once|refresh_company_overview|refresh_financial_report|Quote\\(" backend_v2/src/routes backend_v2/src/jobs.py backend_v2/src/main.py
```

Expected: no matches in read routes/startup except allowed imports or explicit comments. If matches remain, inspect them and either remove the read-path creation behavior or document why the match is not a market-data write path.

- [ ] **Step 6: Commit Task 7**

Run:

```powershell
git add README.md docs/superpowers/specs/2026-05-14-strict-snapshot-data-mode-design.md
git commit -m "docs: document strict snapshot data mode"
```

## Final Review Checklist

- [ ] Backend startup initializes app infrastructure only and starts no market-data jobs.
- [ ] Read APIs reject `refresh=true` with `REFRESH_DISABLED_IN_SNAPSHOT_MODE`.
- [ ] Read APIs do not call source fetchers to repair missing data.
- [ ] CLI ETL still runs through `etl.run_etl`.
- [ ] Admin ETL trigger still starts `run_etl_in_process`.
- [ ] Missing data returns `NO_DATA_IN_SNAPSHOT` or `SNAPSHOT_NOT_BUILT`.
- [ ] Stale/failed/running ETL states are visible through ETL status metadata.
- [ ] Frontend read calls no longer serialize `refresh=true`.
- [ ] README documents the new operating model and future warehouse direction.
