# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.

## Phase A

- Vue 3, TypeScript, Vite, Tailwind CSS frontend.
- FastAPI backend structure with a crypto simulator API contract.
- BTCUSDT, ETHUSDT, and SOLUSDT mock market data.
- LocalStorage-backed virtual portfolios for the frontend MVP.
- Practice and contest fixtures with public leaderboard screens.

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
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_simulator.py backend_v2\tests\test_crypto_routes.py -q
```

Crypto API contract:

```text
GET /api/crypto/assets
GET /api/crypto/prices/latest
POST /api/crypto/orders/market
```

## Safety

This app must not include real deposits, withdrawals, mainnet swaps, exchange order execution, automated trading signals, guaranteed returns, or real-money payout flows.
