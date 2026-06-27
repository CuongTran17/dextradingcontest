# DuckDB Market Serving Mart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist the fully transformed daily market feature dataset into DuckDB as a queryable serving mart, while keeping parquet/gold outputs as the audit trail.

**Architecture:** ETL continues Extract -> Transform -> parquet/gold. After `build_full_dataset()` and quality validation, the same `dataset` is upserted into DuckDB table `market_features_daily` keyed by `(symbol, data_date)`. DuckDB becomes the fast serving/query layer for dashboards, screeners, and future analytics; realtime remains out of scope.

**Tech Stack:** Python, pandas, DuckDB, FastAPI backend repository layer, existing ETL modules, pytest, compileall.

---

## Current State

- `etl/transform/build_dataset.py` produces the canonical transformed `dataset` with `FINAL_COLUMNS`.
- `etl/load_to_parquet.py` writes:
  - `lake/processed/market_data_<run_id>.parquet`
  - `lake/processed/by_symbol/<SYMBOL>/latest.parquet`
  - `lake/gold/market_features/latest.parquet`
  - `lake/gold/market_features/by_symbol/...`
- `etl/run_etl.py` currently loads:
  - OHLCV into DuckDB `daily_ohlcv`
  - technical cache into DuckDB `technical_cache`
  - overview/financial/news/events into MySQL
- `backend_v2/src/database/market_duckdb.py` owns DuckDB schema and methods for `daily_ohlcv` and `technical_cache`.
- Realtime/intraday is intentionally out of scope for this phase.

## Scope

Add in this phase:

- DuckDB table `market_features_daily`: one wide row per `symbol + data_date`.
- DuckDB table `market_feature_runs`: lightweight lineage/metadata for each ETL load.
- ETL load function `load_market_features_to_duckdb()`.
- Repository methods to upsert and query market features.
- Focused tests for schema creation, upsert idempotency, and schema evolution.

Do not add in this phase:

- Realtime tick ingestion changes.
- New frontend screens.
- Migration of overview/financial/news/events MySQL caches.
- Replacement of parquet/gold audit outputs.

## Proposed DuckDB Tables

`market_features_daily`:

```sql
CREATE TABLE IF NOT EXISTS market_features_daily (
    symbol VARCHAR NOT NULL,
    data_date DATE NOT NULL,
    run_id VARCHAR NOT NULL,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

The implementation should add dataset columns dynamically from the pandas DataFrame. This avoids hardcoding every feature column and keeps the mart compatible when `FINAL_COLUMNS` grows.

`market_feature_runs`:

```sql
CREATE TABLE IF NOT EXISTS market_feature_runs (
    run_id VARCHAR PRIMARY KEY,
    row_count BIGINT NOT NULL,
    symbol_count BIGINT NOT NULL,
    min_date DATE,
    max_date DATE,
    source_path VARCHAR,
    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Upsert rule:

- Normalize `symbol` uppercase.
- Normalize `data_date` to date.
- Delete rows in DuckDB where `(symbol, data_date)` appears in the incoming dataset.
- Insert all incoming rows with `run_id` and `loaded_at`.
- Insert or replace one `market_feature_runs` row for lineage.

---

### Task 1: Add DuckDB Feature Mart Repository Methods

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Write failing tests**

Append to `backend_v2/tests/test_market_duckdb.py`:

```python
import pandas as pd


def test_upsert_market_features_replaces_symbol_date_rows(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    first = pd.DataFrame(
        [
            {"symbol": "fpt", "data_date": "2026-05-15", "close_price": 100.0, "rsi_14": 55.0},
            {"symbol": "VCB", "data_date": "2026-05-15", "close_price": 80.0, "rsi_14": 45.0},
        ]
    )
    second = pd.DataFrame(
        [
            {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "rsi_14": 56.0},
        ]
    )

    assert repo.upsert_market_features(first, run_id="run-1", source_path="first.parquet") == 2
    assert repo.upsert_market_features(second, run_id="run-2", source_path="second.parquet") == 1

    rows = repo.load_market_features(symbols=["FPT", "VCB"], columns=["symbol", "data_date", "close_price", "rsi_14", "run_id"])

    assert rows == [
        {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "rsi_14": 56.0, "run_id": "run-2"},
        {"symbol": "VCB", "data_date": "2026-05-15", "close_price": 80.0, "rsi_14": 45.0, "run_id": "run-1"},
    ]
```

Append:

```python
def test_market_features_adds_new_columns_without_losing_existing_rows(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    repo.upsert_market_features(
        pd.DataFrame([{"symbol": "FPT", "data_date": "2026-05-14", "close_price": 100.0}]),
        run_id="run-1",
    )
    repo.upsert_market_features(
        pd.DataFrame([{"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "new_factor": 9.5}]),
        run_id="run-2",
    )

    rows = repo.load_market_features(symbols=["FPT"], columns=["symbol", "data_date", "close_price", "new_factor"])

    assert rows == [
        {"symbol": "FPT", "data_date": "2026-05-14", "close_price": 100.0, "new_factor": None},
        {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0, "new_factor": 9.5},
    ]
```

- [ ] **Step 2: Run red tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: FAIL because `upsert_market_features()` and `load_market_features()` do not exist.

- [ ] **Step 3: Add schema helpers**

In `backend_v2/src/database/market_duckdb.py`, add to `ensure_schema()`:

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS market_features_daily (
        symbol VARCHAR NOT NULL,
        data_date DATE NOT NULL,
        run_id VARCHAR NOT NULL,
        loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS market_feature_runs (
        run_id VARCHAR PRIMARY KEY,
        row_count BIGINT NOT NULL,
        symbol_count BIGINT NOT NULL,
        min_date DATE,
        max_date DATE,
        source_path VARCHAR,
        loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)
```

Add helper methods:

```python
def _table_columns(self, conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    return {str(row[1]) for row in rows}


def _duckdb_type_for_series(self, series: pd.Series) -> str:
    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"
    if pd.api.types.is_float_dtype(series):
        return "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"
    return "VARCHAR"
```

- [ ] **Step 4: Add market feature methods**

Add:

```python
def _prepare_market_features(self, dataset: pd.DataFrame, run_id: str) -> pd.DataFrame:
    if dataset.empty:
        return pd.DataFrame()
    if "symbol" not in dataset.columns or "data_date" not in dataset.columns:
        raise ValueError("market feature dataset requires symbol and data_date columns")

    frame = dataset.copy()
    frame["symbol"] = frame["symbol"].astype(str).str.upper()
    frame["data_date"] = pd.to_datetime(frame["data_date"], errors="coerce").dt.date
    frame = frame.dropna(subset=["symbol", "data_date"])
    frame = frame.drop_duplicates(["symbol", "data_date"], keep="last")
    frame["run_id"] = run_id
    frame["loaded_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
    return frame


def _ensure_market_feature_columns(self, conn: duckdb.DuckDBPyConnection, frame: pd.DataFrame) -> None:
    existing = self._table_columns(conn, "market_features_daily")
    for column in frame.columns:
        if column in existing:
            continue
        col_type = self._duckdb_type_for_series(frame[column])
        conn.execute(f'ALTER TABLE market_features_daily ADD COLUMN "{column}" {col_type}')
        existing.add(column)


def upsert_market_features(self, dataset: pd.DataFrame, run_id: str, source_path: str | None = None) -> int:
    frame = self._prepare_market_features(dataset, run_id)
    if frame.empty:
        return 0

    with self.connect() as conn:
        self._ensure_market_feature_columns(conn, frame)
        conn.register("incoming_market_features", frame)
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute(
                """
                DELETE FROM market_features_daily AS target
                USING incoming_market_features AS incoming
                WHERE target.symbol = incoming.symbol
                  AND target.data_date = incoming.data_date
                """
            )
            columns = list(frame.columns)
            quoted = ", ".join(f'"{column}"' for column in columns)
            conn.execute(
                f"""
                INSERT INTO market_features_daily ({quoted})
                SELECT {quoted}
                FROM incoming_market_features
                """
            )
            conn.execute(
                "DELETE FROM market_feature_runs WHERE run_id = ?",
                [run_id],
            )
            conn.execute(
                """
                INSERT INTO market_feature_runs
                    (run_id, row_count, symbol_count, min_date, max_date, source_path, loaded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    run_id,
                    int(len(frame)),
                    int(frame["symbol"].nunique()),
                    frame["data_date"].min(),
                    frame["data_date"].max(),
                    source_path,
                    frame["loaded_at"].iloc[0],
                ],
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.unregister("incoming_market_features")
    return int(len(frame))
```

Add:

```python
def load_market_features(
    self,
    symbols: list[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    columns: list[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    requested = columns or ["*"]
    if requested == ["*"]:
        select_sql = "*"
    else:
        available = self._table_columns(self.connect(), "market_features_daily")
        missing = [column for column in requested if column not in available]
        if missing:
            raise ValueError(f"Unknown market feature columns: {missing}")
        select_sql = ", ".join(f'"{column}"' for column in requested)

    where = []
    params: list[Any] = []
    if symbols:
        normalized = [symbol.strip().upper() for symbol in symbols]
        placeholders = ", ".join("?" for _ in normalized)
        where.append(f"symbol IN ({placeholders})")
        params.extend(normalized)
    if start_date:
        where.append("data_date >= ?")
        params.append(start_date)
    if end_date:
        where.append("data_date <= ?")
        params.append(end_date)

    query = f"SELECT {select_sql} FROM market_features_daily"
    if where:
        query += " WHERE " + " AND ".join(where)
    query += " ORDER BY symbol, data_date"
    if limit is not None:
        query += " LIMIT ?"
        params.append(max(limit, 1))

    with self.connect() as conn:
        result = conn.execute(query, params)
        names = [item[0] for item in result.description]
        rows = result.fetchall()

    output = []
    for row in rows:
        item = {}
        for key, value in zip(names, row):
            item[key] = value.isoformat() if isinstance(value, date) else value
        output.append(item)
    return output
```

Also add delegating methods to `LazyMarketDuckDB`.

- [ ] **Step 5: Run green tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2\src\database\market_duckdb.py backend_v2\tests\test_market_duckdb.py
git commit -m "feat: add duckdb market feature mart"
```

### Task 2: Add ETL Loader For Market Feature Mart

**Files:**
- Modify: `etl/load_to_duckdb.py`
- Modify: `etl/run_etl.py`
- Test: `tests/test_load_to_duckdb.py`

- [ ] **Step 1: Write failing loader test**

Append to `tests/test_load_to_duckdb.py`:

```python
from etl.load_to_duckdb import load_market_features_to_duckdb


def test_load_market_features_to_duckdb(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    dataset = pd.DataFrame(
        [
            {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 108.0, "rsi_14": 50.0},
            {"symbol": "VCB", "data_date": "2026-05-15", "close_price": 90.0, "rsi_14": 60.0},
        ]
    )

    assert load_market_features_to_duckdb(dataset=dataset, repo=repo, run_id="run-test", source_path="market.parquet") == 2

    rows = repo.load_market_features(columns=["symbol", "data_date", "close_price", "rsi_14", "run_id"])
    assert rows == [
        {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 108.0, "rsi_14": 50.0, "run_id": "run-test"},
        {"symbol": "VCB", "data_date": "2026-05-15", "close_price": 90.0, "rsi_14": 60.0, "run_id": "run-test"},
    ]
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib tests\test_load_to_duckdb.py -q
```

Expected: FAIL because `load_market_features_to_duckdb` does not exist.

- [ ] **Step 3: Implement loader**

In `etl/load_to_duckdb.py`, add:

```python
def load_market_features_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
    run_id: str | None = None,
    source_path: str | None = None,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            log.error("No parquet files found in processed dir")
            return 0
        dataset = pd.read_parquet(latest_file)
        source_path = source_path or str(latest_file)

    resolved_run_id = run_id or (cfg.run_id if cfg else "manual")
    total = repo.upsert_market_features(dataset, run_id=resolved_run_id, source_path=source_path)
    log.info("Loaded %d market feature rows into DuckDB", total)
    return total
```

- [ ] **Step 4: Wire ETL load phase**

In `etl/run_etl.py`, update import:

```python
from etl.load_to_duckdb import (
    load_daily_price_to_duckdb,
    load_eod_rows_to_duckdb,
    load_market_features_to_duckdb,
    load_technical_cache_to_duckdb,
)
```

After `processed_parquet = save_processed_parquet(dataset, cfg)` and inside `if cfg.enable_market_duckdb_load:`, add:

```python
load_market_features_to_duckdb(cfg, dataset, run_id=cfg.run_id, source_path=str(processed_parquet))
metadata.artifacts["duckdb_market_features_load"] = "enabled"
```

If disabled:

```python
metadata.artifacts["duckdb_market_features_load"] = "disabled"
```

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py tests\test_load_to_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add etl\load_to_duckdb.py etl\run_etl.py tests\test_load_to_duckdb.py
git commit -m "feat: load transformed market features into duckdb"
```

### Task 3: Add Mart Inspection Utilities

**Files:**
- Create: `etl/inspect_duckdb_market_mart.py`
- Test: manual command

- [ ] **Step 1: Create inspection script**

Create `etl/inspect_duckdb_market_mart.py`:

```python
from __future__ import annotations

import duckdb

from backend_v2.src.database.market_duckdb import _resolve_duckdb_path


def main() -> None:
    db_path = _resolve_duckdb_path()
    with duckdb.connect(str(db_path), read_only=True) as conn:
        print("market_features_daily")
        print(conn.execute("select count(*) as rows, count(distinct symbol) as symbols, min(data_date), max(data_date) from market_features_daily").fetchone())
        print("market_feature_runs")
        print(conn.execute("select run_id, row_count, symbol_count, min_date, max_date, source_path, loaded_at from market_feature_runs order by loaded_at desc limit 5").fetchall())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run script after a test ETL/mart load**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.inspect_duckdb_market_mart
```

Expected: prints mart row/symbol/date counts and recent run lineage.

- [ ] **Step 3: Commit**

```powershell
git add etl\inspect_duckdb_market_mart.py
git commit -m "chore: add duckdb market mart inspection"
```

### Task 4: Backfill Mart From Latest Parquet Without Re-Extracting

**Files:**
- Create: `etl/backfill_duckdb_market_features.py`
- Test: manual command

- [ ] **Step 1: Create backfill script**

Create `etl/backfill_duckdb_market_features.py`:

```python
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from etl.load_to_duckdb import load_market_features_to_duckdb


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill DuckDB market_features_daily from an existing parquet file.")
    parser.add_argument("--parquet", default="lake/gold/market_features/latest.parquet")
    parser.add_argument("--run-id", default="backfill-latest")
    args = parser.parse_args()

    parquet_path = Path(args.parquet)
    if not parquet_path.exists():
        raise FileNotFoundError(parquet_path)

    dataset = pd.read_parquet(parquet_path)
    count = load_market_features_to_duckdb(dataset=dataset, run_id=args.run_id, source_path=str(parquet_path))
    print(f"Loaded {count} market feature rows from {parquet_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run backfill**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_duckdb_market_features --parquet lake\gold\market_features\latest.parquet --run-id backfill-latest
```

Expected: loads rows into `market_features_daily`.

- [ ] **Step 3: Inspect**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.inspect_duckdb_market_mart
```

Expected: counts match the parquet row count.

- [ ] **Step 4: Commit**

```powershell
git add etl\backfill_duckdb_market_features.py
git commit -m "chore: add duckdb market feature backfill"
```

### Task 5: Optional Backend Read Helper For Future APIs

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Add screener-style query test**

Append:

```python
def test_load_market_features_filters_dates_and_limit(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    repo.upsert_market_features(
        pd.DataFrame(
            [
                {"symbol": "FPT", "data_date": "2026-05-14", "close_price": 100.0},
                {"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0},
                {"symbol": "VCB", "data_date": "2026-05-15", "close_price": 90.0},
            ]
        ),
        run_id="run-1",
    )

    rows = repo.load_market_features(symbols=["FPT"], start_date=date(2026, 5, 15), columns=["symbol", "data_date", "close_price"])

    assert rows == [{"symbol": "FPT", "data_date": "2026-05-15", "close_price": 101.0}]
```

- [ ] **Step 2: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS if Task 1 filtering already supports this; otherwise implement the missing filter.

- [ ] **Step 3: Commit if code changed**

```powershell
git add backend_v2\src\database\market_duckdb.py backend_v2\tests\test_market_duckdb.py
git commit -m "test: cover duckdb market feature filters"
```

### Task 6: Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Run unit tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py tests\test_load_to_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 2: Compile**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: PASS.

- [ ] **Step 3: Backfill latest mart**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.backfill_duckdb_market_features --parquet lake\gold\market_features\latest.parquet --run-id backfill-latest
```

Expected: row count equals latest parquet row count.

- [ ] **Step 4: Inspect mart**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.inspect_duckdb_market_mart
```

Expected: nonzero rows, expected symbol count, valid date range, recent lineage row.

- [ ] **Step 5: Smoke import app**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.main import app; print(app.title)"
```

Expected: prints `VNStock Intraday API V2`.

---

## Recommended Priority

Do this before realtime work because it gives the app a clean market-data serving layer:

1. Persist transformed features into DuckDB.
2. Backfill from existing gold parquet.
3. Add query helpers for future screener/dashboard APIs.
4. Only then revisit realtime ingestion.

## Risks And Controls

- Schema drift: use dynamic DuckDB columns and tests for new columns.
- Duplicate rows: enforce delete-then-insert by `(symbol, data_date)` in one transaction.
- Auditability: keep parquet/gold as source-of-truth artifacts; DuckDB is serving/query layer.
- Large JSON/text fields: `news_headlines`, `event_headlines`, and Google News fields should stay `VARCHAR`; avoid indexing them.
- Dirty worktree: phase 1/2 changes and local generated data are currently present. Do not include `market_data.csv` or `check_vhm_db.py` in this work unless explicitly requested.

## Self-Review

- Spec coverage: plan focuses on DuckDB first and leaves realtime untouched.
- Placeholder scan: no TBD/TODO placeholders; each task includes files, code, commands, and expected results.
- Type consistency: `market_features_daily`, `market_feature_runs`, `upsert_market_features()`, `load_market_features()`, and `load_market_features_to_duckdb()` are used consistently.
