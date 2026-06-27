# Educational Crypto DEX Trading Contest Design

## Decision

Build the new project by converting the existing stock platform domain into an educational crypto trading contest app. Keep the current Vue 3, Vite, Tailwind CSS, lightweight-charts, and Python backend structure for Phase A. Do not rebuild with Next.js/NestJS yet.

Phase A creates a working MVP with mock or adapter-backed crypto data. Phase B deepens the backend, realtime, wallet, and blockchain features after the product flow is validated.

## Product Positioning

The app is an educational trading simulator. Users connect or identify with a wallet-style profile, receive virtual contest capital, analyze real or simulated crypto market charts, place simulated buy/sell orders, and compete on a public leaderboard.

The app must clearly state that all balances, assets, PnL, and trades are simulated, have no real-money value, and are not investment advice.

## Phase A Scope

Phase A is a domain conversion MVP:

- Rename user-facing stock concepts to crypto contest concepts.
- Keep the existing app shell, routing, auth/admin patterns, chart library, and backend folder structure.
- Add crypto-centered pages for dashboard, trade simulator, contests, leaderboard, and virtual portfolio.
- Use BTC/USDT, ETH/USDT, and SOL/USDT as the initial assets.
- Support market buy/sell orders only.
- Track virtual USDT_TEST, positions, order history, equity, PnL, ROI, volume, trade count, and leaderboard rank.
- Provide Practice Mode and Contest Mode as product concepts, with Practice Mode allowed to reset virtual capital and Contest Mode locked by contest rules.

Out of scope for Phase A:

- Real deposits or withdrawals.
- Mainnet swaps.
- Binance/OKX trading API execution.
- AI trading recommendations.
- Copy trading.
- Limit orders, stop loss, take profit, pending orders.
- Production smart contracts and NFT minting.

## Phase B Scope

Phase B hardens the product after Phase A works:

- Replace mock price data with Binance/CoinGecko adapters and cache policy.
- Add backend contest data model and migration discipline.
- Add a trading engine service for order execution, fee/slippage simulation, portfolio accounting, and leaderboard snapshots.
- Add realtime updates through WebSocket or the existing realtime manager pattern.
- Add wallet connect/profile integration appropriate for Vue, or evaluate a framework change only after Phase A.
- Add testnet contracts for mock tokens, faucet, contest result registry, and achievement NFTs.

## Frontend Design

The first screen should be the actual crypto contest dashboard, not a marketing landing page. It should show market cards, active contests, portfolio equity, recent trades, and a clear educational/simulated disclaimer.

Primary routes:

- `/` Crypto Contest Dashboard.
- `/trade/:symbol?` Trading simulator with chart, timeframe controls, indicator toggles, order panel, positions, and order history.
- `/contests` Contest list with practice, upcoming, active, and ended states.
- `/contests/:contestId` Contest detail with rules, timer, symbols, participants, and join action.
- `/contests/:contestId/leaderboard` Public leaderboard sorted by ROI.
- `/portfolio` Virtual portfolio with balances, positions, PnL, ROI, and history.
- `/admin` Admin contest management adapted from the existing admin shell.

The UI should remain operational and dashboard-like: dense, scannable, and suited to repeated trading workflows.

## Backend Design

Keep `backend_v2` for Phase A and convert it incrementally. New or renamed domains should be introduced around these responsibilities:

- Assets: BTC, ETH, SOL, and USDT_TEST metadata.
- Price service: latest prices and candle data, initially mock/sample or adapter-backed.
- Contests: lifecycle, rules, symbols, initial capital, start/end times.
- Participants: user/wallet association and contest balances.
- Orders/trades: market order requests and execution records.
- Portfolio: virtual balances, positions, equity, PnL, ROI.
- Leaderboard: rank calculation and snapshots.

The execution rule for Phase A:

1. User submits buy or sell market order.
2. Backend resolves latest price.
3. Backend applies configured fee and slippage simulation.
4. Backend validates virtual balance or position.
5. Backend records order/trade.
6. Backend updates virtual portfolio and leaderboard metrics.

## Data Model Targets

The target entities are:

- `users`
- `assets`
- `contests`
- `contest_participants`
- `orders`
- `trades`
- `portfolios`
- `leaderboard_snapshots`
- `price_candles`

Phase A may begin with existing storage patterns or in-memory/mock data where useful, but names and API boundaries should point toward this model.

## Migration Strategy From Stock Project

1. Copy the existing project into `C:\Users\Lenovo\Downloads\crypto-dex-trading-contest` without `.git`, `node_modules`, build output, virtualenv, generated market data, or real `.env` secrets.
2. Rename package/app metadata and visible product text from stock/Vietnam-market wording to crypto contest wording.
3. Replace main navigation and routes with crypto contest pages.
4. Introduce crypto mock data and service interfaces before deleting old stock modules.
5. Convert reusable stock chart/portfolio/order components into crypto equivalents.
6. Keep old stock-specific files only until their crypto replacements pass build/tests, then remove or archive them deliberately.

## Safety Rules

The product must not contain flows for real-money deposits, withdrawals, mainnet swaps, or exchange order execution. Every trade-related screen must make clear that the environment is simulated and educational.

Contest screens must not give buy/sell recommendations. Indicators may be shown, but the app should not explain them as signals during contests.

## Success Criteria For Phase A

- The copied project installs and builds independently.
- The app opens as a crypto contest dashboard, not a stock dashboard.
- Users can view BTC/ETH/SOL chart data.
- Users can place simulated market buy/sell orders using USDT_TEST.
- Portfolio, PnL, ROI, and order history update from simulated trades.
- Contest join and leaderboard flows are represented in the UI.
- Admin can create or manage contest-shaped records at least at mock/API-contract level.
- All visible safety disclaimers are present.
