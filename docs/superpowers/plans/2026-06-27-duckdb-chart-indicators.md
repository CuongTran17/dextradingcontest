# DuckDB Chart Indicators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a TradingView-like indicator picker and show MACD below the crypto chart using values precomputed and stored in DuckDB.

**Architecture:** DuckDB stores indicator series in a generic `crypto_indicators` table keyed by symbol, interval, indicator, params, and candle open time. Backend exposes an indicator API that reads the DuckDB cache and materializes missing MACD values from stored candles. Frontend opens a searchable picker, selects MACD, and renders a compact indicator panel under the chart from backend data.

**Tech Stack:** DuckDB, pandas, FastAPI, Vue 3, Vitest, pytest.

---

## Tasks

### Task 1: DuckDB MACD Cache

**Files:**
- Modify: `backend_v2/src/database/crypto_market_duckdb.py`
- Modify: `backend_v2/tests/test_crypto_market_duckdb.py`

- [ ] Write failing tests that MACD is materialized from stored candles, stored in DuckDB, and loaded chronologically.
- [ ] Implement `crypto_indicators` schema.
- [ ] Implement `materialize_macd()` and `load_indicator()`.
- [ ] Verify with `.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_crypto_market_duckdb.py -q`.

### Task 2: Indicator API

**Files:**
- Modify: `backend_v2/src/routes/crypto.py`
- Modify: `backend_v2/tests/test_crypto_routes.py`

- [ ] Write failing route tests for `GET /api/crypto/indicators`.
- [ ] Implement MACD route that reads DuckDB cache and materializes missing values.
- [ ] Verify route tests.

### Task 3: Frontend Indicator Picker

**Files:**
- Modify: `src/types/crypto.ts`
- Modify: `src/services/cryptoMarketData.ts`
- Modify: `src/components/crypto/CryptoChart.vue`
- Create: `src/components/crypto/__tests__/CryptoChart.test.ts`

- [ ] Write failing tests for searchable indicator picker and MACD panel.
- [ ] Add indicator API service/types.
- [ ] Add compact picker in chart header.
- [ ] Show MACD panel below candle chart after selection.

### Task 4: Verification

- [ ] Run backend retained tests.
- [ ] Run frontend unit tests.
- [ ] Run frontend build.
- [ ] Run `git diff --check`.
- [ ] Smoke test `/trade/BTCUSDT` in browser.
- [ ] Commit.
