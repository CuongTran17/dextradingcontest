# Small ETL Exclusive Backend Read-Only Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent DuckDB lock conflicts in local/dev by making ETL the only DuckDB writer and keeping backend request handling read-only/fallback-friendly.

**Architecture:** ETL runs as an explicit, exclusive command before or outside backend runtime. Backend reads existing lake/gold parquet and cached data; it never starts ETL or writes DuckDB from normal API requests.

**Tech Stack:** FastAPI, pandas/parquet, DuckDB, PowerShell/npm scripts, unittest.

---

## File Structure

- Modify `backend_v2/src/settings.py`: add small runtime switches for ETL on startup and request-time DuckDB writes.
- Modify `backend_v2/src/cache.py`: skip technical cache writes from API requests by default.
- Modify `backend_v2/src/routes/stocks.py`: keep/use lake gold fallback for history and technical data when DuckDB is unavailable.
- Create `backend_v2/src/services/etl_marker.py`: read/write `lake/status/last_etl_run.json`.
- Create or modify an ETL entrypoint script if one already exists after inspection: after successful ETL, write the marker.
- Modify `package.json`: add explicit scripts for `backend:dev`, `etl:update`, and optionally `dev:after-etl`.
- Extend `backend_v2/tests/test_snapshot_mode.py`: cover read-only behavior and marker parsing.

---

## Task 1: Add Minimal Runtime Switches

**Files:**
- Modify: `backend_v2/src/settings.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add:

```python
class SmallRuntimeModeSettingsTests(unittest.TestCase):
    def test_backend_defaults_to_no_request_duckdb_writes_and_no_startup_etl(self):
        from src.settings import Settings

        settings = Settings()

        self.assertFalse(settings.duckdb_request_writes_enabled)
        self.assertFalse(settings.etl_run_on_backend_start)
```

- [ ] **Step 2: Run the test**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.SmallRuntimeModeSettingsTests -v
```

Expected: FAIL because the settings do not exist.

- [ ] **Step 3: Implement settings**

In `backend_v2/src/settings.py`, inside `Settings`, add:

```python
    duckdb_request_writes_enabled: bool = False
    etl_run_on_backend_start: bool = False
```

- [ ] **Step 4: Verify**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.SmallRuntimeModeSettingsTests -v
```

Expected: PASS.

---

## Task 2: Stop Request-Time Technical Cache Writes

**Files:**
- Modify: `backend_v2/src/cache.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add to technical cache tests:

```python
async def test_save_technical_cache_skips_duckdb_when_request_writes_disabled(self):
    from src import cache

    result = await cache._save_technical_cache(
        "FPT",
        None,
        None,
        180,
        180,
        "2026-05-26",
        {"symbol": "FPT"},
    )

    self.assertIsNone(result)
```

- [ ] **Step 2: Run the test**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.TechnicalCacheTests.test_save_technical_cache_skips_duckdb_when_request_writes_disabled -v
```

Expected: FAIL if `_save_technical_cache` still attempts DuckDB writes.

- [ ] **Step 3: Implement skip**

In `backend_v2/src/cache.py`, import:

```python
from src.settings import get_settings
```

At the top of `_save_technical_cache`, add:

```python
    if not get_settings().duckdb_request_writes_enabled:
        return None
```

- [ ] **Step 4: Verify**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.TechnicalCacheTests -v
```

Expected: PASS.

---

## Task 3: Keep Lake Gold Fallback for API Reads

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Confirm existing fallback behavior**

Keep or add this test:

```python
async def test_history_data_falls_back_to_gold_lake_when_duckdb_is_empty(self):
    from src.routes import stocks

    async def empty_history(*args, **kwargs):
        return []

    original_load = stocks.fetcher_service.load_history_from_db_async
    original_root = stocks.REPO_ROOT

    with TemporaryDirectory() as tmp:
        lake_path = Path(tmp) / "lake" / "gold" / "market_features" / "by_symbol" / "symbol=FPT"
        lake_path.mkdir(parents=True)
        pd.DataFrame(
            [
                {"symbol": "FPT", "data_date": "2026-05-25", "open_price": 73.5, "high_price": 75.0, "low_price": 73.0, "close_price": 74.0, "volume": 1000},
                {"symbol": "FPT", "data_date": "2026-05-26", "open_price": 74.0, "high_price": 75.5, "low_price": 73.5, "close_price": 74.5, "volume": 2000},
            ]
        ).to_parquet(lake_path / "latest.parquet", index=False)

        stocks.fetcher_service.load_history_from_db_async = empty_history
        stocks.REPO_ROOT = Path(tmp)
        try:
            records = await stocks._load_history_data("FPT", start_date=None, end_date=None, limit=1)
        finally:
            stocks.fetcher_service.load_history_from_db_async = original_load
            stocks.REPO_ROOT = original_root

    self.assertEqual(records[0]["close"], 74.5)
```

- [ ] **Step 2: Run the test**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_history_data_falls_back_to_gold_lake_when_duckdb_is_empty -v
```

Expected: PASS if the current fallback patch is present.

- [ ] **Step 3: If missing, implement minimal fallback**

In `backend_v2/src/routes/stocks.py`, `_load_history_data()` should:

```python
records = await fetcher_service.load_history_from_db_async(...)
if records:
    return records
return _load_history_from_gold_lake(...)
```

`_load_history_from_gold_lake()` reads:

```text
lake/gold/market_features/by_symbol/symbol=<SYMBOL>/latest.parquet
```

and maps `data_date/open_price/high_price/low_price/close_price/volume` to API `time/open/high/low/close/volume`.

- [ ] **Step 4: Verify technical endpoint**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from src.main import app; c=TestClient(app, raise_server_exceptions=False); r=c.get('/api/stocks/FPT/technical?limit=180'); print(r.status_code); print(r.json().get('count'), r.json().get('data_status'))"
```

Expected: `200`, count > `0`, `DATA_AVAILABLE` when lake gold FPT exists.

---

## Task 4: Add ETL Marker File

**Files:**
- Create: `backend_v2/src/services/etl_marker.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write marker tests**

Add:

```python
class EtlMarkerTests(unittest.TestCase):
    def test_write_and_read_etl_marker(self):
        from src.services.etl_marker import read_last_etl_marker, write_last_etl_marker

        with TemporaryDirectory() as tmp:
            marker = write_last_etl_marker(
                repo_root=Path(tmp),
                run_id="20260527T001500",
                data_date="2026-05-26",
                status="success",
                symbols=["FPT", "ACB"],
            )
            loaded = read_last_etl_marker(repo_root=Path(tmp))

        self.assertTrue(marker.exists())
        self.assertEqual(loaded["run_id"], "20260527T001500")
        self.assertEqual(loaded["data_date"], "2026-05-26")
        self.assertEqual(loaded["status"], "success")
        self.assertEqual(loaded["symbols"], ["FPT", "ACB"])
```

- [ ] **Step 2: Run test**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.EtlMarkerTests -v
```

Expected: FAIL because marker service does not exist.

- [ ] **Step 3: Implement marker service**

Create `backend_v2/src/services/etl_marker.py`:

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.settings import REPO_ROOT


def _marker_path(repo_root: Path | None = None) -> Path:
    return Path(repo_root or REPO_ROOT) / "lake" / "status" / "last_etl_run.json"


def write_last_etl_marker(
    run_id: str,
    data_date: str,
    status: str,
    symbols: list[str],
    repo_root: Path | None = None,
) -> Path:
    path = _marker_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "data_date": data_date,
        "status": status,
        "symbols": symbols,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_last_etl_marker(repo_root: Path | None = None) -> dict[str, Any]:
    path = _marker_path(repo_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
```

- [ ] **Step 4: Verify**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.EtlMarkerTests -v
```

Expected: PASS.

---

## Task 5: Wire Marker Into ETL Completion

**Files:**
- Inspect and modify the current ETL entrypoint found by `rg -n "etl|market_features|upsert_market_features|run_id" backend_v2 scripts .`
- Test: use the smallest existing ETL/unit test if present, otherwise smoke manually.

- [ ] **Step 1: Find ETL entrypoint**

Run:

```powershell
rg -n "etl|market_features|upsert_market_features|run_id" backend_v2 .
```

Expected: identify the command/script that writes `lake/gold/market_features` or calls `upsert_market_features`.

- [ ] **Step 2: Add marker write after successful ETL**

At the end of the successful ETL path, call:

```python
from src.services.etl_marker import write_last_etl_marker

write_last_etl_marker(
    run_id=run_id,
    data_date=str(max_date),
    status="success",
    symbols=sorted(symbols),
)
```

If the ETL script is outside the `src` package, use the matching import path already used by that script.

- [ ] **Step 3: Add failure marker if the ETL wrapper has top-level exception handling**

In the exception path:

```python
write_last_etl_marker(
    run_id=run_id,
    data_date="",
    status="failed",
    symbols=sorted(symbols),
)
```

- [ ] **Step 4: Smoke ETL marker**

Run the ETL command in a separate terminal while backend is stopped.

Expected:

```text
lake/status/last_etl_run.json
```

exists and contains `"status": "success"`.

---

## Task 6: Add Explicit npm Scripts

**Files:**
- Modify: `package.json`

- [ ] **Step 1: Add scripts**

In `package.json`, add scripts matching the actual ETL entrypoint found in Task 5:

```json
{
  "backend:dev": "cd backend_v2 && ..\\.venv\\Scripts\\python.exe -m uvicorn src.main:app --reload",
  "etl:update": "cd backend_v2 && ..\\.venv\\Scripts\\python.exe -m <ETL_MODULE>",
  "dev:after-etl": "npm run etl:update && npm run backend:dev"
}
```

Replace `<ETL_MODULE>` with the real module.

- [ ] **Step 2: Verify backend script**

```powershell
npm.cmd run backend:dev
```

Expected: backend starts on `127.0.0.1:8000`.

- [ ] **Step 3: Verify ETL script with backend stopped**

```powershell
npm.cmd run etl:update
```

Expected: ETL completes and marker updates.

---

## Task 7: Final Verification

- [ ] **Step 1: Run backend tests**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
..\.venv\Scripts\python.exe -m compileall src
```

Expected: PASS.

- [ ] **Step 2: Run frontend type-check**

```powershell
npm.cmd run type-check
```

Expected: PASS. If sandbox blocks `node_modules/.tmp/tsconfig.app.tsbuildinfo`, rerun with approved escalation.

- [ ] **Step 3: Manual workflow rule**

Use this operating rule:

```text
Stop backend -> run npm run etl:update -> start npm run backend:dev
```

Do not run ETL while `uvicorn --reload` is active.

- [ ] **Step 4: Smoke app pages**

Start backend and frontend. Verify:

- Stock Detail price card has a real price.
- TradingView chart renders.
- Technical Analysis renders.
- Market Overview index values and chart render.

---

## Self-Review

**Spec coverage:** This plan avoids DuckDB conflicts by operational separation first, not by a large architecture rewrite. It keeps current fallback fixes and adds marker visibility for future “has ETL run today?” checks.

**Placeholder scan:** Only `<ETL_MODULE>` remains because the exact ETL entrypoint must be identified in Task 5 before editing `package.json`. This is an intentional inspection step, not an implementation gap.

**Type consistency:** Settings names, marker service function names, and expected paths are consistent across tasks.

