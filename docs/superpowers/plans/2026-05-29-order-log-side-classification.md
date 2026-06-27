# Order Log Side Classification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show meaningful order-log side labels (`Mua`, `Bán`, `Không rõ`) instead of `manual`, using real DNSE side fields when available and conservative inference otherwise.

**Architecture:** Normalize side at the DNSE payload boundary first. If the source payload has no side, infer aggressor side from tick-to-tick price movement in the backend cache path, while preserving an explicit confidence/source field so the UI does not present inferred data as guaranteed truth.

**Tech Stack:** FastAPI backend, DNSE market data parser, in-memory/Redis tick cache, Vue OrderLog component, pytest/unittest.

---

## File Structure

- Modify `backend_v2/src/services/dnse_market_data.py`: parse side-like DNSE fields into canonical `match_type`.
- Modify `backend_v2/src/services/dnse_realtime_provider.py`: pass side metadata from DNSE tick to quote ingestion.
- Modify `backend_v2/src/services/vnstock_fetcher.py`: infer side when no source side exists and store side confidence/source on ticks.
- Modify `backend_v2/src/routes/stocks.py`: return normalized ticks with `match_type`, `side_source`, `side_confidence`.
- Modify `src/services/stockBackendApi.ts`: extend `OrderTick`.
- Modify `src/components/stock/OrderLog.vue`: display `Mua`, `Bán`, `Không rõ`, and visually distinguish inferred/unknown side.
- Extend `backend_v2/tests/test_dnse_market_data.py`: parsing real side fields.
- Extend `backend_v2/tests/test_snapshot_mode.py`: inferred side behavior.

---

## Task 1: Parse Source Side From DNSE Payload

**Files:**
- Modify: `backend_v2/src/services/dnse_market_data.py`
- Test: `backend_v2/tests/test_dnse_market_data.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
def test_normalize_latest_trade_maps_buy_side_fields():
    tick = normalize_latest_trade("FPT", {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21", "side": "B"})

    assert tick["match_type"] == "buy"
    assert tick["side_source"] == "dnse"
    assert tick["side_confidence"] == "source"


def test_normalize_latest_trade_maps_sell_side_fields():
    tick = normalize_latest_trade("FPT", {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21", "matchType": "S"})

    assert tick["match_type"] == "sell"
    assert tick["side_source"] == "dnse"
    assert tick["side_confidence"] == "source"


def test_normalize_latest_trade_marks_missing_side_unknown():
    tick = normalize_latest_trade("FPT", {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21"})

    assert tick["match_type"] == "unknown"
    assert tick["side_source"] == "missing"
    assert tick["side_confidence"] == "unknown"
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_market_data.py -q
```

Expected: FAIL because DNSE parser does not populate side metadata.

- [ ] **Step 3: Implement side normalization**

In `dnse_market_data.py`, add:

```python
def _normalize_side(raw: dict[str, Any]) -> tuple[str, str, str]:
    text = _first_text(raw, ("side", "matchType", "match_type", "tradeType", "bsType", "type"))
    value = (text or "").strip().lower()
    buy_values = {"b", "buy", "bu", "mua", "bid"}
    sell_values = {"s", "sell", "sd", "ban", "bán", "ask"}
    if value in buy_values:
        return "buy", "dnse", "source"
    if value in sell_values:
        return "sell", "dnse", "source"
    return "unknown", "missing", "unknown"
```

In `normalize_latest_trade()`, after resolving `trade`, call:

```python
match_type, side_source, side_confidence = _normalize_side(trade)
```

and return:

```python
"match_type": match_type,
"side_source": side_source,
"side_confidence": side_confidence,
```

- [ ] **Step 4: Verify tests pass**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_market_data.py -q
```

Expected: PASS.

---

## Task 2: Pass DNSE Side Metadata Into Tick Ingestion

**Files:**
- Modify: `backend_v2/src/services/dnse_realtime_provider.py`
- Test: `backend_v2/tests/test_dnse_realtime_provider.py`

- [ ] **Step 1: Write failing test**

Add or extend test:

```python
async def test_tick_to_quote_preserves_side_metadata():
    provider = DnseRealtimeProvider(market_client=FakeClient(), fetcher=FakeFetcher(), enabled=True)

    quote = provider._tick_to_quote(
        {
            "symbol": "FPT",
            "price": 74.5,
            "volume": 100,
            "trade_time_local": "2026-05-29T10:20:21+07:00",
            "match_type": "buy",
            "side_source": "dnse",
            "side_confidence": "source",
        }
    )

    assert quote["match_type"] == "buy"
    assert quote["side_source"] == "dnse"
    assert quote["side_confidence"] == "source"
```

- [ ] **Step 2: Run test and verify failure**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_realtime_provider.py -q
```

Expected: FAIL until metadata is copied.

- [ ] **Step 3: Implement pass-through**

In `_tick_to_quote()`, include:

```python
"match_type": tick.get("match_type") or "unknown",
"side_source": tick.get("side_source") or "missing",
"side_confidence": tick.get("side_confidence") or "unknown",
```

- [ ] **Step 4: Verify**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_realtime_provider.py -q
```

Expected: PASS.

---

## Task 3: Infer Side When Source Side Is Missing

**Files:**
- Modify: `backend_v2/src/services/vnstock_fetcher.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write failing tests**

Add tests:

```python
class OrderSideInferenceTests(unittest.TestCase):
    def test_infers_buy_when_price_moves_up(self):
        from src.services.vnstock_fetcher import _infer_match_type

        match_type, source, confidence = _infer_match_type(current_price=75.0, previous_price=74.5, source_match_type="unknown")

        self.assertEqual((match_type, source, confidence), ("buy", "price_tick", "inferred"))

    def test_infers_sell_when_price_moves_down(self):
        from src.services.vnstock_fetcher import _infer_match_type

        match_type, source, confidence = _infer_match_type(current_price=74.0, previous_price=74.5, source_match_type="unknown")

        self.assertEqual((match_type, source, confidence), ("sell", "price_tick", "inferred"))

    def test_keeps_unknown_when_price_is_unchanged(self):
        from src.services.vnstock_fetcher import _infer_match_type

        match_type, source, confidence = _infer_match_type(current_price=74.5, previous_price=74.5, source_match_type="unknown")

        self.assertEqual((match_type, source, confidence), ("unknown", "price_tick", "unknown"))
```

- [ ] **Step 2: Run tests and verify failure**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.OrderSideInferenceTests -v
```

Expected: FAIL because `_infer_match_type` does not exist.

- [ ] **Step 3: Implement helper**

In `vnstock_fetcher.py`, add:

```python
def _canonical_match_type(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"buy", "b", "mua"}:
        return "buy"
    if normalized in {"sell", "s", "ban", "bán"}:
        return "sell"
    if normalized in {"ato", "atc", "lo"}:
        return normalized
    return "unknown"


def _infer_match_type(current_price: float, previous_price: float | None, source_match_type: Any) -> tuple[str, str, str]:
    canonical = _canonical_match_type(source_match_type)
    if canonical in {"buy", "sell", "ato", "atc", "lo"}:
        return canonical, "dnse", "source"
    if previous_price is None or previous_price <= 0:
        return "unknown", "price_tick", "unknown"
    if current_price > previous_price:
        return "buy", "price_tick", "inferred"
    if current_price < previous_price:
        return "sell", "price_tick", "inferred"
    return "unknown", "price_tick", "unknown"
```

- [ ] **Step 4: Use helper in `ingest_realtime_quotes()`**

Before creating the tick, compute previous price from existing in-memory/Redis tick cache or current snapshot:

```python
previous_price = _to_float(snapshot.get("price")) if snapshot else None
match_type, side_source, side_confidence = _infer_match_type(price, previous_price, quote.get("match_type"))
```

Then tick should include:

```python
"match_type": match_type,
"side_source": quote.get("side_source") if side_confidence == "source" else side_source,
"side_confidence": quote.get("side_confidence") if side_confidence == "source" else side_confidence,
```

If quote source says `missing`, inferred result should use `price_tick`.

- [ ] **Step 5: Verify tests**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.OrderSideInferenceTests -v
```

Expected: PASS.

---

## Task 4: Return Side Metadata From `/ticks`

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_snapshot_mode.py`

- [ ] **Step 1: Write failing test**

Add:

```python
async def test_ticks_response_preserves_side_metadata(self):
    from src.routes import stocks

    class Fetcher:
        def is_intraday_fetch_window(self):
            return True

        def get_intraday_cache_view(self, symbols, limit):
            return {
                "FPT": [
                    {
                        "id": "1",
                        "symbol": "FPT",
                        "time": "2026-05-29T10:20:21+07:00",
                        "price": 74.5,
                        "volume": 100,
                        "match_type": "buy",
                        "side_source": "price_tick",
                        "side_confidence": "inferred",
                    }
                ]
            }

    async def fake_refresh(symbols):
        return {"status": "cached"}

    original_fetcher = stocks.fetcher_service
    original_refresh = stocks._refresh_dnse_realtime
    stocks.fetcher_service = Fetcher()
    stocks._refresh_dnse_realtime = fake_refresh
    try:
        response = await stocks.get_ticks("FPT", limit=10)
    finally:
        stocks.fetcher_service = original_fetcher
        stocks._refresh_dnse_realtime = original_refresh

    tick = response["ticks"][0]
    self.assertEqual(tick["match_type"], "buy")
    self.assertEqual(tick["side_source"], "price_tick")
    self.assertEqual(tick["side_confidence"], "inferred")
```

- [ ] **Step 2: Run test**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode.StockReadApiSnapshotModeTests.test_ticks_response_preserves_side_metadata -v
```

Expected: PASS if route already returns all tick fields; otherwise fail and normalize response shape.

- [ ] **Step 3: Implement response normalization if needed**

In `get_ticks()`, map each tick:

```python
{
    **tick,
    "match_type": tick.get("match_type") or "unknown",
    "side_source": tick.get("side_source") or "missing",
    "side_confidence": tick.get("side_confidence") or "unknown",
}
```

- [ ] **Step 4: Verify**

Run the test again. Expected: PASS.

---

## Task 5: Update Frontend Types And UI Labels

**Files:**
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/components/stock/OrderLog.vue`

- [ ] **Step 1: Extend `OrderTick` type**

In `src/services/stockBackendApi.ts`:

```ts
export interface OrderTick {
  id: string
  symbol: string
  time: string
  price: number
  volume: number
  match_type: string
  side_source?: 'dnse' | 'price_tick' | 'missing' | string
  side_confidence?: 'source' | 'inferred' | 'unknown' | string
}
```

- [ ] **Step 2: Update local interface**

In `OrderLog.vue`, add matching optional fields:

```ts
side_source?: string
side_confidence?: string
```

- [ ] **Step 3: Update labels**

In `sideLabel()`:

```ts
if (mt === 'buy') return 'Mua'
if (mt === 'sell') return 'Bán'
if (mt === 'unknown' || mt === 'manual') return '?'
```

Add tooltip/title to badge:

```vue
:title="sideTitle(tick)"
```

Implement:

```ts
function sideTitle(tick: OrderTick): string {
  if (tick.side_confidence === 'source') return 'Phân loại từ DNSE'
  if (tick.side_confidence === 'inferred') return 'Suy luận theo biến động giá tick trước'
  return 'Nguồn không cung cấp chiều mua/bán'
}
```

- [ ] **Step 4: Update badge color**

Keep buy green, sell red, unknown gray. If inferred, use softer opacity:

```ts
if (matchType === 'buy' && confidence === 'inferred') return 'bg-success-50 text-success-700 ...'
if (matchType === 'sell' && confidence === 'inferred') return 'bg-error-50 text-error-700 ...'
```

- [ ] **Step 5: Verify type-check**

```powershell
npm.cmd run type-check
```

Expected: PASS. If sandbox blocks `node_modules/.tmp`, rerun with approved escalation.

---

## Task 6: Final Verification

- [ ] **Step 1: Backend tests**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -m pytest tests/test_dnse_market_data.py tests/test_dnse_realtime_provider.py -q
..\.venv\Scripts\python.exe -m unittest tests.test_snapshot_mode -v
..\.venv\Scripts\python.exe -m compileall src
```

Expected: PASS.

- [ ] **Step 2: API smoke**

```powershell
cd backend_v2
..\.venv\Scripts\python.exe -c "from fastapi.testclient import TestClient; from src.main import app; c=TestClient(app, raise_server_exceptions=False); r=c.get('/api/stocks/FPT/ticks?limit=5'); print(r.status_code); print(r.json().get('ticks', [])[:1])"
```

Expected: first tick contains `match_type`, `side_source`, and `side_confidence`.

- [ ] **Step 3: Manual UI smoke**

Start backend and Vite, open `/stocks/FPT`, verify:

- Source side `buy` displays `Mua`.
- Source side `sell` displays `Bán`.
- Inferred side displays `Mua`/`Bán` with softer badge and tooltip.
- Missing/flat side displays `?` or `Không rõ`, not `manual`.

---

## Notes

This feature should not claim perfect buy/sell classification unless DNSE provides source-side data. Tick-rule inference is useful for visual context, but it is not equivalent to exchange-level aggressor side.

