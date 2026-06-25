# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

## Implemented Features

- Vue 3, TypeScript, Vite, Tailwind CSS frontend.
- FastAPI backend with authenticated virtual trading APIs.
- Binance Spot prices, candles, and order-book snapshots.
- BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.
- MySQL-backed contest participants, accounts, balances, positions, orders, and fills.
- One isolated virtual account per user and contest.
- Idempotent market orders executed against Binance order-book depth.
- Dedicated DuckDB warehouse with a rolling year of `1m` Spot candles.
- Materialized `5m`, `15m`, `1h`, and `4h` candles generated from canonical `1m` data.
- Resumable Binance backfill with checkpointing, gap detection, and gap repair.

Portfolio and order state is authoritative in MySQL. Browser `localStorage` is not used for
balances, positions, or trading history.

## Architecture

| Component | Responsibility |
| --- | --- |
| Vue frontend | Charts, order book, simulated trading, portfolio, and contest views |
| FastAPI backend | Authentication, market APIs, order execution, and account APIs |
| MySQL | Users, contests, accounts, balances, positions, orders, and fills |
| DuckDB | Historical Binance Spot candles and ingestion checkpoints |
| Binance REST API | Latest prices, order-book depth, fallback candles, and historical backfill |

MySQL and DuckDB are intentionally separate. Transactional user and trading state belongs in
MySQL, while high-volume analytical market data belongs in DuckDB.

## Market Data

Supported symbols:

```text
BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, BNBUSDT
```

Stored timeframes:

```text
1m, 5m, 15m, 1h, 4h
```

The warehouse keeps approximately 365 days of rolling history. A completed initial backfill
contains about 525,599 `1m` candles per symbol and about 3.38 million rows in total after
including materialized timeframes. The DuckDB file is approximately 334 MB. These values vary
slightly as new candles are added and old candles pass the retention cutoff.

The current live price and order-book endpoints read Binance directly. Historical chart
requests use DuckDB first, then fall back to Binance when stored data is unavailable.

## Setup

### 1. Frontend dependencies

```powershell
npm install
```

### 2. Backend environment

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend_v2\requirements.txt pytest
Copy-Item backend_v2\.env.example backend_v2\.env
```

Set `MYSQL_URL`, `MYSQL_ASYNC_URL`, and a long random `JWT_SECRET` in
`backend_v2\.env`. Keep the default DuckDB path unless the warehouse should live elsewhere.

### 3. MySQL database

```sql
CREATE DATABASE crypto_dex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

Apply all Alembic migrations:

```powershell
Set-Location backend_v2
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
```

The migrations seed the `practice-arena` contest and the five supported Binance Spot assets.

### 4. Historical market data

Backfill one rolling year for all configured symbols:

```powershell
npm.cmd run crypto:backfill -- --days 365
```

Run a smaller smoke backfill:

```powershell
npm.cmd run crypto:backfill -- --symbols BTCUSDT --days 1 --page-limit 500
```

The command is safe to rerun. It resumes from `crypto_ingestion_state`, repairs missing
internal candle ranges, ignores still-open candles, rebuilds derived timeframes, and removes
data older than the rolling retention window.

### 5. Start the application

Run the backend:

```powershell
npm.cmd run backend:dev
```

Run the frontend in another terminal:

```powershell
npm.cmd run dev
```

Open `http://localhost:5174`. The backend runs at `http://localhost:8000`.

## API

Public market endpoints:

```text
GET /api/crypto/assets
GET /api/crypto/prices/latest
GET /api/crypto/candles?symbol=BTCUSDT&interval=1h
GET /api/crypto/orderbook?symbol=BTCUSDT
```

Authenticated trading endpoints:

```text
POST /api/crypto/contests/{contest_id}/join
GET  /api/crypto/accounts/{contest_id}
POST /api/crypto/orders/market
```

## Verification

```powershell
npm.cmd run test:unit
npm.cmd run type-check
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest backend_v2\tests -q
```

## Roadmap

1. Binance WebSocket ingestion for current `1m` candles and synchronized order books.
2. Persisted leaderboard snapshots and scheduled contest ranking updates.
3. Admin contest management for starting capital, start/end times, locking, and invalidation.
4. Binance Futures market data after the Spot workflow is stable.

## Safety

This app must not include real deposits, withdrawals, mainnet swaps, exchange order execution, automated trading signals, guaranteed returns, or real-money payout flows.
