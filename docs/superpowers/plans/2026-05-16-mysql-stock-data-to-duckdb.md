# MySQL Stock Data To DuckDB Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move durable stock/market OHLCV storage from MySQL `daily_ohlcv` into a local DuckDB database while keeping MySQL for user/app/business tables.

**Architecture:** Introduce a small DuckDB repository boundary for market data reads/writes. ETL continues to build parquet/gold snapshots, then writes daily OHLCV and tick EOD rows into DuckDB instead of MySQL. API routes keep their response contracts but read history/snapshot fallback from DuckDB through the fetcher service.

**Tech Stack:** FastAPI, SQLAlchemy/MySQL for app data, DuckDB Python package for market data, pandas/pyarrow parquet snapshots, pytest/compileall for verification.

---

## Current Project Map

- `backend_v2/src/database/models.py`: defines MySQL ORM models. `DailyOHLCV` is the stock table to remove from runtime market data usage.
- `backend_v2/src/database/db.py`: creates MySQL sync/async engines and initializes MySQL schema for app/cache tables.
- `backend_v2/src/services/vnstock_fetcher.py`: reads/writes `DailyOHLCV` for historical OHLCV, snapshot fallback, history preload, and intraday-to-daily aggregation.
- `backend_v2/src/routes/stocks.py`: calls `fetcher_service.load_history_from_db_async()` and labels history/technical sources as MySQL.
- `etl/load_to_mysql.py`: writes processed OHLCV and cache tables into MySQL. This should be split so OHLCV goes to DuckDB while JSON/cache tables can remain MySQL for now.
- `etl/run_etl.py`: orchestrates parquet writes, MySQL load, and tick EOD load.
- `backend_v2/init_database.sql`: creates `daily_ohlcv` alongside app/cache tables.
- `backend_v2/requirements.txt`: currently lacks `duckdb`.
- `README.md`: already states the long-term direction: MySQL keeps app/business data; stock/market data moves to parquet/DuckDB.

## Scope Decision For This Plan

Phase 1 should move only stock price tables:

- Move out of MySQL: `daily_ohlcv`.
- Keep in MySQL for now: `company_overview_cache`, `financial_report_cache`, `news_cache`, `events_cache`, `technical_cache`, `users`, `user_subscriptions`, `user_portfolios`, `ai_predictions`, `flash_sales`, `promotion_codes`.

Reason: overview/news/financial/technical caches are still SQLAlchemy ORM based and intertwined with async MySQL session helpers. Moving them at the same time would be a much larger cache-store migration. This plan still satisfies the durable stock-price goal and reduces risk.

Approved phase-1 decisions on 2026-05-16:

- Move `daily_ohlcv` first.
- Keep DuckDB at `lake/warehouse/market.duckdb`.
- Do not drop or delete MySQL `daily_ohlcv` in phase 1.
- Continue loading MySQL cache tables, including `technical_cache`; migrate `technical_cache` later in phase 2.

## Proposed DuckDB Layout

Default DB file:

```text
lake/warehouse/market.duckdb
```

New table:

```sql
CREATE TABLE IF NOT EXISTS daily_ohlcv (
    symbol VARCHAR NOT NULL,
    date DATE NOT NULL,
    open DOUBLE NOT NULL DEFAULT 0,
    high DOUBLE NOT NULL DEFAULT 0,
    low DOUBLE NOT NULL DEFAULT 0,
    close DOUBLE NOT NULL DEFAULT 0,
    volume BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date)
);
```

DuckDB supports primary keys, but implementation should still upsert defensively with delete+insert inside one transaction or `MERGE INTO` if the installed DuckDB version supports it.

---

### Task 1: Add DuckDB Configuration And Dependency

**Files:**
- Modify: `backend_v2/requirements.txt`
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Modify: `README.md`

- [ ] **Step 1: Add dependency**

Add to `backend_v2/requirements.txt`:

```text
duckdb>=1.1.0
```

- [ ] **Step 2: Add setting**

In `backend_v2/src/settings.py`, add a field near database settings:

```python
duckdb_path: str = "lake/warehouse/market.duckdb"
```

- [ ] **Step 3: Document env example**

In `backend_v2/.env.example`, add:

```env
DUCKDB_PATH=lake/warehouse/market.duckdb
```

- [ ] **Step 4: Update README architecture**

Adjust README wording so database responsibilities are explicit:

```text
MySQL: user/app/business data + JSON cache tables
DuckDB: durable stock OHLCV warehouse
Data Lake: raw / processed / gold parquet audit trail
```

- [ ] **Step 5: Verify import surface**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: compile succeeds after dependency/config changes.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2\requirements.txt backend_v2\src\settings.py backend_v2\.env.example README.md
git commit -m "chore: configure duckdb market warehouse"
```

### Task 2: Create DuckDB Market Repository

**Files:**
- Create: `backend_v2/src/database/market_duckdb.py`
- Test: `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Write repository tests first**

Create `backend_v2/tests/test_market_duckdb.py`:

```python
from datetime import date

from src.database.market_duckdb import MarketDuckDB


def test_upsert_and_load_history(tmp_path):
    db_path = tmp_path / "market.duckdb"
    repo = MarketDuckDB(db_path)

    repo.upsert_daily_rows(
        "FPT",
        [
            {"date": date(2026, 5, 14), "open": 100, "high": 110, "low": 99, "close": 108, "volume": 123},
            {"date": date(2026, 5, 15), "open": 108, "high": 112, "low": 107, "close": 111, "volume": 456},
        ],
    )
    repo.upsert_daily_rows(
        "FPT",
        [{"date": date(2026, 5, 15), "open": 109, "high": 113, "low": 108, "close": 112, "volume": 789}],
    )

    rows = repo.load_history("FPT", limit=10)

    assert rows == [
        {"time": "2026-05-14", "open": 100.0, "high": 110.0, "low": 99.0, "close": 108.0, "volume": 123},
        {"time": "2026-05-15", "open": 109.0, "high": 113.0, "low": 108.0, "close": 112.0, "volume": 789},
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_market_duckdb.py -q
```

Expected: FAIL because `src.database.market_duckdb` does not exist.

- [ ] **Step 3: Implement repository**

Create `backend_v2/src/database/market_duckdb.py`:

```python
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

from src.settings import REPO_ROOT, get_settings


def _resolve_duckdb_path(path_value: str | Path | None = None) -> Path:
    raw = Path(path_value or get_settings().duckdb_path)
    return raw if raw.is_absolute() else REPO_ROOT / raw


def _to_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


class MarketDuckDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _resolve_duckdb_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_ohlcv (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    open DOUBLE NOT NULL DEFAULT 0,
                    high DOUBLE NOT NULL DEFAULT 0,
                    low DOUBLE NOT NULL DEFAULT 0,
                    close DOUBLE NOT NULL DEFAULT 0,
                    volume BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                )
                """
            )

    def upsert_daily_rows(self, symbol: str, rows: Iterable[dict[str, Any]]) -> int:
        normalized = symbol.strip().upper()
        payload = [
            (
                normalized,
                _to_date(row["date"]),
                float(row.get("open") or 0),
                float(row.get("high") or 0),
                float(row.get("low") or 0),
                float(row.get("close") or 0),
                int(float(row.get("volume") or 0)),
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            for row in rows
        ]
        if not payload:
            return 0

        with self.connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.executemany(
                    "DELETE FROM daily_ohlcv WHERE symbol = ? AND date = ?",
                    [(item[0], item[1]) for item in payload],
                )
                conn.executemany(
                    """
                    INSERT INTO daily_ohlcv
                        (symbol, date, open, high, low, close, volume, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [(item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[7], item[7]) for item in payload],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return len(payload)

    def load_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 365,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT date, open, high, low, close, volume
            FROM daily_ohlcv
            WHERE symbol = ?
        """
        params: list[Any] = [symbol.strip().upper()]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ?"
        params.append(max(limit, 1))

        with self.connect() as conn:
            records = conn.execute(query, params).fetchall()

        rows = list(reversed(records))
        return [
            {
                "time": item[0].isoformat(),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": int(item[5]),
            }
            for item in rows
        ]


market_repo = MarketDuckDB()
```

- [ ] **Step 4: Run repository test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend_v2\src\database\market_duckdb.py backend_v2\tests\test_market_duckdb.py
git commit -m "feat: add duckdb market repository"
```

### Task 3: Route Historical Price Reads/Writes Through DuckDB

**Files:**
- Modify: `backend_v2/src/services/vnstock_fetcher.py`
- Test: extend `backend_v2/tests/test_market_duckdb.py`

- [ ] **Step 1: Add service-level tests for fetcher history shape**

Extend `backend_v2/tests/test_market_duckdb.py` with a repository-backed shape test:

```python
def test_repository_filters_dates_and_limit(tmp_path):
    db_path = tmp_path / "market.duckdb"
    repo = MarketDuckDB(db_path)
    repo.upsert_daily_rows(
        "VCB",
        [
            {"date": date(2026, 5, 13), "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
            {"date": date(2026, 5, 14), "open": 2, "high": 3, "low": 2, "close": 3, "volume": 20},
            {"date": date(2026, 5, 15), "open": 3, "high": 4, "low": 3, "close": 4, "volume": 30},
        ],
    )

    rows = repo.load_history("VCB", start_date=date(2026, 5, 14), end_date=date(2026, 5, 15), limit=1)

    assert rows == [
        {"time": "2026-05-15", "open": 3.0, "high": 4.0, "low": 3.0, "close": 4.0, "volume": 30}
    ]
```

- [ ] **Step 2: Run test**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS once repository behavior is stable.

- [ ] **Step 3: Modify fetcher imports**

In `backend_v2/src/services/vnstock_fetcher.py`, remove:

```python
from sqlalchemy import select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from src.database.db import AsyncSessionLocal, SessionLocal
from src.database.models import DailyOHLCV
```

Add:

```python
from src.database.market_duckdb import market_repo
```

Keep MySQL imports only if another non-market path still needs them.

- [ ] **Step 4: Replace `_upsert_daily_rows_sync` implementation**

Change:

```python
affected = await asyncio.to_thread(self._upsert_daily_rows_sync, normalized, rows)
```

so `_upsert_daily_rows_sync()` calls:

```python
return market_repo.upsert_daily_rows(symbol, rows)
```

- [ ] **Step 5: Replace history readers**

Change `load_history_from_db()` to return:

```python
return market_repo.load_history(
    normalized,
    start_date=start_date,
    end_date=end_date,
    limit=limit,
)
```

Change `load_history_from_db_async()` to:

```python
return await asyncio.to_thread(
    self.load_history_from_db,
    normalized,
    start_date,
    end_date,
    limit,
)
```

- [ ] **Step 6: Replace `aggregate_today_intraday_to_daily` write**

Remove `SessionLocal()` and `mysql_insert(DailyOHLCV)` from that method. After building `payload_rows`, group by symbol and write:

```python
affected = 0
for symbol in VN30_SYMBOLS:
    symbol_rows = [row for row in payload_rows if row["symbol"] == symbol]
    affected += market_repo.upsert_daily_rows(symbol, symbol_rows)
```

Then clear Redis intraday cache only after successful DuckDB writes.

- [ ] **Step 7: Update source labels**

In `backend_v2/src/routes/stocks.py`, change historical/technical source labels from `"mysql"` to `"duckdb"` where the payload is based on daily OHLCV:

```python
"source": "duckdb"
```

Keep cache labels such as `"mysql-financial-cache"` unchanged.

- [ ] **Step 8: Compile backend**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall backend_v2\src
```

Expected: no import or syntax errors.

- [ ] **Step 9: Commit**

```powershell
git add backend_v2\src\services\vnstock_fetcher.py backend_v2\src\routes\stocks.py backend_v2\tests\test_market_duckdb.py
git commit -m "feat: read stock history from duckdb"
```

### Task 4: Split ETL Loads So OHLCV Goes To DuckDB

**Files:**
- Create: `etl/load_to_duckdb.py`
- Modify: `etl/load_to_mysql.py`
- Modify: `etl/run_etl.py`
- Modify: `etl/config.py`
- Modify: `etl/scheduler.py`
- Test: `tests/test_load_to_duckdb.py`

- [ ] **Step 1: Write loader tests**

Create `tests/test_load_to_duckdb.py`:

```python
import pandas as pd

from backend_v2.src.database.market_duckdb import MarketDuckDB
from etl.load_to_duckdb import load_daily_price_to_duckdb, load_eod_rows_to_duckdb


def test_load_daily_price_to_duckdb(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    dataset = pd.DataFrame(
        [
            {
                "symbol": "FPT",
                "data_date": "2026-05-15",
                "open_price": 100,
                "high_price": 110,
                "low_price": 99,
                "close_price": 108,
                "volume": 1234,
            }
        ]
    )

    assert load_daily_price_to_duckdb(dataset=dataset, repo=repo) == 1
    assert repo.load_history("FPT", limit=1)[0]["close"] == 108.0


def test_load_eod_rows_to_duckdb(tmp_path):
    repo = MarketDuckDB(tmp_path / "market.duckdb")
    rows = [{"symbol": "MBB", "date": "2026-05-15", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10}]

    assert load_eod_rows_to_duckdb(rows, repo=repo) == 1
    assert repo.load_history("MBB", limit=1)[0]["time"] == "2026-05-15"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_load_to_duckdb.py -q
```

Expected: FAIL because `etl.load_to_duckdb` does not exist.

- [ ] **Step 3: Implement DuckDB ETL loader**

Create `etl/load_to_duckdb.py`:

```python
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from backend_v2.src.database.market_duckdb import MarketDuckDB, market_repo
from etl.config import EtlConfig
from etl.processed_files import latest_processed_parquet

log = logging.getLogger(__name__)


def _latest_processed_parquet(cfg: EtlConfig | None = None) -> Path | None:
    processed_dir = cfg.processed_dir if cfg else Path("lake/processed")
    return latest_processed_parquet(processed_dir)


def load_daily_price_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB = market_repo,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            log.error("No parquet files found in processed dir")
            return 0
        dataset = pd.read_parquet(latest_file)

    ohlcv_cols = ["symbol", "data_date", "open_price", "high_price", "low_price", "close_price", "volume"]
    if dataset is None or not all(col in dataset.columns for col in ohlcv_cols):
        log.error("Missing required OHLCV columns in dataset")
        return 0

    frame = dataset[ohlcv_cols].copy()
    frame = frame.rename(
        columns={
            "data_date": "date",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
    )
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype(int)

    total = 0
    for symbol, rows in frame.groupby(frame["symbol"].astype(str).str.upper()):
        total += repo.upsert_daily_rows(str(symbol), rows.to_dict(orient="records"))
    log.info("Loaded %d daily OHLCV rows into DuckDB", total)
    return total


def load_eod_rows_to_duckdb(rows: list[dict[str, Any]], repo: MarketDuckDB = market_repo) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            grouped[symbol].append(row)

    total = 0
    for symbol, symbol_rows in grouped.items():
        total += repo.upsert_daily_rows(symbol, symbol_rows)
    log.info("Loaded %d aggregated EOD rows into DuckDB", total)
    return total
```

- [ ] **Step 4: Rename MySQL ETL flags**

In `etl/config.py`, add a clearer flag while preserving compatibility:

```python
enable_market_duckdb_load: bool = True
enable_mysql_cache_load: bool = True
```

Keep `enable_mysql_load` temporarily as a backward-compatible alias if needed by existing CLI/admin request bodies.

- [ ] **Step 5: Update `etl/load_to_mysql.py`**

Remove `load_daily_price()` and `load_eod_rows()` from `load_all()` results, or leave wrappers that call DuckDB with deprecation comments. The safer phase-1 behavior:

```python
def load_all(cfg: EtlConfig, dataset: pd.DataFrame | None = None) -> dict[str, int]:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        dataset = pd.read_parquet(latest_file) if latest_file else None
    results = {
        "overview": load_overview_cache(cfg),
        "financial": load_financial_cache(cfg),
        "news": load_news_cache(cfg),
        "events": load_events_cache(cfg),
        "technical": load_technical_cache(cfg, dataset),
    }
    log.info("MySQL cache load_all results: %s", results)
    return results
```

- [ ] **Step 6: Update `etl/run_etl.py` imports**

Change:

```python
from etl.load_to_mysql import load_all, load_eod_rows
```

To:

```python
from etl.load_to_duckdb import load_daily_price_to_duckdb, load_eod_rows_to_duckdb
from etl.load_to_mysql import load_all as load_mysql_caches
```

- [ ] **Step 7: Update `etl/run_etl.py` load phase**

Replace the MySQL-only block with:

```python
if cfg.enable_market_duckdb_load:
    load_daily_price_to_duckdb(cfg, dataset)
    metadata.artifacts["duckdb_market_load"] = "enabled"
else:
    metadata.artifacts["duckdb_market_load"] = "disabled"

if cfg.enable_mysql_cache_load:
    load_mysql_caches(cfg, dataset)
    metadata.artifacts["mysql_cache_load"] = "enabled"
else:
    metadata.artifacts["mysql_cache_load"] = "disabled"

if cfg.enable_tick_eod:
    eod_rows = aggregate_all_ticks_to_eod(cfg.symbols, cfg, source=cfg.tick_source)
    load_eod_rows_to_duckdb(eod_rows)
    metadata.row_counts["tick_eod_rows"] = int(len(eod_rows))
```

- [ ] **Step 8: Preserve CLI compatibility**

Keep `--disable-mysql-load` for one release, but make it disable MySQL cache load only. Add a new CLI flag:

```python
parser.add_argument(
    "--disable-duckdb-market-load",
    action="store_true",
    default=False,
    help="Skip loading daily OHLCV into DuckDB market warehouse",
)
```

- [ ] **Step 9: Run loader tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_load_to_duckdb.py backend_v2\tests\test_market_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```powershell
git add etl\load_to_duckdb.py etl\load_to_mysql.py etl\run_etl.py etl\config.py etl\scheduler.py tests\test_load_to_duckdb.py
git commit -m "feat: load market ohlcv into duckdb"
```

### Task 5: Provide One-Time MySQL To DuckDB Migration Script

**Files:**
- Create: `etl/migrate_mysql_daily_ohlcv_to_duckdb.py`
- Test: manual dry-run command

- [ ] **Step 1: Create migration script**

Create `etl/migrate_mysql_daily_ohlcv_to_duckdb.py`:

```python
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import create_engine, text

from backend_v2.src.database.market_duckdb import market_repo
from backend_v2.src.settings import get_settings


def migrate(dry_run: bool = True) -> int:
    settings = get_settings()
    engine = create_engine(settings.mysql_url)
    grouped: dict[str, list[dict]] = defaultdict(list)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT symbol, date, open, high, low, close, volume
                FROM daily_ohlcv
                ORDER BY symbol, date
                """
            )
        ).mappings().all()

    for row in rows:
        grouped[str(row["symbol"]).upper()].append(dict(row))

    if dry_run:
        print(f"DRY RUN: would migrate {len(rows)} rows across {len(grouped)} symbols")
        return len(rows)

    total = 0
    for symbol, symbol_rows in grouped.items():
        total += market_repo.upsert_daily_rows(symbol, symbol_rows)
    print(f"Migrated {total} rows across {len(grouped)} symbols")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate MySQL daily_ohlcv rows into DuckDB.")
    parser.add_argument("--execute", action="store_true", help="Write rows into DuckDB. Without this flag, dry-run only.")
    args = parser.parse_args()
    migrate(dry_run=not args.execute)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Dry-run migration before any write**

Run:

```powershell
.\.venv\Scripts\python.exe -m etl.migrate_mysql_daily_ohlcv_to_duckdb
```

Expected: prints row count and symbol count only.

- [ ] **Step 3: Execute only after backup approval**

After user confirms MySQL backup exists, run:

```powershell
.\.venv\Scripts\python.exe -m etl.migrate_mysql_daily_ohlcv_to_duckdb --execute
```

Expected: migrated row count equals dry-run row count.

- [ ] **Step 4: Verify sample parity**

Run:

```powershell
.\.venv\Scripts\python.exe -c "from backend_v2.src.database.market_duckdb import market_repo; print(market_repo.load_history('VHM', limit=3))"
```

Expected: prints latest VHM rows from DuckDB.

- [ ] **Step 5: Commit**

```powershell
git add etl\migrate_mysql_daily_ohlcv_to_duckdb.py
git commit -m "feat: add mysql ohlcv to duckdb migration"
```

### Task 6: Remove Daily OHLCV From MySQL Schema After Cutover

Status: deferred to phase 2. Do not execute in phase 1.

**Files:**
- Modify: `backend_v2/src/database/models.py`
- Create: `backend_v2/alembic/versions/20260516_0002_drop_daily_ohlcv.py`
- Modify: `backend_v2/init_database.sql`
- Modify: `README.md`

- [ ] **Step 1: Confirm cutover criteria**

Before dropping MySQL data, verify:

```powershell
.\.venv\Scripts\python.exe -m etl.migrate_mysql_daily_ohlcv_to_duckdb
.\.venv\Scripts\python.exe -c "from backend_v2.src.database.market_duckdb import market_repo; print(len(market_repo.load_history('VHM', limit=5000)))"
```

Expected: DuckDB contains migrated rows and API history works.

- [ ] **Step 2: Remove ORM model**

Delete `DailyOHLCV` class from `backend_v2/src/database/models.py` only after all imports are removed.

- [ ] **Step 3: Create Alembic migration**

Create `backend_v2/alembic/versions/20260516_0002_drop_daily_ohlcv.py`:

```python
"""drop daily ohlcv from mysql

Revision ID: 20260516_0002
Revises: 20260429_0001
Create Date: 2026-05-16
"""

from alembic import op

revision = "20260516_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("daily_ohlcv")


def downgrade() -> None:
    op.create_table(
        "daily_ohlcv",
        op.inline_literal(""),
    )
    raise RuntimeError("Downgrade requires restoring daily_ohlcv from backup or DuckDB export.")
```

Important: the downgrade above must be replaced with a valid SQLAlchemy table definition before implementation. Do not leave `op.inline_literal("")` in committed migration.

- [ ] **Step 4: Use a valid downgrade table definition**

Replace downgrade with:

```python
import sqlalchemy as sa


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
```

- [ ] **Step 5: Remove table from init SQL**

Delete the `CREATE TABLE IF NOT EXISTS daily_ohlcv` block from `backend_v2/init_database.sql`.

- [ ] **Step 6: Compile and migration dry check**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall backend_v2\src etl
```

Expected: no references to deleted `DailyOHLCV`.

- [ ] **Step 7: Commit**

```powershell
git add backend_v2\src\database\models.py backend_v2\alembic\versions\20260516_0002_drop_daily_ohlcv.py backend_v2\init_database.sql README.md
git commit -m "refactor: remove mysql daily ohlcv table"
```

### Task 7: End-To-End Verification

**Files:**
- No new files expected.

- [ ] **Step 1: Compile backend and ETL**

Run:

```powershell
.\.venv\Scripts\python.exe -m compileall etl backend_v2\src
```

Expected: compile succeeds.

- [ ] **Step 2: Run DuckDB tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_market_duckdb.py tests\test_load_to_duckdb.py -q
```

Expected: PASS.

- [ ] **Step 3: Smoke import app**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.main import app; print(app.title)"
```

Expected: prints `VNStock Intraday API V2`.

- [ ] **Step 4: Smoke stock history from DuckDB**

Run:

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'backend_v2'); from src.services.vnstock_fetcher import fetcher_service; print(fetcher_service.load_history_from_db('VHM', limit=2))"
```

Expected: prints DuckDB-backed rows after migration or an empty list if migration has not been executed.

- [ ] **Step 5: Full ETL smoke with tiny symbol set**

Run only when external source credentials/network are ready:

```powershell
.\.venv\Scripts\python.exe -m etl.run_etl --symbols VHM --run-mode incremental --max-workers 1
```

Expected: parquet/gold snapshots update, DuckDB market load artifact is enabled, MySQL cache artifact remains enabled.

- [ ] **Step 6: Commit final docs/test adjustments**

```powershell
git add README.md docs\superpowers\plans\2026-05-16-mysql-stock-data-to-duckdb.md
git commit -m "docs: describe duckdb market data cutover"
```

---

## Approval Questions

1. Should Phase 1 move only `daily_ohlcv`, or do you also want `technical_cache` moved to DuckDB now?
2. Should DuckDB live at `lake/warehouse/market.duckdb`, or do you prefer another path?
3. Should the migration drop `daily_ohlcv` from MySQL immediately after parity checks, or keep it read-only for a rollback window?
4. Should ETL still maintain MySQL JSON cache tables in this phase?

## Risks And Controls

- Data loss risk: do not drop `daily_ohlcv` until migration dry-run, DuckDB row parity, and a MySQL backup are confirmed.
- Runtime lock risk: DuckDB is file-based. Backend and ETL concurrent writes should be serialized by operational scheduling in phase 1.
- Scope risk: moving every cache table at once will touch many async SQLAlchemy helpers. Keep cache migration as phase 2 unless explicitly approved.
- Dependency risk: installing `duckdb` may require package download. If the environment lacks it, request approval before installing dependencies.

## Self-Review

- Spec coverage: plan reads project, identifies current MySQL stock storage, proposes DuckDB migration, and delays execution until approval.
- Placeholder scan: implementation tasks include exact files, commands, and code. Task 6 intentionally calls out an invalid migration snippet and immediately replaces it with the valid version in the next step.
- Type consistency: repository methods use `upsert_daily_rows()` and `load_history()` consistently across backend, ETL, and tests.
