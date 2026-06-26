# Binance Spot WebSocket Realtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Binance Spot realtime prices, 1m candles, and 100-level order books for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.

**Architecture:** The backend owns one public Binance combined WebSocket stream and keeps an in-memory realtime cache. Frontend tabs connect to one backend WebSocket, receive all-symbol prices, and subscribe to one detailed trading symbol for candles and orderbook.

**Tech Stack:** FastAPI, Starlette WebSocket, asyncio, httpx/Binance REST fallback, DuckDB, Vue 3, Vitest, pytest.

---

## Files

- Create: `backend_v2/src/services/crypto_realtime_cache.py`
- Create: `backend_v2/src/services/binance_realtime.py`
- Create: `backend_v2/tests/test_binance_realtime.py`
- Create: `src/services/cryptoRealtime.ts`
- Create: `src/services/__tests__/cryptoRealtime.test.ts`
- Modify: `backend_v2/src/routes/crypto.py`
- Modify: `backend_v2/src/routes/health.py`
- Modify: `backend_v2/src/jobs.py`
- Modify: `src/components/crypto/CryptoChart.vue`
- Modify: `src/components/crypto/OrderBook.vue`
- Modify: `src/views/CryptoTrade.vue`
- Modify: `src/types/crypto.ts`

## Task 1: Backend Event Normalization And Cache

**Files:**
- Create: `backend_v2/src/services/crypto_realtime_cache.py`
- Create: `backend_v2/src/services/binance_realtime.py`
- Test: `backend_v2/tests/test_binance_realtime.py`

- [ ] Write failing pytest tests for combined stream URL, ticker parsing, kline parsing, cache snapshots, and 100-level orderbook trimming.
- [ ] Run `.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_binance_realtime.py -q` and verify failures are due to missing modules.
- [ ] Implement dataclasses and pure functions:
  - `build_combined_stream_url(symbols)`
  - `normalize_ticker_event(payload)`
  - `normalize_kline_event(payload)`
  - `RealtimeMarketCache`
  - `LocalOrderBook`
- [ ] Re-run the new pytest file and verify it passes.

## Task 2: Orderbook Snapshot Synchronization

**Files:**
- Modify: `backend_v2/src/services/binance_realtime.py`
- Test: `backend_v2/tests/test_binance_realtime.py`

- [ ] Add failing tests for Binance diff-depth bridge rules, zero-quantity deletion, sequential updates, and sequence-gap resync.
- [ ] Run the orderbook tests and verify they fail for missing sync behavior.
- [ ] Implement `OrderBookSynchronizer` with buffered events, REST snapshot loading callback, and gap detection.
- [ ] Re-run the orderbook tests and verify they pass.

## Task 3: Candle Persistence Worker

**Files:**
- Modify: `backend_v2/src/services/binance_realtime.py`
- Test: `backend_v2/tests/test_binance_realtime.py`

- [ ] Add failing async tests that closed `kline_1m` events are queued, persisted idempotently, update ingestion state, and materialize derived intervals.
- [ ] Run the new async tests and verify they fail for missing persistence worker.
- [ ] Implement a bounded `asyncio.Queue` and `CandlePersistenceWorker` that writes only closed candles.
- [ ] Re-run the persistence tests and verify they pass.

## Task 4: Backend WebSocket Endpoint And REST Preference

**Files:**
- Modify: `backend_v2/src/routes/crypto.py`
- Modify: `backend_v2/src/routes/health.py`
- Modify: `backend_v2/src/jobs.py`
- Test: `backend_v2/tests/test_binance_realtime.py`
- Test: `backend_v2/tests/test_crypto_app_surface.py`

- [ ] Add failing tests that `/api/crypto/prices/latest` prefers realtime cache, `/api/crypto/orderbook` prefers synced cache, and malformed WebSocket subscribe messages return an error event.
- [ ] Run the backend tests and verify they fail for missing route integration.
- [ ] Register a singleton realtime service in app lifespan, start it on startup, stop it on shutdown, and expose it on `app.state.crypto_realtime`.
- [ ] Add `/api/crypto/ws` to accept frontend clients, send an initial snapshot, accept `{ "type": "subscribe", "symbol": "ETHUSDT" }`, and stream cache updates.
- [ ] Update health output with realtime status.
- [ ] Re-run backend tests and verify they pass.

## Task 5: Frontend Shared WebSocket Client

**Files:**
- Create: `src/services/cryptoRealtime.ts`
- Create: `src/services/__tests__/cryptoRealtime.test.ts`
- Modify: `src/types/crypto.ts`

- [ ] Add failing Vitest tests that the service opens one WebSocket, stores all-symbol price updates, sends subscribe messages, routes candle events, routes orderbook events, and reconnects after close.
- [ ] Run `npm.cmd run test:unit -- src/services/__tests__/cryptoRealtime.test.ts` and verify failures are due to missing service.
- [ ] Implement `cryptoRealtime` as a small module-level shared client with `connect`, `subscribeSymbol`, `onSnapshot`, `onCandle`, `onOrderBook`, and `getState`.
- [ ] Re-run the new Vitest file and verify it passes.

## Task 6: Frontend Trade Screen Integration

**Files:**
- Modify: `src/views/CryptoTrade.vue`
- Modify: `src/components/crypto/CryptoChart.vue`
- Modify: `src/components/crypto/OrderBook.vue`
- Test: existing Vue/Vitest tests plus new realtime tests.

- [ ] Add failing tests or adapt existing tests to show the trade page uses realtime prices without the 5-second price timer and orderbook without the 3-second polling timer.
- [ ] Run the affected frontend tests and verify they fail for old polling behavior.
- [ ] Wire `CryptoTrade.vue` to the shared realtime client and subscribe on route symbol changes.
- [ ] Update `CryptoChart.vue` to load REST history once, then apply realtime `1m` candle updates only when the selected timeframe is `1m`.
- [ ] Update `OrderBook.vue` to accept a realtime book prop and call REST only while no realtime book is available.
- [ ] Re-run frontend tests and verify they pass.

## Task 7: Verification And Commit

**Files:**
- All files changed above.

- [ ] Run backend targeted tests:
  `.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_binance_realtime.py backend_v2/tests/test_crypto_app_surface.py -q`
- [ ] Run retained backend tests:
  `$tests = git ls-files 'backend_v2/tests/*.py' | Where-Object { (Test-Path $_) -and ($_ -notmatch '__init__') }; $tests += @('backend_v2/tests/test_crypto_app_surface.py','backend_v2/tests/test_admin_users.py'); .\.venv\Scripts\python.exe -m pytest $tests -q`
- [ ] Run frontend tests:
  `npm.cmd run test:unit`
- [ ] Run frontend build:
  `npm.cmd run build`
- [ ] Run `git diff --check`.
- [ ] Review diff for accidental legacy changes.
- [ ] Commit with message `feat: add binance realtime market stream`.

## Self-Review

- Spec coverage: backend Binance combined stream, cache, orderbook sync, closed-candle persistence, REST preference, health, one frontend WebSocket, and frontend routing are covered.
- Placeholder scan: no task depends on unspecified future work.
- Type consistency: backend event names match the spec (`snapshot`, `prices`, `candle`, `orderbook`, `status`, `error`); frontend types will accept `binance-websocket` as a market data source.
