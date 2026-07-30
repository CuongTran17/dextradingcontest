# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market and limit buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

The production application is crypto-only. Earlier stock, DNSE, ETL, AI, payment, and premium
features have been removed from the runtime. Their frontend code is retained under
`legacy/frontend/` for reference and is excluded from production builds.

## Implemented Features

- Vue 3, TypeScript, Vite, Tailwind CSS frontend.
- FastAPI backend with authenticated virtual trading APIs.
- Binance Spot prices, candles, order-book snapshots, and WebSocket realtime updates.
- BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and BNBUSDT.
- MySQL-backed contest participants, accounts, balances, positions, orders, and fills.
- MySQL-backed public contest list/detail pages and live-equity leaderboards.
- Public leaderboard REST snapshots and WebSocket broadcasts with polling fallback.
- Admin contest creation and status management without editing user results.
- Admin participant moderation for active, locked, and disqualified contest accounts.
- One isolated virtual account per user and contest.
- Idempotent market orders executed against Binance order-book depth.
- Limit orders that fill immediately when marketable or remain pending until cancelled or historically triggered.
- Optional take-profit and stop-loss controls reconciled from historical candles on backend startup and while the backend is running.
- Admin contest settlement with pending-order cancellation, mark-to-market final equity, final ranking, audit events, and snapshot hashes.
- Solana devnet contest join proof with wallet connect UI, on-chain `join_contest`, and backend wallet locking.
- Anchor contest program deployed on devnet at `9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx`.
- Solana admin CLI for initializing contests, toggling on-chain joins, and publishing certificate Merkle roots.
- Top-10 certificate export model with PNG certificate rendering, Pinata image/metadata upload, and deterministic Merkle proofs.
- Dedicated DuckDB warehouse with a rolling year of `1m` Spot candles.
- Materialized `5m`, `15m`, `1h`, and `4h` candles generated from canonical `1m` data.
- Precomputed MACD, RSI, EMA, and SMA indicator data for chart overlays.
- Resumable Binance backfill with checkpointing, gap detection, and gap repair.

Portfolio and order state is authoritative in MySQL. Browser `localStorage` is not used for
balances, positions, or trading history.

## Architecture

| Component | Responsibility |
| --- | --- |
| Vue frontend | Charts, order book, realtime trading UI, portfolio, contest, leaderboard, and admin views |
| FastAPI backend | Authentication, market APIs, realtime WebSockets, order execution, leaderboard, and account APIs |
| MySQL | Users, contests, accounts, balances, positions, orders, and fills |
| DuckDB | Historical Binance Spot candles and ingestion checkpoints |
| Binance REST/WebSocket APIs | Latest prices, order-book depth, fallback candles, realtime streams, and historical backfill |
| Solana devnet | On-chain contest join proof and certificate claim registry |
| Pinata IPFS | Certificate PNG images and NFT metadata JSON |

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

The current live price and order-book endpoints use the in-process realtime cache when
available, then fall back to Binance REST. Historical chart requests use DuckDB first,
then fall back to Binance when stored data is unavailable.

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
Order reconciliation is enabled by default with `CRYPTO_PENDING_ORDER_RECONCILE_ON_STARTUP=true`
and `CRYPTO_ORDER_RECONCILE_INTERVAL_SECONDS=30`; it checks pending limit orders and TP/SL
controls after market repair catches up.

For Solana devnet and certificate export, set:

```env
SOLANA_RPC_URL=https://api.devnet.solana.com
SOLANA_CONTEST_PROGRAM_ID=9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
PINATA_JWT=<your_pinata_jwt>
PINATA_GATEWAY_URL=https://gateway.pinata.cloud/ipfs
```

For the frontend wallet join flow, create a root `.env` if needed:

```env
VITE_SOLANA_CLUSTER=devnet
VITE_SOLANA_RPC_URL=https://api.devnet.solana.com
VITE_SOLANA_CONTEST_PROGRAM_ID=9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
```

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

### 6. Solana devnet admin operations

The Anchor workspace lives in `solana/`. Detailed WSL deployment instructions are in
`docs/solana-devnet-deployment.md`.

Install Solana script dependencies:

```bash
cd solana
npm install
```

The current devnet program is:

```text
contest_nft: 9r5T4DCQoY4sAtJm9uH2j7KVahMhyH1qKbd32EsGdaNx
```

Initialize a contest PDA before users join on-chain:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- initialize-contest practice-arena
```

Enable or disable on-chain joins:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- set-join-enabled practice-arena true
```

Publish the certificate Merkle root after backend export:

```bash
ANCHOR_PROVIDER_URL=https://api.devnet.solana.com \
ANCHOR_WALLET=~/.config/solana/contest-devnet.json \
npm run admin -- publish-certificate-root practice-arena <MERKLE_ROOT_HEX> <SNAPSHOT_HASH_HEX>
```

Do not commit Solana deploy keypairs, wallet keypairs, `solana/target/`, `solana/.anchor/`,
or `solana/test-ledger/`.

## API

Public market endpoints:

```text
GET /api/crypto/assets
GET /api/crypto/prices/latest
GET /api/crypto/candles?symbol=BTCUSDT&timeframe=1h
GET /api/crypto/indicators?symbol=BTCUSDT&timeframe=1h&indicator=MACD
GET /api/crypto/orderbook?symbol=BTCUSDT
WS  /api/crypto/ws
```

Contest and trading endpoints:

```text
GET  /api/crypto/contests
GET  /api/crypto/contests/{contest_id}
GET  /api/crypto/contests/{contest_id}/leaderboard
POST /api/crypto/contests/{contest_id}/join
GET  /api/crypto/contests/{contest_id}/wallet
POST /api/crypto/contests/{contest_id}/join/confirm
GET  /api/crypto/accounts/{contest_id}
POST /api/crypto/orders/market
POST /api/crypto/orders/{order_id}/cancel?contest_id={contest_id}
GET  /api/leaderboard/{contest_id}?sort_by=equity
WS   /api/leaderboard/ws/{contest_id}?sort_by=equity
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
POST /api/admin/crypto/contests/{contest_id}/settle
POST /api/admin/crypto/contests/{contest_id}/resettle
GET  /api/admin/crypto/contests/{contest_id}/settlement
POST /api/admin/crypto/contests/{contest_id}/certificates/export
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
- Users can connect a Solana wallet and submit an on-chain `join_contest` transaction.
- The backend verifies the join transaction and locks one Solana wallet address per user per contest.

### Contest Settlement

- Settlement is admin-triggered from `/api/admin/crypto/contests/{contest_id}/settle`.
- Re-running `settle` after completion returns the existing settlement snapshot.
- `/resettle` creates a new settlement version and should be used only for controlled admin correction.
- During settlement, all trading accounts are frozen and all pending orders are cancelled.
- Pending buy orders release locked quote cash back to available cash.
- Pending sell orders release locked position quantity back to the open position.
- Open positions are not force-sold and no settlement sell order or extra fee is created.
- Final equity is mark-to-market:

```text
final_equity = quote_cash_after_releasing_locks + sum(position_quantity * settlement_price)
```

- Settlement price is the close of the latest closed `1m` DuckDB candle at or before `contest.ends_at`.
- If a settlement price is missing for any open position, settlement fails instead of guessing.
- The stored settlement snapshot includes final rows, settlement prices, cancelled orders, version, and a deterministic SHA-256 hash for later smart contract or export workflows.

### Solana Certificates

- Certificate eligibility is limited to settled top-10 participants with a locked Solana wallet.
- Admins export certificates with `/api/admin/crypto/contests/{contest_id}/certificates/export`.
- Export renders a PNG certificate, uploads the image and metadata JSON to Pinata, and stores claim rows in MySQL.
- Each claim includes rank, recipient, final equity, ROI, snapshot hash, IPFS image URI, IPFS metadata URI, Merkle leaf, and Merkle proof.
- Admins publish the exported Merkle root and snapshot hash on-chain with `npm run admin -- publish-certificate-root`.
- The current on-chain certificate instruction verifies Merkle proofs and records one certificate claim per wallet per contest. Full Metaplex NFT mint UI remains a follow-up.

## Verification

```powershell
npm.cmd run test:unit
npm.cmd run type-check
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest backend_v2\tests -q
```

Solana targeted checks:

```powershell
Set-Location solana
npx.cmd ts-mocha -p .\tsconfig.json -t 1000000 tests\admin_script.ts
npx.cmd tsc --noEmit -p .\tsconfig.json
Set-Location ..
```

Run Anchor tests in WSL:

```bash
cd /mnt/c/Users/Lenovo/Downloads/crypto-dex-trading-contest/solana
anchor test
```

## Roadmap

1. Certificate claim API and frontend UI for eligible users.
2. Full Metaplex NFT mint integration for certificate claims.
3. Devnet/testnet faucet for users who need test SOL.
4. Binance Futures market data after the Spot workflow is stable.

## Safety

This app must not include real deposits, withdrawals, mainnet swaps, exchange order execution,
automated trading signals, guaranteed returns, payment or premium flows, or real-money payouts.
