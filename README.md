# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

## Current Phase

- Vue 3, TypeScript, Vite, Tailwind CSS frontend.
- FastAPI backend with authenticated virtual trading APIs.
- Binance Spot market prices, candles, and order-book snapshots.
- BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.
- MySQL-backed contest participants, accounts, balances, positions, orders, and fills.
- One isolated virtual account per user and contest.
- Idempotent market orders executed against Binance order-book depth.

Portfolio and order state is authoritative in MySQL. Browser `localStorage` is not used for
balances, positions, or trading history.

## Frontend

```powershell
npm install
npm.cmd run dev
```

Open `http://localhost:5174`.

Useful checks:

```powershell
npm.cmd run test:unit
npm.cmd run type-check
npm.cmd run build
```

## Backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend_v2\requirements.txt pytest
```

Create a MySQL database and configure the connection:

```sql
CREATE DATABASE crypto_dex CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

```powershell
Copy-Item backend_v2\.env.example backend_v2\.env
# Set MYSQL_URL, MYSQL_ASYNC_URL, and JWT_SECRET in backend_v2\.env.

Set-Location backend_v2
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..

npm.cmd run backend:dev
```

Run backend tests:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2\tests -q
```

Public market API:

```text
GET /api/crypto/assets
GET /api/crypto/prices/latest
GET /api/crypto/candles
GET /api/crypto/orderbook
```

Authenticated trading API:

```text
POST /api/crypto/contests/{contest_id}/join
GET  /api/crypto/accounts/{contest_id}
POST /api/crypto/orders/market
```

The `practice-arena` contest and five Binance Spot assets are seeded by Alembic migration
`20260625_0003`.

## Next Data Phases

- Phase 2 uses a dedicated `crypto_market.duckdb`, rolling `1m` candle history, and
  materialized `5m`, `15m`, `1h`, and `4h` intervals.
- Phase 3: Binance WebSocket ingestion for current candles and synchronized order books.
- Phase 4: persisted leaderboard snapshots and Admin contest management.

Backfill the five configured Spot symbols:

```powershell
npm.cmd run crypto:backfill -- --days 365
```

For a smaller smoke run:

```powershell
npm.cmd run crypto:backfill -- --symbols BTCUSDT --days 1 --page-limit 500
```

The command is resumable. Its checkpoint is stored in the
`crypto_ingestion_state` table inside `lake/warehouse/crypto_market.duckdb`.

## Safety

This app must not include real deposits, withdrawals, mainnet swaps, exchange order execution, automated trading signals, guaranteed returns, or real-money payout flows.
