# DuckDB Read/Write Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the FastAPI backend serve market data reliably while ETL/DuckDB writes are running, eliminating request-time DuckDB lock failures.

**Architecture:** Backend read APIs should prefer immutable gold parquet snapshots and only use DuckDB through explicit read-only adapters. ETL, cache warming, and AI job persistence are the only writers; request handlers must not create schemas or write technical caches during normal reads.

**Tech Stack:** FastAPI, pandas/parquet, DuckDB, unittest, Vue API clients.

---

## File Structure

- Modify `backend_v2/src/settings.py`: add explicit runtime mode and read-source settings.
- Create `backend_v2/src/services/market_lake_reader.py`: read-only parquet adapter for daily OHLCV and market features.
- Modify `backend_v2/src/database/market_duckdb.py`: split DuckDB connection behavior into read-only vs writer, and stop `ensure_schema()` for read-only use.
- Modify `backend_v2/src/cache.py`: make technical cache read/write optional in runtime API mode.
- Modify `backend_v2/src/routes/stocks.py`: use `MarketLakeReader` for history and technical data before DuckDB fallback.
- Modify `backend_v2/src/routes/market.py`: use `MarketLakeReader` for index history instead of route-local parquet logic.
- Modify `backend_v2/src/jobs.py` and `backend_v2/src/main.py`: avoid DuckDB-backed AI job startup work unless explicitly enabled.
- Create `backend_v2/tests/test_market_lake_reader.py`: unit tests for parquet reader.
- Extend `backend_v2/tests/test_snapshot_mode.py`: tests for API behavior while DuckDB is unavailable.
- Optional later: modify `src/components/stock/TechnicalAnalysisChart.vue` to show data-source-specific empty/error states.

---

## Task 1: Add Runtime Source Settings

**Files:**
- Modify: `backend_v2/src/settings.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add this test near `MarketDataStatusTests`:

```python
class RuntimeSettingsTests(unittest.TestCase):
    def test_backend_defaults_to_lake_first_read_mode(self):
        from src.settings import Settings

        settings = Settings()

        self.assertEqual(settings.market_read_source, "lake_first")
        self.assertFalse(settings.duckdb_request_writes_enabled)
        self.assertFalse(settings.duckdb_ai_jobs_enabled)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.RuntimeSettingsTests -v
```

Expected: FAIL because settings fields do not exist yet.

- [ ] **Step 3: Implement settings**

In `Settings` in `backend_v2/src/settings.py`, add:

```python
    market_read_source: str = Field(default="lake_first", pattern="^(lake_first|duckdb_first|lake_only|duckdb_only)$")
    duckdb_request_writes_enabled: bool = False
    duckdb_ai_jobs_enabled: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.RuntimeSettingsTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/settings.py backend_v2/tests/test_snapshot_mode.py
git commit -m "chore: add market data runtime mode settings"
```

---

## Task 2: Create Read-Only Gold Lake Reader

**Files:**
- Create: `backend_v2/src/services/market_lake_reader.py`
- Test: `backend_v2/tests/test_market_lake_reader.py`

- [ ] **Step 1: Write the failing tests**

Create `backend_v2/tests/test_market_lake_reader.py`:

```python
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from src.services.market_lake_reader import MarketLakeReader


class MarketLakeReaderTests(unittest.TestCase):
    def test_load_symbol_history_reads_latest_gold_parquet(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "lake" / "gold" / "market_features" / "by_symbol" / "symbol=FPT"
            target.mkdir(parents=True)
            pd.DataFrame(
                [
                    {"symbol": "FPT", "data_date": "2026-05-25", "open_price": 73.5, "high_price": 75.0, "low_price": 73.0, "close_price": 74.0, "volume": 1000},
                    {"symbol": "FPT", "data_date": "2026-05-26", "open_price": 74.0, "high_price": 75.5, "low_price": 73.5, "close_price": 74.5, "volume": 2000},
                ]
            ).to_parquet(target / "latest.parquet", index=False)

            rows = MarketLakeReader(root).load_symbol_history("FPT", limit=1)

        self.assertEqual(rows, [{"time": "2026-05-26", "open": 74.0, "high": 75.5, "low": 73.5, "close": 74.5, "volume": 2000}])

    def test_load_market_index_history_expands_thousand_unit_values(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "lake" / "gold" / "market_features"
            target.mkdir(parents=True)
            pd.DataFrame(
                [
                    {"data_date": "2026-05-25", "macro_vnindex_close": 1.89, "macro_vnindex_volume": 100},
                    {"data_date": "2026-05-26", "macro_vnindex_close": 1.88, "macro_vnindex_volume": 200},
                ]
            ).to_parquet(target / "latest.parquet", index=False)

            rows = MarketLakeReader(root).load_market_index_history("VNINDEX", "VNINDEX", limit=2)

        self.assertEqual(rows[-1]["close"], 1880.0)
        self.assertEqual(rows[-1]["volume"], 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_market_lake_reader -v
```

Expected: FAIL because `src.services.market_lake_reader` does not exist.

- [ ] **Step 3: Implement `MarketLakeReader`**

Create `backend_v2/src/services/market_lake_reader.py`:

```python
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from src.settings import REPO_ROOT
from src.utils import _to_float, _to_int

logger = logging.getLogger(__name__)


class MarketLakeReader:
    def __init__(self, repo_root: Path | None = None):
        self.repo_root = Path(repo_root or REPO_ROOT)

    def load_symbol_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 365,
    ) -> list[dict[str, Any]]:
        parquet_path = self.repo_root / "lake" / "gold" / "market_features" / "by_symbol" / f"symbol={symbol.upper()}" / "latest.parquet"
        if not parquet_path.exists():
            return []
        try:
            frame = pd.read_parquet(parquet_path)
        except Exception:
            logger.warning("Could not read gold lake history for %s.", symbol, exc_info=True)
            return []

        required = ["data_date", "open_price", "high_price", "low_price", "close_price"]
        if any(column not in frame.columns for column in required):
            return []

        rows = frame.copy()
        rows["data_date"] = pd.to_datetime(rows["data_date"], errors="coerce").dt.date
        rows = rows.dropna(subset=["data_date", "close_price"])
        if isinstance(start_date, date):
            rows = rows[rows["data_date"] >= start_date]
        if isinstance(end_date, date):
            rows = rows[rows["data_date"] <= end_date]

        rows = rows.sort_values("data_date").tail(max(limit, 1))
        output: list[dict[str, Any]] = []
        for raw in rows.to_dict("records"):
            close = _to_float(raw.get("close_price"))
            if close <= 0:
                continue
            output.append(
                {
                    "time": str(raw.get("data_date")),
                    "open": _to_float(raw.get("open_price"), fallback=close),
                    "high": _to_float(raw.get("high_price"), fallback=close),
                    "low": _to_float(raw.get("low_price"), fallback=close),
                    "close": close,
                    "volume": _to_int(raw.get("volume")) if "volume" in raw else 0,
                }
            )
        return output

    def load_market_index_history(self, index_symbol: str, vnstock_symbol: str, limit: int = 365) -> list[dict[str, Any]]:
        parquet_path = self.repo_root / "lake" / "gold" / "market_features" / "latest.parquet"
        if not parquet_path.exists():
            return []
        try:
            frame = pd.read_parquet(parquet_path)
        except Exception:
            logger.warning("Could not read gold lake market index history for %s.", index_symbol, exc_info=True)
            return []

        base = vnstock_symbol.lower()
        close_column = f"macro_{base}_close"
        volume_column = f"macro_{base}_volume"
        if "data_date" not in frame.columns or close_column not in frame.columns:
            return []

        columns = ["data_date", close_column]
        if volume_column in frame.columns:
            columns.append(volume_column)

        rows = (
            frame[columns]
            .dropna(subset=["data_date", close_column])
            .drop_duplicates(subset=["data_date"], keep="last")
            .sort_values("data_date")
            .tail(max(limit, 1))
        )
        output: list[dict[str, Any]] = []
        for raw in rows.to_dict("records"):
            close = self._normalize_index_price(raw.get(close_column))
            output.append(
                {
                    "time": str(raw.get("data_date")),
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": _to_int(raw.get(volume_column)) if volume_column in raw else 0,
                }
            )
        return output

    @staticmethod
    def _normalize_index_price(value: Any) -> float:
        price = _to_float(value)
        if 0 < abs(price) < 10:
            return price * 1000.0
        return price
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_market_lake_reader -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/services/market_lake_reader.py backend_v2/tests/test_market_lake_reader.py
git commit -m "feat: add read-only market lake reader"
```

---

## Task 3: Route Stock History and Technical Reads Through Lake First

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add this test to `StockReadApiSnapshotModeTests`:

```python
async def test_technical_uses_lake_history_when_duckdb_is_empty(self):
    from src.routes import stocks

    class Reader:
        def load_symbol_history(self, symbol, start_date=None, end_date=None, limit=365):
            return [
                {"time": f"2026-01-{day:02d}", "open": 70 + day, "high": 71 + day, "low": 69 + day, "close": 70 + day, "volume": 1000 + day}
                for day in range(1, 31)
            ][-limit:]

    async def empty_history(*args, **kwargs):
        return []

    original_reader = stocks.market_lake_reader
    original_load = stocks.fetcher_service.load_history_from_db_async
    stocks.market_lake_reader = Reader()
    stocks.fetcher_service.load_history_from_db_async = empty_history
    try:
        payload = await stocks.get_technical("FPT", limit=30)
    finally:
        stocks.market_lake_reader = original_reader
        stocks.fetcher_service.load_history_from_db_async = original_load

    self.assertEqual(payload["count"], 30)
    self.assertEqual(payload["data_status"], "DATA_AVAILABLE")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_technical_uses_lake_history_when_duckdb_is_empty -v
```

Expected: FAIL if `stocks.market_lake_reader` is not wired or technical still returns no data.

- [ ] **Step 3: Implement lake-first selection**

In `backend_v2/src/routes/stocks.py`, replace route-local parquet helper with:

```python
from src.services.market_lake_reader import MarketLakeReader

market_lake_reader = MarketLakeReader()
```

Then implement `_load_history_data` as:

```python
async def _load_history_data(symbol: str, start_date: Optional[date], end_date: Optional[date], limit: int) -> list[dict[str, Any]]:
    if settings.market_read_source in {"lake_first", "lake_only"}:
        rows = market_lake_reader.load_symbol_history(symbol, start_date=start_date, end_date=end_date, limit=limit)
        if rows or settings.market_read_source == "lake_only":
            return rows

    if settings.market_read_source in {"duckdb_first", "duckdb_only", "lake_first"}:
        rows = await fetcher_service.load_history_from_db_async(symbol, start_date=start_date, end_date=end_date, limit=limit)
        if rows or settings.market_read_source == "duckdb_only":
            return rows

    return market_lake_reader.load_symbol_history(symbol, start_date=start_date, end_date=end_date, limit=limit)
```

Also update `get_history()` source:

```python
source = "lake-gold-market-features" if records else "snapshot-history-missing"
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_technical_uses_lake_history_when_duckdb_is_empty -v
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/routes/stocks.py backend_v2/tests/test_snapshot_mode.py
git commit -m "feat: serve stock history from lake before duckdb"
```

---

## Task 4: Move Market Index Reads to Lake Reader

**Files:**
- Modify: `backend_v2/src/routes/market.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add this test to `MarketIndexScaleTests`:

```python
def test_market_route_uses_lake_reader_for_index_history(self):
    from src.routes import market

    class Reader:
        def load_market_index_history(self, index_symbol, vnstock_symbol, limit=365):
            return [{"time": "2026-05-26", "open": 1880.0, "high": 1880.0, "low": 1880.0, "close": 1880.0, "volume": 200}]

    original_reader = market.market_lake_reader
    market.market_lake_reader = Reader()
    try:
        rows = market._load_market_index_history_from_lake("VNINDEX", 30)
    finally:
        market.market_lake_reader = original_reader

    self.assertEqual(rows[0]["close"], 1880.0)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.MarketIndexScaleTests.test_market_route_uses_lake_reader_for_index_history -v
```

Expected: FAIL if `market.market_lake_reader` is not defined.

- [ ] **Step 3: Implement route delegation**

In `backend_v2/src/routes/market.py`, add:

```python
from src.services.market_lake_reader import MarketLakeReader

market_lake_reader = MarketLakeReader()
```

Then replace `_load_market_index_history_from_lake()` body with:

```python
def _load_market_index_history_from_lake(index_symbol: str, limit: int) -> list[dict[str, Any]]:
    definition = MARKET_INDEX_DEFINITIONS[index_symbol]
    return market_lake_reader.load_market_index_history(
        index_symbol=index_symbol,
        vnstock_symbol=definition["vnstock_symbol"],
        limit=limit,
    )
```

Keep `_build_market_index_quote()` normalization idempotent as a defensive guard.

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.MarketIndexScaleTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/routes/market.py backend_v2/tests/test_snapshot_mode.py
git commit -m "refactor: use lake reader for market index routes"
```

---

## Task 5: Disable Request-Time DuckDB Cache Writes by Default

**Files:**
- Modify: `backend_v2/src/cache.py`
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add to `TechnicalCacheTests`:

```python
async def test_save_technical_cache_is_skipped_when_request_writes_disabled(self):
    from src import cache

    result = await cache._save_technical_cache("FPT", None, None, 180, 180, "2026-05-26", {"symbol": "FPT"})

    self.assertIsNone(result)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.TechnicalCacheTests.test_save_technical_cache_is_skipped_when_request_writes_disabled -v
```

Expected: FAIL because `_save_technical_cache` still attempts DuckDB writes.

- [ ] **Step 3: Implement skip**

In `backend_v2/src/cache.py`, import settings:

```python
from src.settings import get_settings
```

At the start of `_save_technical_cache`, add:

```python
    if not get_settings().duckdb_request_writes_enabled:
        return None
```

Optionally apply the same setting in `_load_technical_cache` if runtime should skip DuckDB entirely:

```python
    if get_settings().market_read_source == "lake_only":
        return None, None
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.TechnicalCacheTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/cache.py backend_v2/tests/test_snapshot_mode.py
git commit -m "fix: skip duckdb technical cache writes in api runtime"
```

---

## Task 6: Keep DuckDB Schema Initialization in Writer Context Only

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add this test to a new `DuckDBConnectionModeTests` class:

```python
class DuckDBConnectionModeTests(unittest.TestCase):
    def test_lazy_repo_can_be_configured_without_schema_initialization_for_reads(self):
        from src.database.market_duckdb import MarketDuckDB

        repo = MarketDuckDB(db_path=":memory:", ensure_schema_on_init=False)

        self.assertEqual(str(repo.db_path), ":memory:")
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.DuckDBConnectionModeTests -v
```

Expected: FAIL because `ensure_schema_on_init` is not supported.

- [ ] **Step 3: Implement connection mode**

In `MarketDuckDB.__init__`, change signature and body:

```python
class MarketDuckDB:
    def __init__(self, db_path: str | Path | None = None, *, read_only: bool = False, ensure_schema_on_init: bool = True):
        self.db_path = _resolve_duckdb_path(db_path)
        self.read_only = read_only
        if str(self.db_path) != ":memory:":
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if ensure_schema_on_init and not read_only:
            self.ensure_schema()
```

In `connect()`:

```python
return duckdb.connect(str(self.db_path), read_only=self.read_only)
```

In `LazyMarketDuckDB`, keep writer default for ETL:

```python
self._repo = MarketDuckDB()
```

Do not route request handlers through this writer repo after Tasks 3-5.

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.DuckDBConnectionModeTests -v
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/database/market_duckdb.py backend_v2/tests/test_snapshot_mode.py
git commit -m "refactor: separate duckdb schema initialization from read mode"
```

---

## Task 7: Gate AI Job DuckDB Startup Work

**Files:**
- Modify: `backend_v2/src/main.py`
- Modify: `backend_v2/src/jobs.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add to `ReadOnlyLifespanTests`:

```python
async def test_lifespan_skips_ai_job_repo_when_disabled(self):
    from src.jobs import build_lifespan

    calls = []

    def init_db():
        calls.append("init_db")

    class ForbiddenAiJobRepo:
        def load_ai_jobs_by_status(self, status):
            raise AssertionError("AI job repo should not be touched")

    class AiJobService:
        async def requeue_existing(self, job_ids):
            calls.append(f"requeue:{job_ids}")

        def ensure_worker(self):
            calls.append("ensure_worker")

    class App:
        pass

    lifespan = build_lifespan(
        init_db=init_db,
        ai_job_repo=ForbiddenAiJobRepo(),
        ai_job_service=AiJobService(),
        ai_jobs_enabled=False,
    )
    async with lifespan(App()):
        calls.append("inside")

    self.assertEqual(calls, ["init_db", "inside"])
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.ReadOnlyLifespanTests.test_lifespan_skips_ai_job_repo_when_disabled -v
```

Expected: FAIL because `build_lifespan` does not accept `ai_jobs_enabled`.

- [ ] **Step 3: Implement gate**

In `backend_v2/src/jobs.py`, update signature:

```python
def build_lifespan(init_db=init_db, ai_job_repo=market_repo, ai_job_service=ai_job_service, ai_jobs_enabled: bool = True):
```

Inside lifespan, wrap AI job logic:

```python
        if ai_jobs_enabled:
            try:
                queued_jobs = ai_job_repo.load_ai_jobs_by_status("queued")
                if queued_jobs:
                    await ai_job_service.requeue_existing([job["job_id"] for job in queued_jobs])
                    ai_job_service.ensure_worker()
            except Exception:
                logger.exception("Could not requeue orphaned AI analysis jobs during startup.")
```

In `backend_v2/src/main.py`, pass:

```python
lifespan = build_lifespan(
    init_db=init_db,
    ai_job_repo=market_repo,
    ai_job_service=ai_job_service,
    ai_jobs_enabled=settings.duckdb_ai_jobs_enabled,
)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.ReadOnlyLifespanTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/jobs.py backend_v2/src/main.py backend_v2/tests/test_snapshot_mode.py
git commit -m "fix: gate duckdb ai job startup work"
```

---

## Task 8: Add Health/Status Visibility for Data Sources

**Files:**
- Modify: `backend_v2/src/routes/etl_status.py` or create `backend_v2/src/routes/data_status.py`
- Modify: `backend_v2/src/main.py` if creating a new route
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add:

```python
class RuntimeDataSourceStatusTests(unittest.IsolatedAsyncioTestCase):
    async def test_data_sources_status_reports_lake_and_duckdb_modes(self):
        from src.routes.etl_status import get_data_sources_status

        payload = await get_data_sources_status()

        self.assertIn("market_read_source", payload)
        self.assertIn("duckdb_request_writes_enabled", payload)
        self.assertIn("lake_gold_available", payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.RuntimeDataSourceStatusTests -v
```

Expected: FAIL because endpoint function does not exist.

- [ ] **Step 3: Implement endpoint**

In `backend_v2/src/routes/etl_status.py`, add:

```python
from src.settings import REPO_ROOT, get_settings


@router.get("/api/data-sources/status")
async def get_data_sources_status() -> dict[str, Any]:
    settings = get_settings()
    lake_gold = REPO_ROOT / "lake" / "gold" / "market_features"
    duckdb_path = REPO_ROOT / settings.duckdb_path
    return {
        "market_read_source": settings.market_read_source,
        "duckdb_request_writes_enabled": settings.duckdb_request_writes_enabled,
        "duckdb_ai_jobs_enabled": settings.duckdb_ai_jobs_enabled,
        "lake_gold_available": lake_gold.exists(),
        "duckdb_path": str(duckdb_path),
        "duckdb_file_exists": duckdb_path.exists(),
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.RuntimeDataSourceStatusTests -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2/src/routes/etl_status.py backend_v2/tests/test_snapshot_mode.py
git commit -m "feat: expose market data source status"
```

---

## Task 9: Final Verification

**Files:**
- No edits unless tests reveal issues.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode tests.test_market_lake_reader -v
..\.venv\Scripts\python.exe -m compileall src
```

Expected: all tests PASS; compileall has no errors.

- [ ] **Step 2: Smoke test key endpoints**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from src.main import app; c=TestClient(app, raise_server_exceptions=False); paths=['/api/stocks/FPT/history?limit=30','/api/stocks/FPT/technical?limit=180','/api/market-indices?limit=4','/api/market-indices/VNINDEX/history?limit=30','/api/data-sources/status']; [print(p, c.get(p).status_code, c.get(p).json().get('count', c.get(p).json().get('market_read_source'))) for p in paths]"
```

Expected:
- history returns 200 with count > 0 if gold lake exists.
- technical returns 200 with count > 0 for FPT.
- market indices return 200 with count 4.
- VNINDEX history returns 200 with count > 0 and close values around 1800.
- data source status returns `lake_first`.

- [ ] **Step 3: Run frontend type-check**

Run:

```powershell
npm.cmd run type-check
```

Expected: PASS. If sandbox blocks `node_modules/.tmp/tsconfig.app.tsbuildinfo`, rerun with approved escalation.

- [ ] **Step 4: Manual dev smoke**

Start backend and frontend:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m uvicorn src.main:app --reload
```

```powershell
npm.cmd run dev
```

Open `http://localhost:5174` and verify:
- Stock detail price card does not show `--` when gold lake has latest close.
- TradingView chart renders.
- Technical analysis renders for FPT.
- Market Overview index cards show `1.880,00`, `2.030,00`, `280,00`, `130,00`.
- Market Overview index chart renders as line chart.

---

## Self-Review

**Spec coverage:** The plan removes request-time dependency on writable DuckDB, isolates ETL/job writes, keeps parquet gold as runtime read source, and adds status visibility.

**Placeholder scan:** No TBD/TODO placeholders remain. Every implementation task has test code, implementation code, and exact commands.

**Type consistency:** `market_read_source`, `duckdb_request_writes_enabled`, `duckdb_ai_jobs_enabled`, `MarketLakeReader`, and route-level `market_lake_reader` are consistently named across tasks.

