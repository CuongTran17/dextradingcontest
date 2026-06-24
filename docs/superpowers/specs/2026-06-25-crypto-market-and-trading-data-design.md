# Crypto Market And Trading Data Design

## 1. Goal

Build the persistent data foundation for a multi-user Spot crypto trading contest. The system must:

- Give every participant an isolated virtual account per contest.
- Persist balances, positions, orders, fills, and rankings in MySQL.
- Serve one year of Binance Spot candle history for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.
- Update current prices, candles, and order books from Binance WebSocket streams.
- Support chart intervals `1m`, `5m`, `15m`, `1h`, and `4h`.
- Remain extensible to more Spot symbols and Binance Futures without changing the core contest model.

Real deposits, withdrawals, exchange order execution, and real-money rewards remain outside the system.

## 2. Selected Architecture

Use three storage roles with explicit ownership:

1. **MySQL is the transactional source of truth.** It owns users, contests, participants, virtual accounts, balances, positions, orders, fills, equity snapshots, and leaderboard snapshots.
2. **DuckDB is the analytical market warehouse.** A dedicated `crypto_market.duckdb` owns historical closed candles and ingestion metadata.
3. **A realtime cache owns ephemeral state.** The first implementation may use process memory behind an interface. Redis can replace it when the backend runs multiple instances.

Binance REST is used for historical backfill and gap repair. Binance public WebSocket streams provide current kline, ticker, and order book updates. The frontend communicates only with the application backend.

## 3. Supported Market Scope

Initial market:

- Exchange: Binance
- Product: Spot
- Quote asset: USDT
- Symbols: BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT
- Historical retention: rolling 365 days
- Chart intervals: `1m`, `5m`, `15m`, `1h`, `4h`
- Canonical timestamp: UTC milliseconds at ingestion boundaries; UTC timestamps in storage

The symbol list must be configuration-driven. Adding a Spot symbol must not require a database migration.

## 4. MySQL Transactional Model

All monetary columns use `DECIMAL`, never floating-point types. IDs may use unsigned `BIGINT`; public API identifiers use UUID strings where exposing sequential database IDs is undesirable.

### `crypto_assets`

Reference data for supported instruments:

- `id`
- `exchange`
- `market_type` (`spot`, reserved for `futures`)
- `symbol`
- `base_asset`
- `quote_asset`
- `price_precision`
- `quantity_precision`
- `min_quantity`
- `min_notional`
- `is_active`
- `created_at`, `updated_at`

Unique key: `(exchange, market_type, symbol)`.

### `contests`

- `id`, `slug`, `title`
- `mode` (`practice`, `contest`)
- `status` (`draft`, `scheduled`, `active`, `settling`, `completed`, `cancelled`)
- `initial_balance`
- `quote_asset` (initially `USDT_TEST`)
- `starts_at`, `ends_at`
- `fee_rate`
- `slippage_model`
- `rules_json`
- `created_by`, `created_at`, `updated_at`

### `contest_assets`

Joins contests to tradeable assets:

- `contest_id`
- `asset_id`
- `is_enabled`

Unique key: `(contest_id, asset_id)`.

### `contest_participants`

- `id`
- `contest_id`
- `user_id`
- `status` (`active`, `disqualified`, `withdrawn`, `completed`)
- `joined_at`
- `final_rank`
- `final_equity`
- `final_roi`

Unique key: `(contest_id, user_id)`.

### `trading_accounts`

One account per contest participant:

- `id`
- `contest_participant_id`
- `status` (`active`, `frozen`, `closed`)
- `initial_equity`
- `current_equity`
- `realized_pnl`
- `unrealized_pnl`
- `version`
- `created_at`, `updated_at`

Unique key: `contest_participant_id`. The `version` supports optimistic concurrency where row locking is not used.

### `account_balances`

- `id`
- `account_id`
- `asset`
- `available`
- `locked`
- `updated_at`

Unique key: `(account_id, asset)`.

### `positions`

Spot positions are long-only in the first release:

- `id`
- `account_id`
- `asset_id`
- `quantity`
- `average_entry_price`
- `cost_basis`
- `realized_pnl`
- `updated_at`

Unique key: `(account_id, asset_id)`.

### `orders`

- `id`, `client_order_id`
- `account_id`, `asset_id`
- `side` (`buy`, `sell`)
- `order_type` (`market` initially; `limit` reserved)
- `status` (`pending`, `filled`, `partially_filled`, `rejected`, `cancelled`)
- `requested_quantity`
- `filled_quantity`
- `average_fill_price`
- `estimated_notional`
- `executed_notional`
- `fee_amount`
- `fee_asset`
- `rejection_reason`
- `market_price_at_submission`
- `submitted_at`, `completed_at`

Unique key: `(account_id, client_order_id)` for idempotency.

### `trade_fills`

Immutable execution records:

- `id`
- `order_id`
- `fill_sequence`
- `price`
- `quantity`
- `notional`
- `fee_amount`
- `fee_asset`
- `liquidity_source` (`simulated_orderbook`)
- `executed_at`

Unique key: `(order_id, fill_sequence)`.

### `portfolio_snapshots`

Periodic account history for charts and audit:

- `id`
- `account_id`
- `captured_at`
- `cash_value`
- `positions_value`
- `equity`
- `realized_pnl`
- `unrealized_pnl`
- `roi`

Index: `(account_id, captured_at)`.

### `leaderboard_snapshots`

- `id`
- `contest_id`
- `participant_id`
- `captured_at`
- `rank`
- `equity`
- `roi`
- `trade_count`

Indexes: `(contest_id, captured_at, rank)` and `(participant_id, captured_at)`.

### `trading_audit_logs`

Append-only operational records:

- `id`
- `account_id`
- `event_type`
- `entity_type`, `entity_id`
- `payload_json`
- `created_at`

## 5. DuckDB Market Model

Use a separate file:

```text
lake/warehouse/crypto_market.duckdb
```

### `crypto_candles`

- `exchange`
- `market_type`
- `symbol`
- `interval`
- `open_time`
- `close_time`
- `open`, `high`, `low`, `close`
- `volume`
- `quote_volume`
- `trade_count`
- `taker_buy_base_volume`
- `taker_buy_quote_volume`
- `is_closed`
- `source`
- `ingested_at`

Primary uniqueness: `(exchange, market_type, symbol, interval, open_time)`.

Closed `1m` candles are the canonical history. Materialized `5m`, `15m`, `1h`, and `4h` rows are derived from `1m` data and stored in the same table with their interval value. Keeping derived intervals avoids repeated aggregation on every chart request and makes API latency predictable.

Only closed interval buckets are authoritative DuckDB history. The currently open `1m`, `5m`, `15m`, `1h`, and `4h` candles remain in the realtime cache and are overlaid on DuckDB results by the candle API.

### `crypto_ingestion_state`

- `exchange`
- `market_type`
- `symbol`
- `interval`
- `last_closed_open_time`
- `last_checked_at`
- `status`
- `last_error`

Unique key: `(exchange, market_type, symbol, interval)`.

### Retention

A scheduled maintenance job removes candles whose `open_time` is older than 365 days. Derived intervals follow the same cutoff. The backfill and repair jobs are idempotent upserts.

## 6. Historical Backfill

For each configured symbol:

1. Request Binance `1m` klines in pages of at most 1,000 rows.
2. Move from the start timestamp toward the current closed minute.
3. Normalize numeric values and timestamps.
4. Upsert each page into `crypto_candles`.
5. Update `crypto_ingestion_state` after a successful page.
6. Resume from the last recorded closed candle after interruption.
7. Aggregate and upsert `5m`, `15m`, `1h`, and `4h` candles.
8. Run a gap detector and request missing ranges from Binance REST.

Backfill runs as an explicit CLI/job, not inside a web request and not automatically during API startup.

## 7. Realtime Data Flow

The market stream service subscribes to combined Binance public streams:

- `<symbol>@kline_1m` for the current candle
- `<symbol>@bookTicker` for best bid and ask
- `<symbol>@depth@100ms` or a suitable depth stream for the visible order book

Realtime cache entries include the latest tradeable price, current open candle, best bid/ask, order book snapshot, exchange event time, and local receive time.

When a `1m` kline closes:

1. Upsert it into DuckDB.
2. Update derived interval state in cache and persist a derived candle when its complete bucket closes.
3. Publish an internal candle-close event.
4. Recalculate active account equity and leaderboard data asynchronously.

The service reconnects with exponential backoff, proactively renews connections before Binance's 24-hour connection lifetime, and performs REST gap repair after reconnecting.

## 8. Order Book Correctness

The first implementation may continue serving REST depth snapshots. The realtime implementation must follow Binance depth synchronization rules:

1. Buffer WebSocket depth events.
2. Fetch a REST depth snapshot.
3. Discard buffered events older than the snapshot update ID.
4. Apply remaining events in sequence.
5. Rebuild from a new snapshot if sequence continuity is lost.

Only the current reconstructed book belongs in memory or Redis. Full depth-event history is not retained in DuckDB during this phase.

## 9. Simulated Order Execution

Market orders execute against the cached order book:

1. Authenticate the user and load their contest account.
2. Validate contest status, allowed symbol, quantity, balance, and position.
3. Lock the account and affected balance/position rows in one MySQL transaction.
4. Walk asks for buys or bids for sells until the requested quantity is filled.
5. Reject when available depth is insufficient; partial fills are deferred until explicitly enabled.
6. Calculate fill-weighted price, notional, configured fee, and slippage.
7. Insert the order and immutable fill rows.
8. Update balances, positions, PnL, and account equity.
9. Commit the transaction and publish an account-update event.

If the order book is stale beyond a configured threshold, order placement fails safely instead of using mock data.

## 10. API Boundaries

Market endpoints:

- `GET /api/crypto/assets`
- `GET /api/crypto/prices/latest`
- `GET /api/crypto/candles`
- `GET /api/crypto/orderbook`
- `WS /api/ws/crypto/market`

Trading endpoints:

- `GET /api/crypto/contests`
- `POST /api/crypto/contests/{contest_id}/join`
- `GET /api/crypto/accounts/{contest_id}`
- `POST /api/crypto/orders/market`
- `GET /api/crypto/orders`
- `GET /api/crypto/positions`
- `GET /api/crypto/contests/{contest_id}/leaderboard`
- `WS /api/ws/crypto/account`

Frontend `localStorage` is retained only for non-authoritative preferences such as selected symbol or timeframe.

## 11. Failure Handling And Observability

- Binance REST fallback endpoints remain available for public market requests.
- Backfill retries rate-limit and transient network failures with bounded exponential backoff.
- WebSocket state exposes connected, reconnecting, stale, and offline statuses.
- Market API responses include source and freshness timestamps.
- DuckDB write failures do not corrupt MySQL trading state.
- Trading is disabled when market data freshness exceeds the configured maximum.
- Metrics cover stream age, reconnect count, backfill progress, candle gaps, order latency, rejection reasons, and leaderboard update lag.

## 12. Testing Strategy

- Unit tests for candle normalization, interval aggregation, depth synchronization, fill calculation, fees, PnL, and retention cutoffs.
- Repository tests using temporary DuckDB files.
- MySQL integration tests for migrations, constraints, idempotent orders, and concurrent balance updates.
- Contract tests for Binance REST and WebSocket payload adapters using recorded fixtures.
- API tests for contest joining, account isolation, order validation, order history, and leaderboard calculation.
- End-to-end tests proving that a user joins a contest, receives virtual capital, trades, reloads the page, and sees persisted state.
- Recovery tests for interrupted backfill, WebSocket reconnect, missing candle repair, and stale order book rejection.

## 13. Delivery Phases

### Phase 1: Transactional Foundation

Create MySQL migrations and repositories for assets, contests, participants, accounts, balances, positions, orders, fills, and snapshots. Move virtual portfolio ownership out of frontend `localStorage`.

### Phase 2: Historical Market Warehouse

Create `crypto_market.duckdb`, backfill one year of `1m` candles for the five symbols, materialize the supported higher intervals, and expose DuckDB-backed candle APIs.

### Phase 3: Realtime Market Service

Add Binance WebSocket ingestion, cache abstraction, current candle updates, synchronized order books, reconnect handling, and backend-to-frontend WebSocket delivery.

### Phase 4: Trading And Contest Engine

Execute simulated market orders against the order book, persist account state transactionally, calculate equity/PnL, and produce real leaderboard data.

### Phase 5: Production Hardening

Replace process memory with Redis when deploying multiple backend instances, add operational dashboards, load tests, backup procedures, and data reconciliation jobs.

## 14. Acceptance Criteria

- Five configured Spot symbols return up to 365 days of chart data for every supported interval.
- A stopped backfill resumes without duplicates or lost ranges.
- Closed realtime candles appear in DuckDB and chart APIs.
- Current candle and order book updates reach the frontend without page polling.
- Each contest participant has an isolated persistent account.
- Orders survive browser reloads and backend restarts.
- Concurrent orders cannot produce negative balances or positions.
- Leaderboard values are derived from persisted accounts and live market prices.
- Stale or unavailable market data prevents simulated execution.
