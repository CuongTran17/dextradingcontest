# Market Price Source Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop showing `0,00` as a real stock price by selecting a reliable best-available price source and synchronizing that contract across dashboard, detail, market, portfolio, screener, AI, and chart-adjacent views.

**Architecture:** Backend stock snapshots become the single contract for current price. The backend ranks sources as DNSE live/cache first, EOD DuckDB history second, then explicit no-data metadata; frontend renders placeholders for no-data instead of formatting zero as a price. Historical charts continue to use `/history` and `/technical`; they are not mutated with intraday ticks in this phase.

**Tech Stack:** FastAPI, Python unittest/pytest, Vue 3 Composition API, TypeScript, existing `useStockData` composable, existing FastAPI stock routes and DNSE realtime provider.

---

## File Structure

- Modify `backend_v2/src/services/vnstock_fetcher.py`: annotate snapshots with `priceSource` and `dataStatus`; classify cached DNSE/in-memory snapshots versus EOD DuckDB fallback versus no data.
- Modify `backend_v2/src/routes/stocks.py`: set batch `data_status` based on usable positive-price snapshots, not merely a non-empty list.
- Modify `backend_v2/tests/test_snapshot_mode.py`: add backend regression coverage for no-data snapshots and EOD fallback metadata.
- Modify `src/services/stockBackendApi.ts`: extend `StockSnapshot` with optional `priceSource` and `dataStatus`.
- Modify `src/composables/useStockData.ts`: preserve snapshot metadata in shared stock state and avoid treating zero-price snapshots as usable market data.
- Modify `src/views/StockDetail.vue`: render `--` for no current price while keeping charts independent.
- Modify `src/views/StockDashboard.vue`, `src/views/MarketOverview.vue`, `src/views/MyPortfolio.vue`, `src/views/StockScreener.vue`, and `src/views/StockAIAnalysis.vue`: use snapshot metadata/positive-price checks consistently.

## Task 1: Backend Snapshot Source Metadata

**Files:**
- Modify: `backend_v2/src/services/vnstock_fetcher.py`
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Add failing tests for snapshot source selection**

Append these tests to `StockReadApiSnapshotModeTests` in `backend_v2/tests/test_snapshot_mode.py`:

```python
    async def test_snapshot_uses_eod_history_when_cached_price_is_empty(self):
        from src.services import vnstock_fetcher

        class HistoryMarketRepo:
            def load_history(self, symbol, start_date=None, end_date=None, limit=365):
                return [
                    {"time": "2026-05-24", "open": 38, "high": 39, "low": 37, "close": 38.5, "volume": 1000},
                    {"time": "2026-05-25", "open": 39, "high": 40, "low": 38, "close": 39.5, "volume": 2000},
                ]

        original_repo = vnstock_fetcher.market_repo
        vnstock_fetcher.market_repo = HistoryMarketRepo()
        try:
            snapshot = vnstock_fetcher.fetcher_service.get_snapshot("FPT")
        finally:
            vnstock_fetcher.market_repo = original_repo

        self.assertEqual(snapshot["price"], 39.5)
        self.assertEqual(snapshot["priceSource"], "eod_snapshot")
        self.assertEqual(snapshot["dataStatus"], "DATA_AVAILABLE")

    async def test_snapshot_marks_no_data_when_no_price_source_exists(self):
        from src.services import vnstock_fetcher

        class EmptyMarketRepo:
            def load_history(self, symbol, start_date=None, end_date=None, limit=365):
                return []

        original_repo = vnstock_fetcher.market_repo
        vnstock_fetcher.market_repo = EmptyMarketRepo()
        try:
            snapshot = vnstock_fetcher.fetcher_service.get_snapshot("PLX")
        finally:
            vnstock_fetcher.market_repo = original_repo

        self.assertEqual(snapshot["price"], 0.0)
        self.assertEqual(snapshot["priceSource"], "no_data")
        self.assertEqual(snapshot["dataStatus"], "NO_DATA_IN_SNAPSHOT")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests -v
```

Expected: FAIL or ERROR because `priceSource` and `dataStatus` are not present.

- [ ] **Step 3: Implement minimal backend metadata**

In `backend_v2/src/services/vnstock_fetcher.py`, update `_empty_snapshot()` to include:

```python
        "priceSource": "no_data",
        "dataStatus": "NO_DATA_IN_SNAPSHOT",
```

In `ingest_realtime_quotes()`, after setting `snapshot["syncedAt"]`, set:

```python
                snapshot["priceSource"] = "dnse_live"
                snapshot["dataStatus"] = "DATA_AVAILABLE"
```

In `_update_snapshot_from_ticks_no_lock()`, add to `new_snap`:

```python
            "priceSource": "dnse_live",
            "dataStatus": "DATA_AVAILABLE",
```

In `get_snapshot()`, when cached snapshot has positive price before history fallback, set:

```python
            snapshot["priceSource"] = snapshot.get("priceSource") or "dnse_last_tick"
            snapshot["dataStatus"] = "DATA_AVAILABLE"
```

When history fallback updates snapshot, add:

```python
                        "priceSource": "eod_snapshot",
                        "dataStatus": "DATA_AVAILABLE",
```

Before returning, if price is still not positive, force:

```python
        if _to_float(snapshot.get("price")) <= 0:
            snapshot["priceSource"] = "no_data"
            snapshot["dataStatus"] = "NO_DATA_IN_SNAPSHOT"
```

In `backend_v2/src/routes/stocks.py`, update batch status:

```python
    has_usable_snapshot = any(_to_float(item.get("price")) > 0 for item in snapshots)
```

and return:

```python
        "data_status": DATA_AVAILABLE if has_usable_snapshot else NO_DATA_IN_SNAPSHOT,
```

- [ ] **Step 4: Run backend tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
```

Expected: all tests pass.

## Task 2: Frontend Snapshot Metadata Contract

**Files:**
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/composables/useStockData.ts`

- [ ] **Step 1: Add frontend metadata types**

In `src/services/stockBackendApi.ts`, extend `StockSnapshot`:

```ts
  priceSource?: 'dnse_live' | 'dnse_last_tick' | 'eod_snapshot' | 'no_data' | string
  dataStatus?: 'DATA_AVAILABLE' | 'NO_DATA_IN_SNAPSHOT' | string
```

In `src/composables/useStockData.ts`, extend `StockState` with:

```ts
  priceSource: string
  dataStatus: string
```

- [ ] **Step 2: Preserve metadata through state conversion**

In `createEmptyState()`, add:

```ts
    priceSource: 'no_data',
    dataStatus: 'NO_DATA_IN_SNAPSHOT',
```

In `snapshotToState()`, add:

```ts
    priceSource: snapshot.priceSource || 'no_data',
    dataStatus: snapshot.dataStatus || (toNumber(snapshot.price) > 0 ? 'DATA_AVAILABLE' : 'NO_DATA_IN_SNAPSHOT'),
```

In history fallback state construction, add:

```ts
      priceSource: 'eod_snapshot',
      dataStatus: latestClose > 0 ? 'DATA_AVAILABLE' : 'NO_DATA_IN_SNAPSHOT',
```

In `quoteToState()` and `updateFromRealtime()`, add:

```ts
      priceSource: 'dnse_live',
      dataStatus: 'DATA_AVAILABLE',
```

- [ ] **Step 3: Type-check frontend**

Run:

```powershell
npm.cmd run type-check
```

Expected: TypeScript passes.

## Task 3: Stock Detail No-Data Rendering

**Files:**
- Modify: `src/views/StockDetail.vue`

- [ ] **Step 1: Add display helpers**

Add computed helpers:

```ts
const hasCurrentPrice = computed(() => Boolean(selectedStock.value && selectedStock.value.price > 0 && selectedStock.value.dataStatus !== 'NO_DATA_IN_SNAPSHOT'))
const currentPriceDisplay = computed(() => hasCurrentPrice.value ? formatPriceWithDecimals(selectedStock.value?.price || 0) : '--')
const currentChangeDisplay = computed(() => {
  if (!hasCurrentPrice.value) return '--'
  const stock = selectedStock.value
  return `${formatSignedChange(stock?.change || 0)} / ${(stock?.changePercent || 0) >= 0 ? '+' : ''}${(stock?.changePercent || 0).toFixed(2)}%`
})
```

- [ ] **Step 2: Use helpers in the price card**

Replace the price expression with:

```vue
{{ currentPriceDisplay }}
```

Replace the change expression with:

```vue
Biến động: {{ currentChangeDisplay }}
```

- [ ] **Step 3: Type-check frontend**

Run:

```powershell
npm.cmd run type-check
```

Expected: TypeScript passes.

## Task 4: Dashboard and Market Views Use Usable Snapshots Only

**Files:**
- Modify: `src/views/StockDashboard.vue`
- Modify: `src/views/MarketOverview.vue`
- Modify: `src/views/MyPortfolio.vue`
- Modify: `src/views/StockScreener.vue`
- Modify: `src/views/StockAIAnalysis.vue`

- [ ] **Step 1: Use a shared local usable-price check in each touched view**

Add this helper where each view filters or displays snapshot prices:

```ts
function hasUsableSnapshotPrice(item: { price?: number; dataStatus?: string } | null | undefined): boolean {
  return Boolean(item && Number(item.price) > 0 && item.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}
```

- [ ] **Step 2: Replace `price > 0` snapshot filters**

Examples:

```ts
.filter((s) => hasUsableSnapshotPrice(s) && s.changePercent >= 0)
```

and:

```ts
const fromSnapshot = snapshot.value && hasUsableSnapshotPrice(snapshot.value)
  ? toNumber(snapshot.value.price)
  : Number.NaN
```

- [ ] **Step 3: Keep chart data on history endpoints**

Do not change `TradingViewChart`, `PortfolioChart`, or `TechnicalAnalysisChart` data inputs in this task. They remain backed by `/history` and `/technical`.

- [ ] **Step 4: Type-check frontend**

Run:

```powershell
npm.cmd run type-check
```

Expected: TypeScript passes.

## Task 5: End-to-End Verification

**Files:**
- No production changes.

- [ ] **Step 1: Compile backend**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m compileall src
```

Expected: command exits 0.

- [ ] **Step 2: Run backend tests**

Run:

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_market_data.py tests/test_dnse_realtime_provider.py tests/test_stocks_dnse_integration.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Build frontend types**

Run:

```powershell
npm.cmd run type-check
```

Expected: command exits 0.

- [ ] **Step 4: Manual smoke check**

Start backend and frontend, then verify:

```text
/api/stocks/snapshots?symbols=PLX returns priceSource and dataStatus.
Stock detail header shows -- instead of 0,00 when dataStatus is NO_DATA_IN_SNAPSHOT.
Dashboard top movers and Market Overview ignore no-data zero-price snapshots.
TradingView and technical charts continue to use historical data only.
```

## Self-Review

- Spec coverage: The plan covers backend source priority, frontend no-zero rendering, dashboard/market synchronization, and chart boundaries.
- Placeholder scan: No placeholder steps remain; each task names files and concrete changes.
- Type consistency: Backend uses `priceSource`/`dataStatus`; frontend optional types match those exact property names.
