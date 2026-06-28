# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

The production application is crypto-only. Earlier stock, DNSE, ETL, AI, payment, and premium
features have been removed from the runtime. Their frontend code is retained under
`legacy/frontend/` for reference and is excluded from production builds.

## Implemented Features

- Vue 3, TypeScript, Vite, Tailwind CSS frontend.
- FastAPI backend with authenticated virtual trading APIs.
- Binance Spot prices, candles, and order-book snapshots.
- BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.
- MySQL-backed contest participants, accounts, balances, positions, orders, and fills.
- MySQL-backed public contest list/detail pages and live-equity leaderboards.
- Admin contest creation and status management without editing user results.
- Admin participant moderation for active, locked, and disqualified contest accounts.
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

The existing MySQL database may still contain tables created by the earlier project. Those
tables are not queried by the crypto runtime and were intentionally left untouched to avoid
destructive schema changes.

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
Market repair is enabled by default with `CRYPTO_REPAIR_ON_STARTUP=true`; it checks the
existing DuckDB warehouse on backend startup and pulls only missing Binance `1m` ranges.

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

The backend also runs an incremental repair task in the background when it starts.
If the app was offline for a few hours, the task fetches only those missing `1m`
candles, then rebuilds `5m`, `15m`, `1h`, `4h`, and indicators. It does not reload
the full year unless the warehouse is empty.

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

Contest and trading endpoints:

```text
GET  /api/crypto/contests
GET  /api/crypto/contests/{contest_id}
GET  /api/crypto/contests/{contest_id}/leaderboard
POST /api/crypto/contests/{contest_id}/join
GET  /api/crypto/accounts/{contest_id}
POST /api/crypto/orders/market
```

Admin contest endpoints:

```text
GET  /api/admin/users?page=1&per_page=20&role=user&q=email&is_locked=false
PUT  /api/admin/users/{user_id}/role?role=admin
PUT  /api/admin/users/{user_id}/lock?reason=...
PUT  /api/admin/users/{user_id}/unlock
GET  /api/admin/crypto/overview
GET  /api/admin/crypto/accounts?contest_id=practice-arena&page=1&per_page=20
GET  /api/admin/crypto/accounts/{account_id}
GET  /api/admin/crypto/contests
POST /api/admin/crypto/contests
PUT  /api/admin/crypto/contests/{contest_id}
PUT  /api/admin/crypto/contests/{contest_id}/status
GET  /api/admin/crypto/contests/{contest_id}/participants
PUT  /api/admin/crypto/contests/{contest_id}/participants/{user_id}/status?status=locked
```

### Crypto Contest Data

- MySQL stores users, contests, participants, virtual balances, positions, orders, and fills.
- DuckDB stores Binance market candles and precomputed indicators.
- Public contest APIs live under `/api/crypto/contests`.
- Admin contest APIs live under `/api/admin/crypto/contests` and require an admin JWT.
- Admin dashboard APIs live under `/api/admin/crypto/overview` and `/api/admin/crypto/accounts`.
- Admins can create contests and change contest status, but cannot edit user trading results.
- Admins can observe account balances, positions, orders, fills, equity, PnL, and ROI.
- Admins must not edit account balances, positions, orders, fills, PnL, or leaderboard results directly.
- Admins can list contest participants and set participant status to active, locked, or disqualified.
- Locked or disqualified participants have their trading account frozen for that contest.

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
3. Admin participant moderation for locking or disqualifying broken accounts.
4. Binance Futures market data after the Spot workflow is stable.

## Safety

This app must not include real deposits, withdrawals, mainnet swaps, exchange order execution,
automated trading signals, guaranteed returns, payment or premium flows, or real-money payouts.
