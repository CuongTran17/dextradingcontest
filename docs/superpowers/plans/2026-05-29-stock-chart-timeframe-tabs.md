# Stock Chart Timeframe Tabs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add minute, hourly, and daily grouped chart controls to the stock detail chart.

**Architecture:** Keep chart rendering in `TradingViewChart.vue`. `StockDetail.vue` owns timeframe group state and decides whether to call intraday or daily history. The backend intraday endpoint remains the aggregation boundary and accepts larger interval windows.

**Tech Stack:** Vue 3, TypeScript, FastAPI, unittest/TestClient.

---

### Task 1: Backend Intraday Interval Limit

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write the failing test**

Add this test to `StockReadApiSnapshotModeTests`:

```python
def test_intraday_accepts_four_hour_interval(self) -> None:
    response = self.client.get("/api/stocks/FPT/intraday?limit=10&interval_minutes=240")

    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertEqual(payload["symbol"], "FPT")
    self.assertEqual(payload["interval_minutes"], 240)
    self.assertIn("data", payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend_v2 && ..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_intraday_accepts_four_hour_interval -v`

Expected: FAIL or HTTP 422 because `interval_minutes` rejects `240`.

- [ ] **Step 3: Increase the endpoint limit**

Change the `interval_minutes` query limit in `backend_v2/src/routes/stocks.py`:

```python
interval_minutes: int = Query(default=1, ge=1, le=240),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend_v2 && ..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_intraday_accepts_four_hour_interval -v`

Expected: PASS.

### Task 2: Frontend API Interval Parameter

**Files:**
- Modify: `src/services/stockBackendApi.ts`

- [ ] **Step 1: Extend the API method signature**

Update `getIntraday()` to accept `intervalMinutes`.

```ts
async getIntraday(
  symbol: string,
  limit: number = 320,
  refresh: boolean = false,
  force: boolean = false,
  intervalMinutes: number = 1,
): Promise<IntradayResponse> {
  void refresh
  void force
  const query = this.buildQuery({
    limit,
    interval_minutes: intervalMinutes,
  })

  return this.fetch<IntradayResponse>(`/api/stocks/${symbol.toUpperCase()}/intraday${query}`)
}
```

- [ ] **Step 2: Run type-check**

Run: `npm.cmd run type-check`

Expected: PASS.

### Task 3: Grouped Stock Chart Controls

**Files:**
- Modify: `src/views/StockDetail.vue`

- [ ] **Step 1: Replace flat timeframe definitions**

Replace the flat `CHART_TIMEFRAMES` definition with grouped definitions that include `mode`, `intervalMinutes`, and `limit`.

- [ ] **Step 2: Update template controls**

Replace the single flat button loop in the `TradingViewChart` slot with:

- primary buttons for `Phút`, `Giờ`, `Ngày`
- secondary buttons for the selected group

- [ ] **Step 3: Route intraday vs daily loading**

Update `loadHistory()` so `1P`, `5P`, `15P`, `1G`, `4G`, and `1D` use `loadIntradayHistory()`, while `1T`, `3T`, `6T`, and `1N` use `loadDailyHistory()`. Keep `1D` daily fallback when intraday data is empty.

- [ ] **Step 4: Pass interval to `getIntraday()`**

Update `loadIntradayHistory()` to pass `selectedChartTimeframe.value.intervalMinutes`.

- [ ] **Step 5: Run type-check**

Run: `npm.cmd run type-check`

Expected: PASS.

### Task 4: Final Verification

**Files:**
- Verify only.

- [ ] **Step 1: Run backend targeted test**

Run: `cd backend_v2 && ..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_intraday_accepts_four_hour_interval -v`

Expected: PASS.

- [ ] **Step 2: Run frontend type-check**

Run: `npm.cmd run type-check`

Expected: PASS.
