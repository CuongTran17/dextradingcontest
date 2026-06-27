# DNSE Last-Known Ticks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep DNSE ticks visible outside market hours by returning the latest saved tick for each requested symbol, while clearly marking the data as stale rather than realtime.

**Architecture:** Reuse the existing intraday Redis/in-memory cache as the primary same-day tick store and the existing per-day Parquet files as durable fallback. Add a focused last-known tick reader that resolves each symbol from cache first and then searches recent Data Lake tick files. The DNSE sandbox endpoint returns saved ticks when polling is blocked, and the frontend displays them with a stale-data notice and their actual trade timestamps.

**Tech Stack:** FastAPI, Python, Redis optional cache, pandas/pyarrow Parquet, Vue 3 Composition API, TypeScript, pytest, Vitest.

---

## Scope

### In scope

- Continue storing all ingested intraday ticks in the existing Redis/in-memory cache.
- Persist intraday ticks through the existing per-day Parquet Data Lake path with a throttled flush, so fallback files are actually refreshed during the session.
- Read the latest saved tick for each requested symbol from:
  1. Redis/in-memory intraday cache.
  2. Recent Parquet tick files when cache has no data.
- Return last-known ticks from `/api/dnse/ticks/latest` outside market hours without calling DNSE.
- Mark fallback data as stale and expose its source.
- Display stale ticks, chart points, actual trade time, and a visible market-closed warning in `DnseTickSandbox.vue`.
- Preserve the current reduced heartbeat outside market hours.

### Out of scope

- Building a new tick database or DuckDB tick table.
- Backfilling historical ticks that were never captured.
- Showing full historical intraday sessions in the sandbox chart.
- Changing the centralized stock-price realtime manager.
- Treating saved ticks as realtime quotes after the market closes.
- Polling DNSE outside market hours unless `DNSE_REALTIME_POLL_WHEN_CLOSED=true`.

---

## API Contract

During market hours, the current response remains realtime:

```json
{
  "status": "ok",
  "source": "dnse",
  "data_source": "dnse_live",
  "is_stale": false,
  "ticks": []
}
```

Outside market hours, the endpoint does not call DNSE and returns saved ticks:

```json
{
  "status": "market_closed",
  "source": "dnse",
  "data_source": "cached_last_tick",
  "is_stale": true,
  "symbols": ["FPT", "VCB"],
  "ticks": [
    {
      "symbol": "FPT",
      "price": 123400,
      "volume": 100,
      "trade_time": "2026-06-04T07:45:00+00:00",
      "trade_time_local": "2026-06-04T14:45:00+07:00",
      "source": "dnse",
      "storage_source": "cache"
    }
  ],
  "missing_symbols": ["VCB"],
  "errors": {
    "market_session": "Outside market hours"
  }
}
```

Contract rules:

- `status` remains `market_closed` outside the session even when saved ticks exist.
- `is_stale=true` means the ticks must not be presented as live.
- `data_source=dnse_live` means the request polled DNSE.
- `data_source=cached_last_tick` means at least one tick came from saved data.
- `missing_symbols` lists requested symbols without any saved tick.
- Every saved tick includes `storage_source: cache | parquet`. Cache intentionally abstracts whether Redis or the in-memory fallback served it.
- The original trade timestamp is preserved; request time must never replace trade time.

---

## Target Data Flow

```text
During market hours
  DNSE latest trade
    -> DnseRealtimeProvider
    -> fetcher_service.ingest_realtime_quotes()
    -> intraday:{symbol} in Redis or in-memory fallback
    -> throttled flush to data_lake/ticks/YYYY-MM-DD/{symbol}.parquet

Outside market hours
  GET /api/dnse/ticks/latest
    -> do not call DNSE
    -> LastKnownTickReader
         -> intraday cache latest tick
         -> fallback recent data_lake/ticks/YYYY-MM-DD/{symbol}.parquet
    -> response status=market_closed, is_stale=true
    -> sandbox displays saved ticks and stale warning
```

---

## File Structure

### New files

- `backend_v2/src/services/last_known_tick_reader.py`
  - Resolves latest saved tick per symbol from cache and recent Parquet files.
- `backend_v2/tests/test_last_known_tick_reader.py`
  - Unit tests cache priority, Parquet fallback, normalization, and missing symbols.
- `src/services/__tests__/dnseTickSandboxApi.test.ts`
  - Type/contract-level frontend test for stale DNSE tick responses if an API service test pattern is practical.

### Modified files

- `backend_v2/src/database/data_lake.py`
  - Add atomic write and latest-tick read helpers; make tick-file location injectable for tests.
- `backend_v2/src/services/vnstock_fetcher.py`
  - Flush affected intraday symbol lists to Parquet at a bounded interval.
- `backend_v2/src/settings.py`
  - Add the bounded Parquet flush interval setting.
- `backend_v2/tests/test_vnstock_fetcher_tick_persistence.py`
  - Cover throttled intraday Parquet persistence.
- `backend_v2/src/routes/dnse_ticks.py`
  - Return last-known ticks outside market hours and enrich live response metadata.
- `backend_v2/tests/test_dnse_ticks.py`
  - Cover outside-hours cache fallback, no DNSE call, missing symbols, and live metadata.
- `src/services/dnseTickSandboxApi.ts`
  - Add stale response metadata and storage-source types.
- `src/views/DnseTickSandbox.vue`
  - Display saved ticks outside hours and show an amber stale-data notice instead of a red error.
- `README.md`
  - Document last-known tick behavior and storage limitations.

---

### Task 1: Guarantee Durable Intraday Tick Files and Add the Data Lake Reader

**Files:**
- Modify: `backend_v2/src/database/data_lake.py`
- Modify: `backend_v2/src/services/vnstock_fetcher.py`
- Modify: `backend_v2/src/settings.py`
- Test: `backend_v2/tests/test_last_known_tick_reader.py`
- Test: `backend_v2/tests/test_vnstock_fetcher_tick_persistence.py`

- [ ] **Step 1: Write failing tests for reading the newest Parquet tick**

Create tests using `tmp_path` that write two dated tick files for `FPT`, then assert the reader returns the newest trade by tick timestamp rather than filesystem order.

```python
def test_read_latest_tick_from_parquet_returns_newest_trade(tmp_path):
    write_tick_file(tmp_path, "2026-06-03", "FPT", old_rows)
    write_tick_file(tmp_path, "2026-06-04", "FPT", new_rows)

    result = read_latest_tick_from_parquet("FPT", base_dir=tmp_path)

    assert result["symbol"] == "FPT"
    assert result["price"] == 123_400
    assert result["storage_source"] == "parquet"
```

- [ ] **Step 2: Write failing tests for missing and malformed files**

Assert the helper returns `None` when no file exists and skips unreadable/empty files without crashing the request.

```python
def test_read_latest_tick_from_parquet_returns_none_when_missing(tmp_path):
    assert read_latest_tick_from_parquet("VCB", base_dir=tmp_path) is None
```

- [ ] **Step 3: Write failing tests for throttled Parquet persistence**

Inject a fake Parquet writer and monotonic clock into the fetcher. Assert the first ingested quote flushes the affected symbol, a second quote inside the interval does not flush again, and a later quote does.

```python
@pytest.mark.anyio
async def test_ingest_realtime_quotes_flushes_intraday_ticks_at_bounded_interval():
    fetcher = build_fetcher(parquet_flush_seconds=30, clock=FakeClock([0, 10, 31]))

    await fetcher.ingest_realtime_quotes([quote("FPT", 100)])
    await fetcher.ingest_realtime_quotes([quote("FPT", 101)])
    await fetcher.ingest_realtime_quotes([quote("FPT", 102)])

    assert fetcher.parquet_writer.calls == [("FPT", 1), ("FPT", 3)]
```

- [ ] **Step 4: Run the focused tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_last_known_tick_reader.py backend_v2/tests/test_vnstock_fetcher_tick_persistence.py -q
```

Expected: FAIL because the reader and bounded persistence behavior do not exist.

- [ ] **Step 5: Make Parquet writes atomic**

Update `dump_ticks_to_parquet()` to accept an injectable `base_dir`, write to a temporary sibling file, then replace the final file. This prevents the fallback reader from observing a partially written Parquet file.

```python
temp_path = file_path.with_suffix(".tmp.parquet")
df.to_parquet(temp_path, engine="pyarrow", index=False)
temp_path.replace(file_path)
```

- [ ] **Step 6: Implement the minimal Parquet reader**

Add a helper that searches newest date directories first, reads only matching symbol files, normalizes the latest row, and tags it with `storage_source="parquet"`.

```python
def read_latest_tick_from_parquet(
    symbol: str,
    *,
    base_dir: Path = DATA_LAKE_DIR,
    max_days: int = 10,
) -> dict | None:
    normalized = symbol.strip().upper()
    date_dirs = sorted(
        (path for path in base_dir.iterdir() if path.is_dir()),
        reverse=True,
    )[:max_days]
    for date_dir in date_dirs:
        file_path = date_dir / f"{normalized}.parquet"
        if not file_path.exists():
            continue
        try:
            frame = pd.read_parquet(file_path)
        except Exception:
            logger.exception("Failed to read tick parquet: %s", file_path)
            continue
        if frame.empty:
            continue
        row = frame.sort_values("time").iloc[-1].to_dict()
        row["symbol"] = normalized
        row["storage_source"] = "parquet"
        return row
    return None
```

- [ ] **Step 7: Add bounded intraday persistence**

Add the setting:

```python
dnse_tick_parquet_flush_seconds: float = Field(default=30.0, ge=1.0, le=300.0)
```

In `VnstockFetcherService`, track the last flush monotonic time per symbol. After quotes are merged, flush only affected symbols whose interval has elapsed. Snapshot the list under the cache lock, then perform Parquet I/O outside the lock so disk writes do not block realtime cache updates.

The flush should overwrite the symbol's current-day Parquet file atomically with the full bounded intraday list. With Redis unavailable, this limits potential tick loss after restart to the configured flush interval.

- [ ] **Step 8: Run the focused tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_last_known_tick_reader.py backend_v2/tests/test_vnstock_fetcher_tick_persistence.py -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```powershell
git add backend_v2/src/database/data_lake.py backend_v2/src/services/vnstock_fetcher.py backend_v2/src/settings.py backend_v2/tests/test_last_known_tick_reader.py backend_v2/tests/test_vnstock_fetcher_tick_persistence.py
git commit -m "feat: persist and read latest saved DNSE ticks"
```

---

### Task 2: Add Cache-First Last-Known Tick Reader

**Files:**
- Create: `backend_v2/src/services/last_known_tick_reader.py`
- Modify: `backend_v2/tests/test_last_known_tick_reader.py`

- [ ] **Step 1: Write failing tests for cache priority**

Use a fake fetcher whose `get_intraday_cache_view()` returns newest-first ticks. Assert cache data wins over Parquet and only one latest tick is returned per symbol.

```python
def test_reader_prefers_intraday_cache_over_parquet(monkeypatch):
    reader = LastKnownTickReader(fetcher=FakeFetcherWithFptTick())
    monkeypatch.setattr(reader, "_read_parquet", lambda symbol: {"symbol": symbol, "price": 90})

    result = reader.read(["FPT"])

    assert result.ticks[0]["price"] == 100
    assert result.ticks[0]["storage_source"] == "cache"
```

- [ ] **Step 2: Write failing tests for mixed fallback**

Assert a request for `FPT,VCB,VIC` can return FPT from cache, VCB from Parquet, and report VIC in `missing_symbols`.

```python
def test_reader_combines_cache_and_parquet_and_reports_missing():
    result = reader.read(["FPT", "VCB", "VIC"])

    assert [tick["symbol"] for tick in result.ticks] == ["FPT", "VCB"]
    assert result.missing_symbols == ["VIC"]
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_last_known_tick_reader.py -q
```

Expected: FAIL because `LastKnownTickReader` does not exist.

- [ ] **Step 4: Implement the focused reader**

Create a reader with injected fetcher and Parquet function. It must normalize cache ticks into the DNSE sandbox shape without changing their actual timestamps.

```python
@dataclass
class LastKnownTickResult:
    ticks: list[dict[str, Any]]
    missing_symbols: list[str]


class LastKnownTickReader:
    def __init__(self, *, fetcher=fetcher_service, parquet_reader=read_latest_tick_from_parquet):
        self.fetcher = fetcher
        self.parquet_reader = parquet_reader

    def read(self, symbols: list[str]) -> LastKnownTickResult:
        cache = self.fetcher.get_intraday_cache_view(symbols=symbols, limit=1)
        ticks: list[dict[str, Any]] = []
        missing: list[str] = []
        for symbol in symbols:
            cached = (cache.get(symbol) or [None])[0]
            tick = self._normalize(cached, symbol, "cache") if cached else None
            if tick is None:
                parquet = self.parquet_reader(symbol)
                tick = self._normalize(parquet, symbol, "parquet") if parquet else None
            if tick is None:
                missing.append(symbol)
            else:
                ticks.append(tick)
        return LastKnownTickResult(ticks=ticks, missing_symbols=missing)
```

Normalization requirements:

- Map cache `time` to both `trade_time` and `trade_time_local` consistently.
- Preserve `price`, `volume`, `match_type`, `side_source`, and `side_confidence`.
- Return `source="dnse"` and `storage_source`.
- Do not include a large raw DNSE payload in fallback responses.

- [ ] **Step 5: Run tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_last_known_tick_reader.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2/src/services/last_known_tick_reader.py backend_v2/tests/test_last_known_tick_reader.py
git commit -m "feat: resolve last-known DNSE ticks from cache and parquet"
```

---

### Task 3: Return Saved Ticks Outside Market Hours

**Files:**
- Modify: `backend_v2/src/routes/dnse_ticks.py`
- Modify: `backend_v2/src/services/dnse_realtime_provider.py`
- Modify: `backend_v2/tests/test_dnse_ticks.py`

- [ ] **Step 1: Replace the existing closed-market expectation with a failing fallback test**

Inject a fake last-known reader and assert DNSE is never polled.

```python
def test_dnse_latest_route_returns_saved_ticks_when_market_closed(monkeypatch):
    fake_client = FakeConfiguredClient()
    monkeypatch.setattr(dnse_ticks, "get_dnse_market_client", lambda: fake_client)
    monkeypatch.setattr(dnse_ticks, "last_known_tick_reader", FakeLastKnownReader())
    monkeypatch.setattr(dnse_ticks, "get_current_market_session", closed_session)

    body = TestClient(app).get("/api/dnse/ticks/latest?symbols=FPT,VCB").json()

    assert fake_client.calls == []
    assert body["status"] == "market_closed"
    assert body["is_stale"] is True
    assert body["data_source"] == "cached_last_tick"
    assert body["ticks"][0]["symbol"] == "FPT"
    assert body["missing_symbols"] == ["VCB"]
```

- [ ] **Step 2: Add failing live-response metadata test**

Assert an allowed polling request returns `is_stale=false`, `data_source=dnse_live`, and `missing_symbols=[]`. Also inject a fake fetcher and assert the live ticks returned by the sandbox route are ingested, so they enter the same Redis/in-memory and Parquet persistence path as main-web realtime ticks.

- [ ] **Step 3: Run route tests and verify failure**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_ticks.py -q
```

Expected: FAIL because the closed route still returns `ticks: []` and metadata is absent.

- [ ] **Step 4: Implement the closed-market fallback response**

Inject a module-level `last_known_tick_reader`. In the closed-market guard, read saved ticks and return:

```python
saved = last_known_tick_reader.read(parsed)
return {
    "status": "market_closed",
    "source": "dnse",
    "data_source": "cached_last_tick",
    "is_stale": True,
    "symbols": parsed,
    "ticks": saved.ticks,
    "missing_symbols": saved.missing_symbols,
    "errors": {"market_session": market_session["reason"]},
    "latency_ms": 0,
    "market_session": market_session,
}
```

Promote `_tick_to_quote()` in `DnseRealtimeProvider` to a reusable public `tick_to_quote()` helper, preserving its existing behavior and tests. After the sandbox route polls DNSE, convert valid ticks and call `fetcher_service.ingest_realtime_quotes(quotes)` before returning the response. Duplicate ingestion remains safe because the existing tick merge key deduplicates repeated ticks.

Enrich configured live responses with:

```python
response["data_source"] = "dnse_live"
response["is_stale"] = False
response["missing_symbols"] = [
    symbol for symbol in parsed if symbol not in {tick["symbol"] for tick in response["ticks"]}
]
```

Keep the current `not_configured` behavior unchanged. Missing credentials must not expose unrelated cache data through this DNSE sandbox route.

- [ ] **Step 5: Run route and provider tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_ticks.py backend_v2/tests/test_dnse_realtime_provider.py backend_v2/tests/test_vnstock_fetcher_tick_persistence.py -q
```

Expected: PASS and no regression in DNSE ingestion.

- [ ] **Step 6: Commit**

```powershell
git add backend_v2/src/routes/dnse_ticks.py backend_v2/src/services/dnse_realtime_provider.py backend_v2/tests/test_dnse_ticks.py backend_v2/tests/test_dnse_realtime_provider.py
git commit -m "feat: persist and return DNSE sandbox ticks"
```

---

### Task 4: Display Stale Ticks Clearly in the Sandbox

**Files:**
- Modify: `src/services/dnseTickSandboxApi.ts`
- Modify: `src/views/DnseTickSandbox.vue`
- Create: `src/services/__tests__/dnseTickSandboxApi.test.ts`

- [ ] **Step 1: Add frontend contract types**

Extend the response and tick interfaces:

```typescript
export interface DnseTick {
  // existing fields
  storage_source?: 'cache' | 'parquet'
}

export interface DnseTickResponse {
  // existing fields
  data_source?: 'dnse_live' | 'cached_last_tick'
  is_stale?: boolean
  missing_symbols?: string[]
}
```

- [ ] **Step 2: Add a failing service contract test**

Mock `backendFetch` and assert `getLatestTicks()` accepts a `market_closed` response containing saved ticks, `is_stale=true`, and `missing_symbols`.

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/dnseTickSandboxApi.test.ts
```

Expected: FAIL until the response contract is represented correctly.

- [ ] **Step 3: Change the market-closed UI from error to stale notice**

Add a computed stale label using the newest returned trade timestamp:

```typescript
const staleNotice = computed(() => {
  if (!latestResponse.value?.is_stale || ticks.value.length === 0) return ''
  const latest = [...ticks.value].sort(
    (a, b) => Date.parse(b.trade_time_local || b.trade_time || '') - Date.parse(a.trade_time_local || a.trade_time || ''),
  )[0]
  return `Thị trường đã đóng cửa. Đang hiển thị tick gần nhất lúc ${formatTradeTime(latest)}.`
})
```

Render `staleNotice` in an amber information panel. Keep `errorMessage` for actual failures and missing configuration only.

- [ ] **Step 4: Improve empty and row states**

- When `market_closed` and no saved ticks exist, show: `Chưa có tick đã lưu cho các mã được chọn.`
- Add a `Source` column or compact badge showing `cache`/`parquet`.
- Keep the actual trade time visible.
- Continue updating the chart from returned saved ticks.
- Show missing symbols in the stale notice without treating the whole response as failed.

- [ ] **Step 5: Run frontend tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: all unit tests pass and production build succeeds.

- [ ] **Step 6: Verify manually in browser**

With backend market session mocked/known closed and saved ticks available:

1. Open `http://localhost:5174/dnse-ticks`.
2. Click `Refresh once`.
3. Confirm rows and chart display saved ticks.
4. Confirm amber stale notice includes the actual trade time.
5. Confirm market label remains `Market closed`.
6. Confirm no red error appears solely because the market is closed.
7. Confirm the polling interval uses the configured closed heartbeat.

- [ ] **Step 7: Commit**

```powershell
git add src/services/dnseTickSandboxApi.ts src/services/__tests__/dnseTickSandboxApi.test.ts src/views/DnseTickSandbox.vue
git commit -m "feat: display saved DNSE ticks outside market hours"
```

---

### Task 5: Document and Verify the Complete Behavior

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update README**

Document:

- Intraday ticks are kept in Redis or in-memory fallback.
- Intraday ticks are flushed atomically to Data Lake Parquet at `DNSE_TICK_PARQUET_FLUSH_SECONDS` intervals.
- Data Lake Parquet files provide durable last-tick fallback.
- Outside market hours, `/api/dnse/ticks/latest` returns saved ticks with `status=market_closed` and `is_stale=true`.
- In-memory-only mode can lose ticks received since the most recent Parquet flush after backend restart.
- `DNSE_REALTIME_POLL_WHEN_CLOSED=true` remains a testing override and is not required for last-known ticks.

- [ ] **Step 2: Run full backend tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 3: Run full frontend verification**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: all frontend tests pass and build succeeds.

- [ ] **Step 4: Check the final diff**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors; only intended files are changed.

- [ ] **Step 5: Commit**

```powershell
git add README.md
git commit -m "docs: explain DNSE last-known tick fallback"
```

---

## Acceptance Criteria

- Opening `/dnse-ticks` outside market hours displays the latest saved tick for every requested symbol that has saved data.
- The backend does not call DNSE outside market hours when `DNSE_REALTIME_POLL_WHEN_CLOSED=false`.
- Saved ticks preserve their original trade timestamps.
- The API and UI clearly distinguish stale saved data from realtime data.
- Missing symbols are reported without hiding available ticks.
- Cache data takes priority over Parquet fallback.
- Parquet fallback works after the intraday cache is unavailable.
- Existing realtime ingestion, centralized stock-price updates, backend tests, frontend tests, and frontend build remain passing.

## Risks and Guardrails

- **Stale data mistaken for realtime:** Keep `status=market_closed`, return `is_stale=true`, and show an amber UI notice.
- **Parquet read cost:** Search only a bounded number of newest date directories and only requested symbol files.
- **Parquet write cost:** Flush only affected symbols at a bounded interval and perform disk I/O outside the realtime cache lock.
- **Incomplete durability without Redis:** Clearly document that in-memory ticks received after the latest Parquet flush can be lost.
- **Malformed old Parquet:** Skip unreadable files, log the failure, and continue searching older dates.
- **Large raw payloads:** Do not return or persist DNSE `raw` payloads in the last-known fallback response.
- **Timestamp ambiguity:** Never substitute request time for trade time; normalize timestamps consistently to Vietnam local time for display.
