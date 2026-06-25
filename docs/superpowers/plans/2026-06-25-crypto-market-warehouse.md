# Crypto Market Warehouse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store and serve a rolling year of Binance Spot candles for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT from a dedicated DuckDB warehouse.

**Architecture:** Closed `1m` candles are the canonical dataset in `crypto_market.duckdb`. A resumable REST backfill writes paginated `1m` rows, then DuckDB SQL materializes `5m`, `15m`, `1h`, and `4h` buckets; the candle API reads DuckDB first and falls back to Binance only when the warehouse has no rows.

**Tech Stack:** Python, DuckDB, FastAPI, httpx, pytest, Binance Spot REST API.

---

### Task 1: Crypto Candle Repository

**Files:**
- Create: `backend_v2/src/database/crypto_market_duckdb.py`
- Modify: `backend_v2/src/settings.py`
- Test: `backend_v2/tests/test_crypto_market_duckdb.py`

- [ ] Write failing tests for schema creation, idempotent candle upsert, chronological reads, aggregation, ingestion state, and retention.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_market_duckdb.py -q` and confirm import failure.
- [ ] Implement `CryptoMarketDuckDB` with `crypto_candles` and `crypto_ingestion_state`.
- [ ] Add `crypto_duckdb_path`, defaulting to `lake/warehouse/crypto_market.duckdb`.
- [ ] Re-run tests and commit `feat: add crypto market warehouse`.

### Task 2: Resumable Binance Backfill

**Files:**
- Modify: `backend_v2/src/services/binance_market_data.py`
- Create: `backend_v2/src/services/crypto_market_backfill.py`
- Test: `backend_v2/tests/test_crypto_market_backfill.py`

- [ ] Write failing tests proving pagination advances by candle open time, closed candles only are stored, reruns resume from ingestion state, and five default symbols are supported.
- [ ] Add `get_klines_page(symbol, interval, limit, start_time, end_time)` returning complete Binance kline fields.
- [ ] Implement `CryptoMarketBackfillService.backfill_symbol()` and `backfill_all()`.
- [ ] Re-run tests and commit `feat: backfill binance spot candles`.

### Task 3: DuckDB-Backed Candle API

**Files:**
- Modify: `backend_v2/src/routes/crypto.py`
- Test: `backend_v2/tests/test_crypto_routes.py`

- [ ] Write a failing route test asserting DuckDB rows are returned without calling Binance.
- [ ] Add an injectable warehouse dependency and query `1m`, `5m`, `15m`, `1h`, `4h`.
- [ ] Keep Binance fallback when DuckDB returns no rows; keep mock fallback only when both sources fail.
- [ ] Re-run backend crypto tests and commit `feat: serve crypto candles from duckdb`.

### Task 4: Backfill CLI And Verification

**Files:**
- Create: `backend_v2/scripts/backfill_crypto_market.py`
- Modify: `package.json`
- Modify: `backend_v2/.env.example`
- Modify: `README.md`
- Test: `backend_v2/tests/test_crypto_market_cli.py`

- [ ] Write a failing parser test for `--symbols`, `--days`, and `--page-limit`.
- [ ] Implement CLI with progress output and a `crypto:backfill` npm script.
- [ ] Document `CRYPTO_DUCKDB_PATH` and the backfill command.
- [ ] Run targeted backend tests, full tracked backend tests, frontend tests, and production build.
- [ ] Run a limited live backfill smoke test, inspect row counts, and commit `docs: document crypto market backfill`.

## Acceptance Criteria

- Warehouse uses a separate `crypto_market.duckdb`.
- Upserts are idempotent by exchange, market type, symbol, interval, and open time.
- Backfill resumes after interruption and stores only closed candles.
- Five configured symbols can backfill up to 365 days.
- API serves chronological candles from DuckDB.
- Retention removes rows older than 365 days.
- Full tracked backend tests, frontend tests, and build pass.
