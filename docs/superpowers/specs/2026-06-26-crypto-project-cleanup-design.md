# Crypto Project Cleanup Design

## Goal

Convert the repository from a reused stock-market application into a focused educational
crypto trading contest project before adding Binance WebSocket ingestion.

The cleanup must preserve the current crypto functionality, frontend styling, and existing
MySQL database. It must remove legacy backend runtime code and move old frontend screens out
of the production application while keeping them available for reference.

## Decisions

- Keep the existing `crypto_dex` MySQL database and all current tables.
- Do not drop or recreate MySQL tables during this cleanup.
- Do not rewrite or squash existing Alembic migration history.
- Remove legacy stock, DNSE, VNStock, ETL, AI/Kaggle, news, payment, and premium backend code.
- Keep the crypto frontend, authentication, profile, layout, CSS, contest, portfolio, and admin
  foundations.
- Move unused legacy frontend code outside `src` so it is excluded from router, type checking,
  tests, and production builds.
- Remove premium and payment navigation and authorization behavior.
- Keep historical legacy implementation available in Git history and in the frontend reference
  directory where useful.

## Target Runtime

### Backend

The FastAPI application will expose only:

- Authentication and user profile APIs.
- Crypto asset, price, candle, and order-book APIs.
- Crypto contest participation and virtual account APIs.
- Simulated crypto market-order execution.
- Crypto-focused admin APIs.
- Health checks.

The application lifespan will initialize only the MySQL connection and crypto-specific
services. It will not start stock preloaders, ETL jobs, AI jobs, DNSE polling, news fetching,
mock stock streaming, or payment integrations.

### Data Stores

| Store | Retained responsibility |
| --- | --- |
| MySQL `crypto_dex` | Users, contests, participants, accounts, balances, positions, orders, and fills |
| DuckDB `crypto_market.duckdb` | Binance Spot candle history and ingestion checkpoints |

Legacy MySQL tables may remain physically present, but no retained runtime module may query or
write them.

### Frontend

The production frontend will retain:

- Shared Tailwind styles, theme, layout, icons, and reusable UI components.
- Crypto dashboard and trading screen.
- Contest list, detail, and leaderboard screens.
- Virtual crypto portfolio.
- Sign-in, sign-up, guest gate, and profile screens.
- Admin foundation needed for future contest management.

The production router and sidebar will no longer expose stock, DNSE, AI, premium, or payment
features.

Unused frontend screens and their feature-specific services, stores, composables, constants,
and tests will move to `legacy/frontend/`. This directory is reference-only and is not imported
by production code.

## Backend Removal Scope

The cleanup will remove modules whose only purpose is:

- Vietnam stock market data.
- DNSE polling, caching, and sandbox views.
- VNStock ingestion and rate limiting.
- Stock ETL and data-lake orchestration.
- Stock AI analysis, Kaggle integration, and prediction caches.
- News, events, fundamentals, and technical stock analysis.
- SePay, premium subscriptions, promotions, and payment callbacks.
- Legacy stock portfolio and alert APIs.
- Legacy stock WebSocket routes.

Shared modules will be inspected before removal. Authentication, database session management,
error handling, request IDs, and configuration helpers will be retained or reduced when crypto
code still depends on them.

## Migration Strategy

Existing migrations remain unchanged so the current `crypto_dex` database continues to match
its recorded Alembic revision.

Future migrations will manage only crypto contest features. Legacy tables will not be removed
as part of this cleanup. If they are removed later, that will be a separate explicit migration
after confirming backups and data-retention requirements.

## Dependency Cleanup

After code removal, backend dependencies will be reduced to packages required by:

- FastAPI and Uvicorn.
- SQLAlchemy, Alembic, MySQL connectors, and authentication.
- HTTPX for Binance REST.
- DuckDB, pandas, and PyArrow for the crypto warehouse.
- Redis only if retained crypto code actually uses it.

Packages used only by VNStock, news, scheduling, stock analysis, or payment flows will be
removed.

Frontend dependencies will be removed only when no retained production or legacy-reference
workflow needs them. Moving files to `legacy/frontend/` does not require the production build
to compile those files.

## Safety Sequence

1. Establish a passing crypto-focused backend and frontend test baseline.
2. Move frontend legacy code and remove its router/sidebar references.
3. Reduce FastAPI router registration and application lifespan.
4. Remove unused backend modules in small groups.
5. Remove unused dependencies and configuration.
6. Update tests, environment examples, scripts, and README.
7. Run production build and crypto API smoke tests.

Each deletion group must be followed by import checks and tests. Existing untracked workspace
files are outside the cleanup scope and must not be deleted.

## Verification

The cleanup is complete when:

- The frontend production build contains only crypto, authentication, profile, and admin routes.
- No production import references stock, DNSE, VNStock, ETL, AI/Kaggle, premium, or payment code.
- FastAPI starts without legacy jobs or integrations.
- Existing MySQL crypto accounts and contests remain readable.
- Binance prices, DuckDB candles, order books, contest joining, account loading, and simulated
  market orders still work.
- All retained backend tests and frontend tests pass.
- The existing `crypto_dex` database is not dropped, recreated, or destructively migrated.

## Next Phase

After this cleanup is verified, the next implementation phase is Binance WebSocket ingestion
for live prices, current `1m` candles, and synchronized Spot order books.
