# DuckDB Technical Cache Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move `technical_cache` from MySQL to the same DuckDB market warehouse used by `daily_ohlcv`, then prepare gated cleanup of MySQL `daily_ohlcv` and `technical_cache`.

**Architecture:** Extend `backend_v2/src/database/market_duckdb.py` into the market-data repository for both OHLCV and technical indicator cache. Keep JSON/company/news/financial/user/business data in MySQL. Replace only the technical cache helpers in `backend_v2/src/cache.py` and the ETL technical cache loader so API contracts stay unchanged.

**Tech Stack:** FastAPI, DuckDB Python, pandas, SQLAlchemy/MySQL for remaining app/cache tables, pytest, Alembic.

---

## Current State

- Phase 1 already migrated durable OHLCV reads/writes to DuckDB at `lake/warehouse/market.duckdb`.
- DuckDB `daily_ohlcv` parity was checked: `8890` rows across `30` symbols.
- MySQL still retains `daily_ohlcv` and `technical_cache`.
- `technical_cache` is still read/written through SQLAlchemy model `TechnicalCache`.
- `technical_cache` is used by:
  - `backend_v2/src/cache.py`: `_load_technical_cache()` and `_save_technical_cache()`.
  - `backend_v2/src/routes/stocks.py`: `/api/stocks/{symbol}/technical`.
  - `backend_v2/src/routes/analysis.py`: `/api/analysis/{symbol}/generate`.
  - `etl/load_to_mysql.py`: `load_technical_cache()` warms the cache after ETL.

## Scope Decision

Move in phase 2:

- `technical_cache`

Clean up after parity gate:

- Remove MySQL table/model for `daily_ohlcv`.
- Remove MySQL table/model for `technical_cache`.

Keep in MySQL:

- `company_overview_cache`
- `financial_report_cache`
- `news_cache`
- `events_cache`
- `users`, `user_subscriptions`, `user_portfolios`, `ai_predictions`, `flash_sales`, `promotion_codes`

Do not touch:

- `market_data.csv`
- `market_data.parquet`
- `lake/processed`, `lake/gold`, except normal ETL output when explicitly running ETL
- user/payment/portfolio tables

Approved phase-2 decisions:

- After parity is OK, drop both MySQL `daily_ohlcv` and `technical_cache` in the same Alembic migration.
- Return `duckdb-technical-cache` for cached technical responses so frontend/logs can see the data source.
- Use the existing `enable_market_duckdb_load` flag for both OHLCV and technical cache because both are market data.

## Proposed DuckDB Technical Table

```sql
CREATE TABLE IF NOT EXISTS technical_cache (
    symbol VARCHAR NOT NULL,
    start_date DATE,
    end_date DATE,
    limit_value INTEGER NOT NULL DEFAULT 365,
    history_count INTEGER NOT NULL DEFAULT 0,
    history_last_time VARCHAR,
    payload_json VARCHAR NOT NULL,
    source VARCHAR NOT NULL DEFAULT 'duckdb',
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, start_date, end_date, limit_value)
);
```

Because SQL primary keys treat `NULL` specially across databases, implementation should not depend only on the primary key for nullable date signatures. Use explicit delete-then-insert with `IS NULL` handling for `(symbol, start_date, end_date, limit_value)`.

---

### Task 1: Add DuckDB Technical Repository Methods

**Files:**
- Modify: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Write failing tests for technical cache**

Append to `backend_v2/tests/test_market_duckdb.py`:

```python
from datetime import datetime, timezone


def test_upsert_and_load_technical_cache(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    payload = {"ohlcv": {"time": ["2026-05-15"]}, "indicators": {"rsi_14": [55.5]}}

    synced_at = repo.upsert_technical_cache(
        symbol="FPT",
        start_date=None,
        end_date=None,
        limit=365,
        history_count=1,
        history_last_time="2026-05-15",
        payload=payload,
        source="test",
    )
    row, loaded_payload = repo.load_technical_cache("FPT", start_date=None, end_date=None, limit=365)

    assert synced_at is not None
    assert row is not None
    assert row.symbol == "FPT"
    assert row.history_count == 1
    assert row.history_last_time == "2026-05-15"
    assert row.source == "test"
    assert isinstance(row.updated_at, datetime)
    assert loaded_payload == payload
```

- [ ] **Step 2: Add date-signature overwrite test**

Append:

```python
def test_technical_cache_overwrites_same_signature_only(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    repo.upsert_technical_cache("VCB", None, None, 365, 1, "2026-05-14", {"version": 1})
    repo.upsert_technical_cache("VCB", None, None, 365, 2, "2026-05-15", {"version": 2})
    repo.upsert_technical_cache("VCB", date(2026, 5, 1), date(2026, 5, 15), 365, 3, "2026-05-15", {"version": 3})

    default_row, default_payload = repo.load_technical_cache("VCB", None, None, 365)
    ranged_row, ranged_payload = repo.load_technical_cache("VCB", date(2026, 5, 1), date(2026, 5, 15), 365)

    assert default_row.history_count == 2
    assert default_payload == {"version": 2}
    assert ranged_row.history_count == 3
    assert ranged_payload == {"version": 3}
```

- [ ] **Step 3: Run tests to verify red**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: FAIL because `MarketDuckDB.upsert_technical_cache` and `load_technical_cache` do not exist.

- [ ] **Step 4: Implement row dataclass and repository methods**

In `backend_v2/src/database/market_duckdb.py`, add imports:

```python
import json
from dataclasses import dataclass
```

Add after `_to_date()`:

```python
def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    return _to_date(value)


@dataclass(frozen=True)
class TechnicalCacheRow:
    symbol: str
    start_date: date | None
    end_date: date | None
    limit_value: int
    history_count: int
    history_last_time: str | None
    payload_json: str
    source: str
    updated_at: datetime
```

Extend `ensure_schema()`:

```python
conn.execute(
    """
    CREATE TABLE IF NOT EXISTS technical_cache (
        symbol VARCHAR NOT NULL,
        start_date DATE,
        end_date DATE,
        limit_value INTEGER NOT NULL DEFAULT 365,
        history_count INTEGER NOT NULL DEFAULT 0,
        history_last_time VARCHAR,
        payload_json VARCHAR NOT NULL,
        source VARCHAR NOT NULL DEFAULT 'duckdb',
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)
```

Add helper methods:

```python
def _technical_where_clause(self, start_date: date | None, end_date: date | None) -> tuple[str, list[Any]]:
    clauses = ["symbol = ?", "limit_value = ?"]
    params: list[Any] = []
    if start_date is None:
        clauses.append("start_date IS NULL")
    else:
        clauses.append("start_date = ?")
        params.append(start_date)
    if end_date is None:
        clauses.append("end_date IS NULL")
    else:
        clauses.append("end_date = ?")
        params.append(end_date)
    return " AND ".join(clauses), params
```

Add methods:

```python
def upsert_technical_cache(
    self,
    symbol: str,
    start_date: date | None,
    end_date: date | None,
    limit: int,
    history_count: int,
    history_last_time: str | None,
    payload: dict[str, Any],
    source: str = "duckdb",
) -> str:
    normalized = symbol.strip().upper()
    safe_start = _optional_date(start_date)
    safe_end = _optional_date(end_date)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    where_sql, date_params = self._technical_where_clause(safe_start, safe_end)

    with self.connect() as conn:
        conn.execute("BEGIN TRANSACTION")
        try:
            conn.execute(
                f"DELETE FROM technical_cache WHERE {where_sql}",
                [normalized, int(limit), *date_params],
            )
            conn.execute(
                """
                INSERT INTO technical_cache
                    (symbol, start_date, end_date, limit_value, history_count, history_last_time, payload_json, source, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [normalized, safe_start, safe_end, int(limit), int(history_count), history_last_time, payload_json, source, now],
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return now.replace(tzinfo=timezone.utc).isoformat()


def load_technical_cache(
    self,
    symbol: str,
    start_date: date | None,
    end_date: date | None,
    limit: int,
) -> tuple[TechnicalCacheRow | None, dict[str, Any] | None]:
    normalized = symbol.strip().upper()
    safe_start = _optional_date(start_date)
    safe_end = _optional_date(end_date)
    where_sql, date_params = self._technical_where_clause(safe_start, safe_end)

    with self.connect() as conn:
        record = conn.execute(
            f"""
            SELECT symbol, start_date, end_date, limit_value, history_count, history_last_time, payload_json, source, updated_at
            FROM technical_cache
            WHERE {where_sql}
            LIMIT 1
            """,
            [normalized, int(limit), *date_params],
        ).fetchone()

    if record is None:
        return None, None

    row = TechnicalCacheRow(
        symbol=record[0],
        start_date=record[1],
        end_date=record[2],
        limit_value=int(record[3]),
        history_count=int(record[4]),
        history_last_time=record[5],
        payload_json=record[6],
        source=record[7],
        updated_at=record[8].replace(tzinfo=timezone.utc) if record[8].tzinfo is None else record[8],
    )
    payload = json.loads(row.payload_json)
    return row, payload if isinstance(payload, dict) else {}
```

Extend `LazyMarketDuckDB` with the same two methods delegating to `_get_repo()`.

- [ ] **Step 5: Run tests to verify green**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2\src\database\market_duckdb.py backend_v2\tests\test_market_duckdb.py
git commit -m "feat: add duckdb technical cache repository"
```

### Task 2: Move Runtime Technical Cache Helpers To DuckDB

**Files:**
- Modify: `backend_v2/src/cache.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Replace technical-only imports**

In `backend_v2/src/cache.py`, change:

```python
from src.database.models import FinancialReportCache, TechnicalCache
```

To:

```python
from src.database.market_duckdb import TechnicalCacheRow, market_repo
from src.database.models import FinancialReportCache
```

- [ ] **Step 2: Remove `_apply_date_filters()`**

Delete:

```python
def _apply_date_filters(query: Any, start_date: Any, end_date: Any) -> Any:
    query = query.where(TechnicalCache.start_date.is_(None) if start_date is None else TechnicalCache.start_date == start_date)
    query = query.where(TechnicalCache.end_date.is_(None) if end_date is None else TechnicalCache.end_date == end_date)
    return query
```

- [ ] **Step 3: Change `_load_technical_cache()` implementation**

Replace the function body with:

```python
async def _load_technical_cache(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
) -> tuple[Optional[TechnicalCacheRow], Optional[dict[str, Any]]]:
    return await asyncio.to_thread(
        market_repo.load_technical_cache,
        symbol,
        start_date,
        end_date,
        limit,
    )
```

Add `import asyncio` at the top of the file.

- [ ] **Step 4: Change `_save_technical_cache()` implementation**

Replace the function body with:

```python
async def _save_technical_cache(
    symbol: str,
    start_date: Optional[date],
    end_date: Optional[date],
    limit: int,
    history_count: int,
    history_last_time: Optional[str],
    payload: dict[str, Any],
) -> Optional[str]:
    try:
        return await asyncio.to_thread(
            market_repo.upsert_technical_cache,
            symbol,
            start_date,
            end_date,
            limit,
            history_count,
            history_last_time,
            payload,
            "duckdb",
        )
    except Exception as exc:
        logger.warning("Failed to save DuckDB technical cache for %s: %s", symbol, exc)
        return None
```

- [ ] **Step 5: Update module docstring**

Change docstring first paragraph to:

```python
"""Cache helpers.

Provides MySQL-backed helpers for symbol payload caches and financial-report
caches, plus DuckDB-backed helpers for technical-indicator cache.
"""
```

- [ ] **Step 6: Compile**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add backend_v2\src\cache.py
git commit -m "refactor: use duckdb for runtime technical cache"
```

### Task 3: Move ETL Technical Cache Warmup To DuckDB

**Files:**
- Modify: `etl/load_to_duckdb.py`
- Modify: `etl/load_to_mysql.py`
- Modify: `etl/run_etl.py`
- Test: `tests/test_load_to_duckdb.py`

- [ ] **Step 1: Write failing ETL loader test**

Append to `tests/test_load_to_duckdb.py`:

```python
from etl.load_to_duckdb import load_technical_cache_to_duckdb


def test_load_technical_cache_to_duckdb(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    dataset = pd.DataFrame(
        [
            {"symbol": "FPT", "data_date": "2026-05-14", "open_price": 1, "high_price": 2, "low_price": 1, "close_price": 2, "volume": 10},
            {"symbol": "FPT", "data_date": "2026-05-15", "open_price": 2, "high_price": 3, "low_price": 2, "close_price": 3, "volume": 20},
        ]
    )

    assert load_technical_cache_to_duckdb(dataset=dataset, repo=repo, limit=365) == 1
    row, payload = repo.load_technical_cache("FPT", None, None, 365)

    assert row.history_count == 2
    assert row.history_last_time == "2026-05-15"
    assert payload["symbol"] == "FPT"
    assert "ohlcv" in payload
    assert "indicators" in payload
```

- [ ] **Step 2: Run red test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib tests\test_load_to_duckdb.py -q
```

Expected: FAIL because `load_technical_cache_to_duckdb` does not exist.

- [ ] **Step 3: Move technical payload helper to DuckDB loader**

In `etl/load_to_duckdb.py`, add:

```python
from backend_v2.src.services.technical_indicators import build_technical_payload
```

Add:

```python
def _technical_payload_from_processed(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("data_date").reset_index(drop=True)
    return build_technical_payload(
        symbol,
        frame,
        time_col="data_date",
        open_col="open_price",
        high_col="high_price",
        low_col="low_price",
        close_col="close_price",
        volume_col="volume",
    )


def load_technical_cache_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
    limit: int = 365,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            return 0
        dataset = pd.read_parquet(latest_file)

    total = 0
    for symbol, frame in dataset.groupby("symbol"):
        frame = frame.sort_values("data_date").tail(limit)
        if frame.empty:
            continue
        normalized = str(symbol).upper()
        payload = _technical_payload_from_processed(normalized, frame)
        repo.upsert_technical_cache(
            normalized,
            None,
            None,
            limit,
            len(frame),
            str(frame["data_date"].iloc[-1]),
            payload,
            "etl-processed",
        )
        total += 1
    log.info("Loaded %d technical cache rows into DuckDB", total)
    return total
```

- [ ] **Step 4: Leave compatibility wrapper in MySQL loader**

In `etl/load_to_mysql.py`, replace existing `load_technical_cache()` body with:

```python
def load_technical_cache(cfg: EtlConfig, dataset: pd.DataFrame | None = None, limit: int = 365) -> int:
    log.warning("load_technical_cache() now writes technical cache to DuckDB, not MySQL.")
    return load_technical_cache_to_duckdb(cfg=cfg, dataset=dataset, limit=limit)
```

Import `load_technical_cache_to_duckdb` from `etl.load_to_duckdb`.

- [ ] **Step 5: Update `load_all()` naming**

In `etl/load_to_mysql.py`, remove `"technical": load_technical_cache(cfg, dataset)` from `load_all()` because `load_all()` should only represent MySQL cache loads.

In `etl/run_etl.py`, import `load_technical_cache_to_duckdb`:

```python
from etl.load_to_duckdb import load_daily_price_to_duckdb, load_eod_rows_to_duckdb, load_technical_cache_to_duckdb
```

After `load_daily_price_to_duckdb(cfg, dataset)`, add:

```python
load_technical_cache_to_duckdb(cfg, dataset)
metadata.artifacts["duckdb_technical_cache_load"] = "enabled"
```

If `cfg.enable_market_duckdb_load` is false, set:

```python
metadata.artifacts["duckdb_technical_cache_load"] = "disabled"
```

- [ ] **Step 6: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py tests\test_load_to_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add etl\load_to_duckdb.py etl\load_to_mysql.py etl\run_etl.py tests\test_load_to_duckdb.py
git commit -m "feat: load technical cache into duckdb"
```

### Task 4: Migrate Existing MySQL Technical Cache To DuckDB

**Files:**
- Create: `etl/migrate_mysql_technical_cache_to_duckdb.py`

- [ ] **Step 1: Create migration script**

Create `etl/migrate_mysql_technical_cache_to_duckdb.py`:

```python
from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine, text

from backend_v2.src.database.market_duckdb import LazyMarketDuckDB, MarketDuckDB, market_repo
from backend_v2.src.settings import get_settings


def migrate(*, dry_run: bool = True, repo: MarketDuckDB | LazyMarketDuckDB = market_repo) -> int:
    settings = get_settings()
    engine = create_engine(settings.mysql_url)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT symbol, start_date, end_date, limit_value, history_count,
                       history_last_time, payload_json, source, updated_at
                FROM technical_cache
                ORDER BY symbol, limit_value, start_date, end_date
                """
            )
        ).mappings().all()

    if dry_run:
        print(f"DRY RUN: would migrate {len(rows)} technical_cache rows")
        return len(rows)

    total = 0
    for row in rows:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}
        repo.upsert_technical_cache(
            str(row["symbol"]).upper(),
            row["start_date"],
            row["end_date"],
            int(row["limit_value"]),
            int(row["history_count"]),
            row["history_last_time"],
            payload,
            str(row["source"] or "mysql-migrated"),
        )
        total += 1
    print(f"Migrated {total} technical_cache rows")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate MySQL technical_cache rows into DuckDB.")
    parser.add_argument("--execute", action="store_true", help="Write rows into DuckDB. Without this flag, dry-run only.")
    args = parser.parse_args()
    migrate(dry_run=not args.execute)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.migrate_mysql_technical_cache_to_duckdb
```

Expected: prints MySQL technical cache row count without writing.

- [ ] **Step 3: Execute only after user approval**

Run after approval:

```powershell
.\.venv\Scripts\python.exe -m etl.migrate_mysql_technical_cache_to_duckdb --execute
```

Expected: migrated count equals dry-run count.

- [ ] **Step 4: Commit**

```powershell
git add etl\migrate_mysql_technical_cache_to_duckdb.py
git commit -m "feat: add technical cache duckdb migration"
```

### Task 5: Parity And Runtime Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Compare MySQL and DuckDB counts**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from sqlalchemy import create_engine,text; from backend_v2.src.settings import get_settings; s=get_settings(); e=create_engine(s.mysql_url); print(e.connect().execute(text('select count(*) from technical_cache')).scalar())"
```

Run:

```powershell
.\.venv\Scripts\python.exe -c "import duckdb; con=duckdb.connect('lake/warehouse/market.duckdb', read_only=True); print(con.execute('select count(*) from technical_cache').fetchone()[0])"
```

Expected: counts match after migration.

- [ ] **Step 2: Verify API technical route**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from fastapi.testclient import TestClient; from src.main import app; c=TestClient(app); r=c.get('/api/stocks/VHM/technical?limit=365'); print(r.status_code); print(r.json().get('source')); print(r.json().get('data_status'))"
```

Expected: status `200`; source is `duckdb-technical-cache` for cached response.

- [ ] **Step 3: Verify analysis route import path**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.routes.analysis import router; print(len(router.routes))"
```

Expected: imports without MySQL `TechnicalCache` dependency.

- [ ] **Step 4: Run tests and compile**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest --import-mode=importlib backend_v2\tests\test_market_duckdb.py tests\test_load_to_duckdb.py -q
```

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: both pass.

- [ ] **Step 5: Commit verification/doc updates**

```powershell
git add README.md docs\superpowers\plans\2026-05-16-duckdb-technical-cache-phase-2.md
git commit -m "docs: plan duckdb technical cache cutover"
```

### Task 6: Gated MySQL Cleanup For Market Tables

**Files:**
- Modify: `backend_v2/src/database/models.py`
- Modify: `backend_v2/src/database/db.py`
- Modify: `backend_v2/init_database.sql`
- Create: `backend_v2/alembic/versions/20260516_0002_drop_market_tables.py`
- Modify: `README.md`

Gate: execute this task only after user confirms:

```text
DuckDB daily_ohlcv parity OK.
DuckDB technical_cache parity OK.
MySQL backup exists or rollback is not needed.
Proceed with MySQL table cleanup.
```

- [ ] **Step 1: Remove ORM models**

In `backend_v2/src/database/models.py`, delete:

```python
class DailyOHLCV(Base):
    ...

class TechnicalCache(Base):
    ...
```

Keep all user/app/cache JSON models.

- [ ] **Step 2: Remove legacy DDL maintenance for technical cache**

In `backend_v2/src/database/db.py`, remove `technical_cache` from `_ensure_payload_columns_longtext()`:

```python
"ALTER TABLE technical_cache MODIFY COLUMN payload_json LONGTEXT NOT NULL",
```

- [ ] **Step 3: Remove init SQL blocks**

In `backend_v2/init_database.sql`, delete the `CREATE TABLE IF NOT EXISTS daily_ohlcv` block and the `CREATE TABLE IF NOT EXISTS technical_cache` block.

- [ ] **Step 4: Create Alembic migration**

Create `backend_v2/alembic/versions/20260516_0002_drop_market_tables.py`:

```python
"""drop market tables moved to duckdb

Revision ID: 20260516_0002
Revises: 20260429_0001
Create Date: 2026-05-16
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260516_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("technical_cache")
    op.drop_table("daily_ohlcv")


def downgrade() -> None:
    op.create_table(
        "daily_ohlcv",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("open", sa.Float(), nullable=False, server_default="0"),
        sa.Column("high", sa.Float(), nullable=False, server_default="0"),
        sa.Column("low", sa.Float(), nullable=False, server_default="0"),
        sa.Column("close", sa.Float(), nullable=False, server_default="0"),
        sa.Column("volume", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "date", name="uq_daily_ohlcv_symbol_date"),
    )
    op.create_index("idx_symbol", "daily_ohlcv", ["symbol"])
    op.create_index("idx_date", "daily_ohlcv", ["date"])

    op.create_table(
        "technical_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(length=50), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("limit_value", sa.Integer(), nullable=False, server_default="365"),
        sa.Column("history_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("history_last_time", sa.String(length=32), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False, server_default="mysql"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol", "start_date", "end_date", "limit_value", name="uq_technical_cache_signature"),
    )
    op.create_index("idx_technical_cache_symbol", "technical_cache", ["symbol"])
    op.create_index("idx_technical_cache_updated_at", "technical_cache", ["updated_at"])
```

- [ ] **Step 5: Run cleanup verification**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Run:

```powershell
rg -n "DailyOHLCV|TechnicalCache|technical_cache|daily_ohlcv" backend_v2\src etl
```

Expected: no runtime MySQL references to ORM models or MySQL DDL helpers. DuckDB SQL references in `market_duckdb.py`, ETL migration scripts, and docs are expected.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2\src\database\models.py backend_v2\src\database\db.py backend_v2\init_database.sql backend_v2\alembic\versions\20260516_0002_drop_market_tables.py README.md
git commit -m "refactor: remove mysql market tables"
```

---

## Approval Questions

Answered:

1. Drop both MySQL `daily_ohlcv` and `technical_cache` in one Alembic migration after parity OK.
2. Cached `/api/stocks/{symbol}/technical` responses should return source `duckdb-technical-cache`.
3. ETL should load technical cache whenever `enable_market_duckdb_load=true`; do not add a separate flag.

## Risks And Controls

- Technical cache payloads are JSON blobs. Migration must parse JSON and skip/fail loudly on invalid payloads; do not silently write corrupt data.
- `start_date` and `end_date` are nullable cache-signature fields. Use explicit delete predicates with `IS NULL`, not naive equality.
- Cleanup is irreversible without backup/export. Do not run Alembic drop migration until after parity and user approval.
- Phase 1 worktree is currently dirty. Commit or intentionally carry phase 1 changes before starting phase 2 to avoid mixing unrelated edits.

## Self-Review

- Spec coverage: plan migrates `technical_cache`, keeps other MySQL cache/app tables, and includes gated cleanup for both market tables.
- Placeholder scan: no unresolved TBD/TODO placeholders; every task has files, code, commands, and expected outcomes.
- Type consistency: `TechnicalCacheRow`, `upsert_technical_cache()`, `load_technical_cache()`, and `load_technical_cache_to_duckdb()` are used consistently across tasks.
