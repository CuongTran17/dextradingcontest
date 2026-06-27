# Crypto DEX Trading Contest Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the copied stock platform into an educational crypto trading contest MVP with simulated market orders, virtual portfolio, contests, and leaderboard.

**Architecture:** Keep the existing Vue 3/Vite/Tailwind frontend and Python backend structure. Build a typed frontend crypto domain layer first, then route the app through crypto pages, then add backend-shaped simulator endpoints for Phase B to replace with persistent services.

**Tech Stack:** Vue 3, TypeScript, Vite, Tailwind CSS, lightweight-charts, Vitest, Python FastAPI structure, localStorage-backed simulation state for Phase A.

---

## File Map

Frontend files to create:

- `src/types/crypto.ts` shared domain types.
- `src/constants/cryptoAssets.ts` BTC/ETH/SOL/USDT_TEST metadata.
- `src/constants/cryptoContests.ts` Phase A contest fixtures.
- `src/services/cryptoMarketData.ts` deterministic mock candles and latest prices.
- `src/services/tradingSimulator.ts` market order accounting, fee, slippage, PnL, ROI.
- `src/stores/cryptoContestStore.ts` localStorage state for joined contests and portfolios.
- `src/components/crypto/SimulationDisclaimer.vue`
- `src/components/crypto/CryptoChart.vue`
- `src/components/crypto/OrderTicket.vue`
- `src/components/crypto/PortfolioSummary.vue`
- `src/components/crypto/LeaderboardTable.vue`
- `src/views/CryptoDashboard.vue`
- `src/views/CryptoTrade.vue`
- `src/views/ContestList.vue`
- `src/views/ContestDetail.vue`
- `src/views/ContestLeaderboard.vue`
- `src/views/VirtualPortfolio.vue`

Frontend files to modify:

- `package.json`, `README.md`
- `src/router/index.ts`, `src/router/__tests__/index.test.ts`
- `src/components/layout/AppSidebar.vue`
- `src/components/layout/header/SearchBar.vue`
- `src/constants/navigation.ts`
- `src/views/Admin/AdminDashboard.vue`

Backend files to create or modify:

- `backend_v2/src/routes/crypto.py`
- `backend_v2/src/services/crypto_simulator.py`
- `backend_v2/src/main.py`
- `backend_v2/tests/test_crypto_simulator.py`
- `backend_v2/tests/test_crypto_routes.py`

---

### Task 1: Project Identity And Safety Baseline

**Files:**
- Modify: `package.json`
- Modify: `README.md`
- Create: `src/components/crypto/SimulationDisclaimer.vue`

- [ ] **Step 1: Initialize git if the copied folder has no repository**

Run: `git status`

Expected if no repo: `fatal: not a git repository`.

Run when needed: `git init`

Expected: repository initialized in `C:\Users\Lenovo\Downloads\crypto-dex-trading-contest`.

- [ ] **Step 2: Rename package**

Change the top of `package.json`:

```json
{
  "name": "crypto-dex-trading-contest",
  "version": "0.1.0",
  "private": true,
  "type": "module"
}
```

Keep existing dependencies and scripts.

- [ ] **Step 3: Replace README opening**

Start `README.md` with:

```markdown
# Educational Crypto DEX Trading Contest

This project is an educational crypto trading contest simulator. Users receive virtual USDT_TEST, analyze crypto charts, place simulated market buy/sell orders, and compete on public leaderboards.

All balances, positions, trades, PnL, ROI, contest rewards, and leaderboard results are simulated. They have no real-money value. The app does not provide investment advice, exchange trading execution, deposits, withdrawals, or mainnet swaps.
```

- [ ] **Step 4: Add disclaimer component**

Create `src/components/crypto/SimulationDisclaimer.vue`:

```vue
<template>
  <section class="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100">
    <strong class="font-semibold">Educational simulator.</strong>
    All balances, trades, PnL, ROI, and contest rankings are virtual and have no real-money value. This is not investment advice.
  </section>
</template>
```

- [ ] **Step 5: Verify and commit**

Run: `npm.cmd pkg get name version private`

Expected: output includes `crypto-dex-trading-contest`, `0.1.0`, and `true`.

Commit:

```bash
git add package.json README.md src/components/crypto/SimulationDisclaimer.vue
git commit -m "chore: rename app for crypto contest"
```

---

### Task 2: Crypto Domain Fixtures

**Files:**
- Create: `src/types/crypto.ts`
- Create: `src/constants/cryptoAssets.ts`
- Create: `src/constants/cryptoContests.ts`
- Create: `src/services/cryptoMarketData.ts`
- Create: `src/services/__tests__/cryptoMarketData.test.ts`

- [ ] **Step 1: Add domain types**

Create `src/types/crypto.ts`:

```ts
export type CryptoSymbol = 'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT'
export type ContestStatus = 'practice' | 'upcoming' | 'active' | 'ended'
export type OrderSide = 'buy' | 'sell'
export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1D'

export interface Candle { time: number; open: number; high: number; low: number; close: number; volume: number }
export interface CryptoAsset { symbol: CryptoSymbol; baseAsset: 'BTC' | 'ETH' | 'SOL'; quoteAsset: 'USDT_TEST'; displayName: string; pricePrecision: number; quantityPrecision: number }
export interface Contest { id: string; title: string; status: ContestStatus; mode: 'practice' | 'contest'; initialCapital: number; symbols: CryptoSymbol[]; startsAt: string; endsAt: string; participantCount: number }
export interface Position { symbol: CryptoSymbol; quantity: number; averageEntry: number }
export interface SimulatedOrder { id: string; contestId: string; symbol: CryptoSymbol; side: OrderSide; quantity: number; executionPrice: number; notional: number; fee: number; slippage: number; createdAt: string }
export interface VirtualPortfolio { contestId: string; cash: number; positions: Position[]; orders: SimulatedOrder[] }
```

- [ ] **Step 2: Add assets and contests**

Create `src/constants/cryptoAssets.ts`:

```ts
import type { CryptoAsset, CryptoSymbol } from '@/types/crypto'

export const DEFAULT_CRYPTO_SYMBOL: CryptoSymbol = 'BTCUSDT'
export const DEFAULT_TRADE_PATH = `/trade/${DEFAULT_CRYPTO_SYMBOL}`
export const CRYPTO_ASSETS: CryptoAsset[] = [
  { symbol: 'BTCUSDT', baseAsset: 'BTC', quoteAsset: 'USDT_TEST', displayName: 'Bitcoin / USDT_TEST', pricePrecision: 2, quantityPrecision: 6 },
  { symbol: 'ETHUSDT', baseAsset: 'ETH', quoteAsset: 'USDT_TEST', displayName: 'Ethereum / USDT_TEST', pricePrecision: 2, quantityPrecision: 5 },
  { symbol: 'SOLUSDT', baseAsset: 'SOL', quoteAsset: 'USDT_TEST', displayName: 'Solana / USDT_TEST', pricePrecision: 3, quantityPrecision: 3 },
]
export function findCryptoAsset(symbol: string) { return CRYPTO_ASSETS.find((asset) => asset.symbol === symbol) }
```

Create `src/constants/cryptoContests.ts`:

```ts
import type { Contest } from '@/types/crypto'

export const DEFAULT_CONTEST_ID = 'practice-arena'
export const CRYPTO_CONTESTS: Contest[] = [
  { id: 'practice-arena', title: 'Practice Arena', status: 'practice', mode: 'practice', initialCapital: 10000, symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'], startsAt: '2026-06-23T00:00:00.000Z', endsAt: '2026-12-31T23:59:59.000Z', participantCount: 128 },
  { id: 'summer-crypto-cup', title: 'Summer Crypto Cup', status: 'active', mode: 'contest', initialCapital: 10000, symbols: ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'], startsAt: '2026-06-20T00:00:00.000Z', endsAt: '2026-07-20T23:59:59.000Z', participantCount: 42 },
]
```

- [ ] **Step 3: Add deterministic mock market data**

Create `src/services/cryptoMarketData.ts` with `BASE_PRICES`, `TIMEFRAME_SECONDS`, `getLatestCryptoPrice(symbol)`, and `getCryptoCandles(symbol, timeframe, count)`. Use BTC 64250, ETH 3420, SOL 148 as seed prices. Candle output must include `time`, `open`, `high`, `low`, `close`, and `volume`.

- [ ] **Step 4: Test market data**

Create `src/services/__tests__/cryptoMarketData.test.ts` asserting `getLatestCryptoPrice('BTCUSDT') > 0` and `getCryptoCandles('BTCUSDT', '1h', 20)` returns 20 candles with increasing time.

Run: `npm.cmd run test:unit -- src/services/__tests__/cryptoMarketData.test.ts`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/types/crypto.ts src/constants/cryptoAssets.ts src/constants/cryptoContests.ts src/services/cryptoMarketData.ts src/services/__tests__/cryptoMarketData.test.ts
git commit -m "feat: add crypto domain fixtures"
```

---

### Task 3: Trading Simulator And Local State

**Files:**
- Create: `src/services/tradingSimulator.ts`
- Create: `src/services/__tests__/tradingSimulator.test.ts`
- Create: `src/stores/cryptoContestStore.ts`
- Create: `src/stores/__tests__/cryptoContestStore.test.ts`

- [ ] **Step 1: Add simulator tests**

Create tests that verify:

```ts
executeMarketOrder(emptyPortfolio, { contestId: 'practice-arena', symbol: 'BTCUSDT', side: 'buy', quantity: 0.1, latestPrice: 50000 })
```

Expected cash after buy: close to `4995`. Expected first position: `BTCUSDT` quantity `0.1`. Oversized sell from an empty portfolio must throw `Insufficient BTCUSDT position`. Metrics after buying 1 ETH at 3000 and marking ETH at 3300 must have positive ROI.

- [ ] **Step 2: Implement simulator**

Create `src/services/tradingSimulator.ts` with:

```ts
const FEE_RATE = 0.001
const SLIPPAGE_RATE = 0.0005
const INITIAL_CAPITAL = 10000
```

Export:

```ts
executeMarketOrder(portfolio, input)
calculatePortfolioMetrics(portfolio, latestPrices)
```

Buy orders subtract `notional + fee` from USDT_TEST cash and update weighted average entry. Sell orders require enough position quantity, add `notional - fee` to cash, and remove zero positions. Every order records `id`, `contestId`, `symbol`, `side`, `quantity`, `executionPrice`, `notional`, `fee`, `slippage`, and `createdAt`.

- [ ] **Step 3: Add store helpers**

Create `src/stores/cryptoContestStore.ts`:

```ts
import type { VirtualPortfolio } from '@/types/crypto'

const STORAGE_KEY = 'crypto-contest-state-v1'
export interface CryptoContestState { joinedContestIds: string[]; portfolios: Record<string, VirtualPortfolio> }
export function createInitialPortfolio(contestId: string, initialCapital: number): VirtualPortfolio { return { contestId, cash: initialCapital, positions: [], orders: [] } }
export function loadContestState(): CryptoContestState { const raw = window.localStorage.getItem(STORAGE_KEY); if (!raw) return { joinedContestIds: [], portfolios: {} }; try { return JSON.parse(raw) as CryptoContestState } catch { return { joinedContestIds: [], portfolios: {} } } }
export function saveContestState(state: CryptoContestState): void { window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state)) }
```

- [ ] **Step 4: Add store tests**

Create tests that clear localStorage, create a portfolio with 10000 cash, save it, and load it back with `joinedContestIds: ['practice-arena']`.

Run:

```bash
npm.cmd run test:unit -- src/services/__tests__/tradingSimulator.test.ts src/stores/__tests__/cryptoContestStore.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/services/tradingSimulator.ts src/services/__tests__/tradingSimulator.test.ts src/stores/cryptoContestStore.ts src/stores/__tests__/cryptoContestStore.test.ts
git commit -m "feat: add virtual trading state"
```

---

### Task 4: Router Conversion

**Files:**
- Modify: `src/router/index.ts`
- Modify: `src/router/__tests__/index.test.ts`
- Create: initial minimal versions of `src/views/CryptoDashboard.vue`, `src/views/CryptoTrade.vue`, `src/views/ContestList.vue`, `src/views/ContestDetail.vue`, `src/views/ContestLeaderboard.vue`, `src/views/VirtualPortfolio.vue`

- [ ] **Step 1: Update route tests first**

Replace public route expectations with:

```ts
['/', 'CryptoDashboard']
['/trade/BTCUSDT', 'CryptoTrade']
['/contests', 'ContestList']
['/contests/practice-arena', 'ContestDetail']
['/contests/practice-arena/leaderboard', 'ContestLeaderboard']
```

Protected guest redirects should include `/portfolio`, `/admin`, `/premium`, and `/profile`.

- [ ] **Step 2: Replace routes**

In `src/router/index.ts`, route to:

```ts
{ path: '/', name: 'CryptoDashboard', component: () => import('../views/CryptoDashboard.vue'), meta: { title: 'Crypto Contest Dashboard' } }
{ path: '/trade/:symbol?', name: 'CryptoTrade', component: () => import('../views/CryptoTrade.vue'), meta: { title: 'Trade Simulator' } }
{ path: '/contests', name: 'ContestList', component: () => import('../views/ContestList.vue'), meta: { title: 'Trading Contests' } }
{ path: '/contests/:contestId', name: 'ContestDetail', component: () => import('../views/ContestDetail.vue'), meta: { title: 'Contest Detail' } }
{ path: '/contests/:contestId/leaderboard', name: 'ContestLeaderboard', component: () => import('../views/ContestLeaderboard.vue'), meta: { title: 'Leaderboard' } }
{ path: '/portfolio', name: 'VirtualPortfolio', component: () => import('../views/VirtualPortfolio.vue'), meta: { title: 'Virtual Portfolio', requiresAuth: true } }
```

Set public route names to the five public crypto routes plus auth routes. Use `Crypto Contest` in `document.title`. Catch-all redirects to `/`.

- [ ] **Step 3: Run route tests**

Run: `npm.cmd run test:unit -- src/router/__tests__/index.test.ts`

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/router/index.ts src/router/__tests__/index.test.ts src/views/CryptoDashboard.vue src/views/CryptoTrade.vue src/views/ContestList.vue src/views/ContestDetail.vue src/views/ContestLeaderboard.vue src/views/VirtualPortfolio.vue
git commit -m "feat: route app around crypto contests"
```

---

### Task 5: Crypto Pages And Components

**Files:**
- Create: `src/components/crypto/CryptoChart.vue`
- Create: `src/components/crypto/OrderTicket.vue`
- Create: `src/components/crypto/PortfolioSummary.vue`
- Create: `src/components/crypto/LeaderboardTable.vue`
- Modify: crypto view files from Task 4
- Create: `src/views/__tests__/CryptoTrade.test.ts`

- [ ] **Step 1: Build reusable components**

`CryptoChart.vue` uses `lightweight-charts`, fixed-height chart container, `symbol` and `timeframe` props, and candles from `getCryptoCandles`.

`OrderTicket.vue` has buy/sell segmented buttons, numeric quantity input, estimated notional, fee, slippage note, error slot or prop, and emits `submit` with `{ side, quantity }`.

`PortfolioSummary.vue` shows cash, equity, PnL, ROI, positions, and recent orders.

`LeaderboardTable.vue` shows rank, user/wallet, equity, PnL, ROI, volume, trade count, win rate, max drawdown, and last trade. Sort rows by ROI descending.

- [ ] **Step 2: Build pages**

`CryptoDashboard.vue`: disclaimer, market cards for BTC/ETH/SOL, active contest cards, portfolio snapshot, recent trades.

`CryptoTrade.vue`: route symbol defaulting to BTCUSDT, timeframe controls, chart, order ticket, portfolio summary, order history. Submit calls `executeMarketOrder`, persists state, and shows validation errors inline.

`ContestList.vue`: contest cards grouped by practice, upcoming, active, ended.

`ContestDetail.vue`: rules, timer, symbols, participant count, join button, leaderboard link.

`ContestLeaderboard.vue`: public leaderboard for route contest ID.

`VirtualPortfolio.vue`: protected portfolio view with practice reset action only for practice contests.

- [ ] **Step 3: Add trade view test**

Create `src/views/__tests__/CryptoTrade.test.ts` asserting the rendered text includes `Educational simulator`, `Buy`, `Sell`, and `BTCUSDT`.

Run:

```bash
npm.cmd run test:unit -- src/views/__tests__/CryptoTrade.test.ts src/router/__tests__/index.test.ts
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/components/crypto src/views/CryptoDashboard.vue src/views/CryptoTrade.vue src/views/ContestList.vue src/views/ContestDetail.vue src/views/ContestLeaderboard.vue src/views/VirtualPortfolio.vue src/views/__tests__/CryptoTrade.test.ts
git commit -m "feat: add crypto contest frontend"
```

---

### Task 6: Navigation And Admin Conversion

**Files:**
- Modify: `src/constants/navigation.ts`
- Modify: `src/components/layout/AppSidebar.vue`
- Modify: `src/components/layout/header/SearchBar.vue`
- Modify: `src/components/layout/__tests__/AppSidebar.test.ts`
- Modify: `src/views/Admin/AdminDashboard.vue`
- Create: `src/views/Admin/components/TabContests.vue`
- Create: `src/views/Admin/components/TabContestParticipants.vue`
- Create: `src/views/Admin/components/TabContestResults.vue`

- [ ] **Step 1: Change navigation constants**

`src/constants/navigation.ts` should export:

```ts
export const DEFAULT_CRYPTO_SYMBOL = 'BTCUSDT'
export const DEFAULT_TRADE_PATH = `/trade/${DEFAULT_CRYPTO_SYMBOL}`
```

- [ ] **Step 2: Replace sidebar and search**

Sidebar items: Dashboard `/`, Trade Simulator `/trade/BTCUSDT`, Contests `/contests`, Leaderboard `/contests/practice-arena/leaderboard`, Virtual Portfolio `/portfolio`, Admin `/admin`.

Search should use `CRYPTO_ASSETS`, placeholder `Search BTCUSDT, ETHUSDT, SOLUSDT`, and navigate to `/trade/<symbol>`.

- [ ] **Step 3: Convert admin surface**

Admin tabs: Overview, Contests, Participants, Results. `TabContests.vue` shows contest title, status, initial capital, symbols, start/end, participants. `TabContestParticipants.vue` shows wallet/user, contest, equity, ROI, trade count. `TabContestResults.vue` shows final rank rows and certificate/NFT status as Phase B text without minting behavior.

- [ ] **Step 4: Run checks**

Run:

```bash
npm.cmd run test:unit -- src/components/layout/__tests__/AppSidebar.test.ts src/router/__tests__/index.test.ts
npm.cmd run type-check
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/constants/navigation.ts src/components/layout/AppSidebar.vue src/components/layout/header/SearchBar.vue src/components/layout/__tests__/AppSidebar.test.ts src/views/Admin/AdminDashboard.vue src/views/Admin/components/TabContests.vue src/views/Admin/components/TabContestParticipants.vue src/views/Admin/components/TabContestResults.vue
git commit -m "feat: adapt navigation and admin to crypto contests"
```

---

### Task 7: Backend Crypto API Contract

**Files:**
- Create: `backend_v2/src/services/crypto_simulator.py`
- Create: `backend_v2/src/routes/crypto.py`
- Modify: `backend_v2/src/main.py`
- Create: `backend_v2/tests/test_crypto_simulator.py`
- Create: `backend_v2/tests/test_crypto_routes.py`

- [ ] **Step 1: Add backend simulator**

Create `backend_v2/src/services/crypto_simulator.py` with `FEE_RATE = 0.001`, `SLIPPAGE_RATE = 0.0005`, and `INITIAL_CAPITAL = 10000.0`. Export `execute_market_order(portfolio, symbol, side, quantity, latest_price)` and `portfolio_metrics(portfolio, latest_prices)` using the same accounting rules as the frontend.

- [ ] **Step 2: Add backend routes**

Create `backend_v2/src/routes/crypto.py` with FastAPI router prefix `/api/crypto`:

- `GET /assets` returns BTCUSDT, ETHUSDT, SOLUSDT and quote asset USDT_TEST.
- `GET /prices/latest` returns seeded latest prices.
- `POST /orders/market` validates symbol and quantity, executes a virtual order, and returns portfolio plus metrics.

- [ ] **Step 3: Register router**

In `backend_v2/src/main.py`, add:

```py
from src.routes.crypto import router as crypto_router
app.include_router(crypto_router)
```

Place it near the existing router includes.

- [ ] **Step 4: Add backend tests**

`test_crypto_simulator.py`: buy decreases cash and creates position; oversized sell raises `ValueError`; metrics calculate equity and ROI.

`test_crypto_routes.py`: `/api/crypto/assets` includes BTCUSDT; `/api/crypto/orders/market` executes a virtual ETH buy and returns `trade_count == 1`.

- [ ] **Step 5: Run backend tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_simulator.py backend_v2\tests\test_crypto_routes.py -q
```

Expected: PASS. If the copied project has no `.venv`, run the same command with the original workspace venv or create a new project venv.

- [ ] **Step 6: Commit**

```bash
git add backend_v2/src/main.py backend_v2/src/routes/crypto.py backend_v2/src/services/crypto_simulator.py backend_v2/tests/test_crypto_simulator.py backend_v2/tests/test_crypto_routes.py
git commit -m "feat: add crypto simulator api contract"
```

---

### Task 8: Stock Surface Isolation And Final Verification

**Files:**
- Review: `src/views/Stock*.vue`, `src/views/MarketOverview.vue`, `src/views/DnseTickSandbox.vue`
- Review: `src/components/stock/*`
- Review: `src/services/stockBackendApi.ts`, `src/services/dnse*.ts`, `src/composables/useStockData.ts`, `src/stores/stockPriceStore.ts`
- Modify: tests that still assert removed stock routes or labels

- [ ] **Step 1: Search stock wording**

Run:

```bash
rg -n "stock|Stock|cổ phiếu|VNSTOCK|DNSE|FPT|VCB|VIC|vnstock" src README.md package.json
```

Expected: results are either removed, replaced, or inactive legacy code not imported by router.

- [ ] **Step 2: Remove inactive stock UI imports**

Delete stock views/components only after the crypto replacements build. Keep backend stock modules isolated in Phase A unless they break tests or build.

- [ ] **Step 3: Run full frontend verification**

Run:

```bash
npm.cmd run test:unit
npm.cmd run build
```

Expected: all active frontend tests pass and Vite build completes.

- [ ] **Step 4: Run backend crypto verification**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_simulator.py backend_v2\tests\test_crypto_routes.py -q
```

Expected: PASS.

- [ ] **Step 5: Manual smoke test**

Run: `npm.cmd run dev`

Open `http://localhost:5174` and verify:

- `/` shows crypto contest dashboard and disclaimer.
- `/trade/BTCUSDT` shows chart, order ticket, portfolio, and order history.
- Buy decreases USDT_TEST and creates a BTC position.
- Sell decreases the BTC position and updates PnL/ROI.
- `/contests` lists practice and active contests.
- `/contests/practice-arena/leaderboard` sorts by ROI.
- `/portfolio` redirects guests to signin.
- `/admin` remains admin-protected.

- [ ] **Step 6: Commit final verification changes**

```bash
git add README.md src backend_v2
git add -u src backend_v2
git commit -m "test: verify crypto contest phase a"
```

---

## Completion Criteria

Phase A is complete when these pass:

```bash
npm.cmd run test:unit
npm.cmd run build
.\.venv\Scripts\python.exe -m pytest backend_v2\tests\test_crypto_simulator.py backend_v2\tests\test_crypto_routes.py -q
```

The first screen must be a crypto contest dashboard. Trading screens must show simulator safety language. The app must not include deposits, withdrawals, mainnet swaps, exchange order execution, automated signals, guaranteed returns, or real-money payout flows.
