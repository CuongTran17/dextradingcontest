# Strict Snapshot Data Mode Design

Date: 2026-05-14

## Goal

Move market data handling to a manual, reproducible dataset snapshot model.
The application must not pull, refresh, or repair market data implicitly during
normal backend startup or read API traffic.

The short-term serving model remains:

- MySQL cache tables are the primary serving layer for market APIs.
- Parquet/lake outputs are the source of truth and audit trail.
- Only explicit ETL execution can create or update market snapshots and caches.
- Missing or stale data is reported, not auto-fixed.

## Non-Goals

- Do not migrate stock/market APIs to DuckDB or Parquet serving in this phase.
- Do not redesign the whole ETL into bronze/silver/gold in this phase.
- Do not remove existing MySQL market cache tables yet.
- Do not remove the admin ETL trigger.
- Do not add new automatic schedulers or background data refresh paths.

## Invariants

1. Backend startup is read-only for market data.
2. Read APIs never create market data.
3. Only CLI/admin ETL can write snapshot/cache.
4. Missing/stale data is reported, not auto-fixed.

## Data Status Contract

Market-data endpoints should speak a shared status vocabulary:

- `DATA_AVAILABLE`: requested data is available from the current serving layer.
- `NO_DATA_IN_SNAPSHOT`: a snapshot exists, but the requested symbol/range/entity
  is not present.
- `SNAPSHOT_NOT_BUILT`: no usable ETL snapshot or metadata exists.
- `REFRESH_DISABLED_IN_SNAPSHOT_MODE`: a read path attempted explicit refresh
  in snapshot mode.
- `ETL_RUNNING`: an ETL run is currently in progress.
- `ETL_FAILED`: the latest ETL run failed.
- `STALE_SNAPSHOT`: the latest usable snapshot is older than the configured
  freshness threshold.

Responses should include this status in a stable metadata field. Existing
payload shapes may remain compatible where practical, but missing/stale cases
must be visible to the frontend.

## Runtime Boundaries

FastAPI startup should initialize application infrastructure only:

- Initialize schema/migrations as currently configured.
- Register routes and middleware.
- Read settings.
- Do not start `fetcher_service.fetch_loop()`.
- Do not call `preload_historical_data()`.
- Do not call `preload_reference_caches()`.
- Do not start `run_mock_streamer()`.
- Do not register embedded `EtlScheduler` jobs.
- Do not run EOD aggregation during shutdown.

The standalone `etl.scheduler` module may remain in the repository for now, but
the backend runtime must not register or start it. Documentation should describe
manual CLI/admin ETL as the supported update path in snapshot mode.

## Write Paths

The only allowed stock/market data write paths are:

1. CLI ETL:

   ```powershell
   .\.venv\Scripts\python.exe -m etl.run_etl --symbols FPT,VCB --run-mode incremental
   ```

2. Admin ETL trigger:

   ```text
   POST /api/etl/trigger
   ```

Both paths execute the ETL pipeline, write lake/parquet artifacts, and publish
serving data into MySQL cache tables. Read APIs must not bypass these paths.

## Read API Behavior

Read APIs should read from the short-term serving layer only:

- Stock snapshots: read existing cache/state and database-backed history.
- Stock history: read `daily_ohlcv`.
- Intraday/ticks: read existing cache/lake-backed tick state only.
- Company overview: read `company_overview_cache`.
- Financials: read `financial_report_cache`.
- News/events: read `news_cache` and `events_cache`.
- Technical data: compute from served history or read `technical_cache`, but do
  not fetch source data if history is missing.
- Market indices: read snapshot/cache/lake-derived serving data, not `vnstock`
  directly from read routes.
- Analysis generation: build context from existing snapshot/cache only; it must
  not refresh fundamentals, news, or price history from market data sources.

If clients send `refresh=true` to a read endpoint in snapshot mode, return a
clear `REFRESH_DISABLED_IN_SNAPSHOT_MODE` status instead of performing the
refresh. This is intentionally loud so stale frontend call sites are found.

If data is missing, return `NO_DATA_IN_SNAPSHOT` or `SNAPSHOT_NOT_BUILT` instead
of silently calling an upstream provider.

## Frontend Behavior

General user-facing refresh buttons should mean "reload from the current
snapshot", not "pull new market data".

Frontend service methods should stop sending `refresh=true` for read APIs.
Screens such as Market Overview, Stock Detail, News/Events, and AI Analysis can
still reload visible data, but they should only re-query the backend read
endpoints.

Admin ETL Monitor remains the place where users intentionally create a new data
snapshot:

- Keep the manual ETL trigger button.
- Show `ETL_RUNNING` after a run starts.
- Show `ETL_FAILED` if latest metadata reports failure.
- Show `STALE_SNAPSHOT` when the current snapshot is older than the freshness
  threshold.
- Make it clear that MySQL is the short-term serving layer and lake/parquet is
  the source of truth.

## Error and Empty States

Frontend should map the shared statuses to explicit UI states:

- `SNAPSHOT_NOT_BUILT`: "No dataset snapshot has been built yet."
- `NO_DATA_IN_SNAPSHOT`: "The current snapshot does not contain this data."
- `STALE_SNAPSHOT`: show existing data with a stale snapshot warning.
- `ETL_RUNNING`: show current data if available and note that a new snapshot is
  being built.
- `ETL_FAILED`: show current data if available and surface the latest ETL error.
- `REFRESH_DISABLED_IN_SNAPSHOT_MODE`: treat as an integration bug; normal UI
  should stop producing this state after frontend updates.

## Short-Term Implementation Areas

- `backend_v2/src/jobs.py`: make FastAPI lifespan market-data read-only.
- `backend_v2/src/routes/stocks.py`: remove read-path refresh and auto-repair.
- `backend_v2/src/routes/market.py`: remove direct market-source fetches from
  read routes.
- `backend_v2/src/routes/analysis.py`: use snapshot/cache context only.
- `backend_v2/src/routes/internal.py`: disable debug intraday refresh in
  snapshot mode; review whether manual quote ingestion remains in scope.
- `backend_v2/src/routes/etl_status.py`: keep admin manual trigger and expose
  status metadata clearly.
- `src/services/stockBackendApi.ts`: stop sending refresh params from read
  methods.
- User-facing Vue views: make refresh buttons reload current snapshot only.
- `README.md`: document strict snapshot mode and the status contract.

## Future Warehouse Direction

The long-term direction is to remove stock/market cache storage from MySQL.
MySQL should eventually store only application and user-domain data:

- users/auth/session-related data
- subscription/payment/business records
- portfolio/watchlist/alerts/user settings
- admin records unrelated to market snapshots

Market data should move to a lakehouse/warehouse model:

```text
External sources
  -> bronze parquet
  -> silver parquet
  -> gold parquet
  -> DuckDB warehouse/views
  -> Stock/Market APIs

MySQL
  -> user/app/business data only
```

Potential long-term layout:

```text
lake/
  bronze/
    prices/run_id=*/data.parquet
    company_overview/run_id=*/data.parquet
    financial_reports/run_id=*/data.parquet
    news/run_id=*/data.parquet
    market_indices/run_id=*/data.parquet
  silver/
    daily_ohlcv/run_id=*/data.parquet
    symbols/run_id=*/data.parquet
    financial_metrics/run_id=*/data.parquet
    news_events/run_id=*/data.parquet
  gold/
    market_features/run_id=*/data.parquet
    symbol_snapshot/run_id=*/data.parquet
    latest_manifest.json
warehouse/
  market.duckdb
  schema.sql
  views.sql
```

Future migration phases:

1. Current phase: strict snapshot mode, MySQL cache remains primary serving.
2. Normalize lake into bronze/silver/gold with schema versions and manifests.
3. Add DuckDB warehouse views/marts over gold parquet.
4. Move stock/market APIs to DuckDB or gold parquet serving.
5. Remove market cache tables from MySQL; keep MySQL for user/app data only.

This keeps the short-term change small while preserving a clean path toward a
proper data warehouse boundary.

## Verification Plan

- Compile backend and ETL:

  ```powershell
  .\.venv\Scripts\python.exe -m compileall etl backend_v2\src
  ```

- Smoke import backend app and confirm startup does not register fetch/scheduler
  work.
- Verify read APIs do not call upstream market providers.
- Verify `refresh=true` on read endpoints returns
  `REFRESH_DISABLED_IN_SNAPSHOT_MODE`.
- Verify missing data returns `SNAPSHOT_NOT_BUILT` or `NO_DATA_IN_SNAPSHOT`.
- Verify ETL status exposes `ETL_RUNNING`, `ETL_FAILED`, and `STALE_SNAPSHOT`
  when applicable.
- Run frontend checks:

  ```powershell
  npm.cmd run type-check
  npm.cmd run build-only
  ```
