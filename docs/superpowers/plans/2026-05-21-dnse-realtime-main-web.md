# DNSE Realtime Main Web Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote DNSE latest-trade realtime ticks from the sandbox route into the main stock dashboard, detail, portfolio, and news pages through the existing backend snapshot/websocket pipeline.

**Architecture:** Keep DNSE credentials and OpenAPI calls backend-only. DNSE latest trades are normalized, converted from DNSE UTC-like timestamps to timezone-aware ISO strings, ingested into the existing `fetcher_service` intraday/snapshot cache, then exposed through existing `/api/stocks/snapshots`, `/api/stocks/{symbol}/ticks`, `/api/stocks/{symbol}/intraday`, and `/api/ws/dnse` paths already used by the main web app. The sandbox route remains available for diagnostics.

**Tech Stack:** FastAPI, `httpx.AsyncClient`, `asyncio`, Pydantic settings, Vue 3 Composition API, Vitest-compatible TypeScript utilities, pytest.

---

## File Structure

- Modify `backend_v2/src/services/dnse_market_data.py`
  - Add bounded concurrent fetching with a shared `httpx.AsyncClient`.
  - Normalize DNSE `time` as UTC, expose `trade_time` as UTC ISO and `trade_time_local` as Vietnam local ISO.
  - Preserve raw DNSE payload for diagnostics.

- Create `backend_v2/src/services/dnse_realtime_provider.py`
  - Backend-only bridge from DNSE latest trades into the existing `fetcher_service.ingest_realtime_quotes(...)`.
  - Provides a short TTL cache to avoid duplicate DNSE calls from snapshots and websocket loops.
  - Returns provider status metadata for routes.

- Modify `backend_v2/src/settings.py`
  - Add flags for main-web DNSE integration:
    - `dnse_realtime_enabled`
    - `dnse_realtime_cache_ttl_seconds`
    - `dnse_realtime_max_concurrency`

- Modify `backend_v2/.env.example`
  - Document the new settings.

- Modify `backend_v2/src/routes/stocks.py`
  - Before returning snapshots/ticks/intraday during market session, ask the DNSE provider to refresh requested symbols.
  - Response `source` should reflect DNSE-backed cache when refresh succeeds.

- Modify `backend_v2/src/routes/websocket.py`
  - Before sending subscribed snapshots, ask the DNSE provider to refresh subscribed symbols.
  - Keep existing websocket protocol so frontend does not need a breaking change.

- Modify `src/services/stockBackendApi.ts`
  - Add optional `source` fields to response interfaces if missing.

- Modify `src/composables/useStockData.ts`
  - Update comments and status handling so the main web path is “backend DNSE-backed snapshots/websocket,” not browser DNSE REST.
  - Keep fallback behavior but do not expose DNSE credentials or call OpenAPI directly.

- Modify `src/views/DnseTickSandbox.vue`
  - Display `trade_time_local` when present.
  - Keep raw JSON visible for comparison.

- Create tests:
  - `backend_v2/tests/test_dnse_market_data.py`
  - `backend_v2/tests/test_dnse_realtime_provider.py`
  - `backend_v2/tests/test_stocks_dnse_integration.py`

---

### Task 1: Normalize DNSE Time and Concurrent Batch Fetch

**Files:**
- Modify: `backend_v2/src/services/dnse_market_data.py`
- Test: `backend_v2/tests/test_dnse_market_data.py`

- [ ] **Step 1: Write failing tests for time normalization and batch concurrency**

Create `backend_v2/tests/test_dnse_market_data.py`:

```python
from __future__ import annotations

import asyncio
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from src.services.dnse_market_data import (
    DnseMarketDataClient,
    normalize_latest_trade,
)


def test_normalize_latest_trade_treats_dnse_naive_time_as_utc():
    tick = normalize_latest_trade(
        "FPT",
        {
            "trades": [
                {
                    "symbol": "FPT",
                    "matchPrice": 76.9,
                    "matchQtty": 40,
                    "time": "2026-05-21 07:29:58",
                }
            ]
        },
    )

    assert tick["trade_time"] == "2026-05-21T07:29:58+00:00"
    assert tick["trade_time_local"] == "2026-05-21T14:29:58+07:00"
    assert datetime.fromisoformat(tick["trade_time_local"]).tzinfo is not None
    assert tick["price"] == 76.9
    assert tick["volume"] == 40


@pytest.mark.asyncio
async def test_get_latest_trades_reuses_client_and_fetches_concurrently(monkeypatch):
    request_started_at: list[float] = []

    async def fake_get(self, url, headers=None):
        request_started_at.append(time.perf_counter())
        await asyncio.sleep(0.15)
        symbol = url.split("/price/")[1].split("/")[0]
        return httpx.Response(
            200,
            json={
                "trades": [
                    {
                        "symbol": symbol,
                        "matchPrice": 10,
                        "matchQtty": 1,
                        "time": "2026-05-21 07:29:58",
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = DnseMarketDataClient(
        api_key="key",
        api_secret="secret",
        base_url="https://openapi.dnse.test",
        board_id="G1",
        timeout_seconds=2,
        max_concurrency=5,
    )

    started = time.perf_counter()
    response = await client.get_latest_trades(["FPT", "VCB", "VIC", "HPG", "SSI"])
    elapsed = time.perf_counter() - started

    assert response["status"] == "ok"
    assert len(response["ticks"]) == 5
    assert response["errors"] == {}
    assert elapsed < 0.45
    assert max(request_started_at) - min(request_started_at) < 0.12
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_market_data.py -v
```

Expected: FAIL because `trade_time_local` and `max_concurrency` do not exist, and batch fetch is sequential.

- [ ] **Step 3: Implement time normalization and shared-client concurrent fetch**

In `backend_v2/src/services/dnse_market_data.py`, update imports:

```python
import asyncio
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
```

Add constants and helpers near `_first_text`:

```python
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _normalize_dnse_trade_time(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    raw = str(value).strip()
    if not raw:
        return None, None

    try:
        if raw.endswith("Z"):
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return raw, raw

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    utc_value = parsed.astimezone(timezone.utc).isoformat()
    local_value = parsed.astimezone(VN_TZ).isoformat()
    return utc_value, local_value
```

Change `normalize_latest_trade`:

```python
    trade_time_raw = _first_text(trade, ("time", "tradeTime", "tradingTime", "createdAt", "t"))
    trade_time, trade_time_local = _normalize_dnse_trade_time(trade_time_raw)
    return {
        "symbol": symbol.strip().upper(),
        "price": price,
        "volume": int(volume) if volume is not None else None,
        "trade_time": trade_time,
        "trade_time_local": trade_time_local,
        "trade_time_raw": trade_time_raw,
        "source": "dnse",
        "raw": raw,
    }
```

Update `DnseMarketDataClient.__init__` signature and body:

```python
        timeout_seconds: float = 10.0,
        max_concurrency: int | None = None,
    ):
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.dnse_market_api_key).strip()
        self.api_secret = (api_secret if api_secret is not None else settings.dnse_market_api_secret).strip()
        self.base_url = (base_url or settings.dnse_market_base_url).rstrip("/")
        self.board_id = (board_id if board_id is not None else settings.dnse_market_board_id).strip()
        self.timeout_seconds = timeout_seconds
        configured_concurrency = getattr(settings, "dnse_realtime_max_concurrency", 8)
        self.max_concurrency = max(1, int(max_concurrency or configured_concurrency))
```

Change `get_latest_trade`:

```python
    async def get_latest_trade(
        self,
        symbol: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        normalized = symbol.strip().upper()
        path = f"/price/{parse.quote(normalized, safe='')}/trades/latest"
        url = self.latest_trade_url(normalized)
        headers = self.build_headers("GET", path)
        started = time.perf_counter()

        if client is None:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as scoped_client:
                response = await scoped_client.get(url, headers=headers)
        else:
            response = await client.get(url, headers=headers)

        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            raw = {"data": raw}
        tick = normalize_latest_trade(normalized, raw)
        tick["latency_ms"] = latency_ms
        return tick
```

Change `get_latest_trades`:

```python
    async def get_latest_trades(self, symbols: list[str]) -> dict[str, Any]:
        requested_symbols = []
        for symbol in symbols:
            normalized = symbol.strip().upper()
            if normalized and normalized not in requested_symbols:
                requested_symbols.append(normalized)

        ticks: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        started = time.perf_counter()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def fetch_one(symbol: str, client: httpx.AsyncClient) -> tuple[str, dict[str, Any] | None, str | None]:
            try:
                async with semaphore:
                    return symbol, await self.get_latest_trade(symbol, client=client), None
            except Exception as exc:
                return symbol, None, str(exc)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http_client:
            results = await asyncio.gather(
                *(fetch_one(symbol, http_client) for symbol in requested_symbols),
            )

        for symbol, tick, error in results:
            if tick is not None:
                ticks.append(tick)
            elif error:
                errors[symbol] = error

        return {
            "status": "ok" if ticks else "error",
            "source": "dnse",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "symbols": requested_symbols,
            "ticks": ticks,
            "errors": errors,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_market_data.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend_v2/src/services/dnse_market_data.py backend_v2/tests/test_dnse_market_data.py
git commit -m "fix: normalize DNSE tick times and batch fetch concurrently"
```

---

### Task 2: Add Backend DNSE Realtime Provider Bridge

**Files:**
- Create: `backend_v2/src/services/dnse_realtime_provider.py`
- Modify: `backend_v2/src/settings.py`
- Modify: `backend_v2/.env.example`
- Test: `backend_v2/tests/test_dnse_realtime_provider.py`

- [ ] **Step 1: Write failing provider tests**

Create `backend_v2/tests/test_dnse_realtime_provider.py`:

```python
from __future__ import annotations

import pytest

from src.services.dnse_realtime_provider import DnseRealtimeProvider


class FakeMarketClient:
    is_configured = True

    def __init__(self):
        self.calls: list[list[str]] = []

    async def get_latest_trades(self, symbols: list[str]):
        self.calls.append(list(symbols))
        return {
            "status": "ok",
            "source": "dnse",
            "symbols": symbols,
            "ticks": [
                {
                    "symbol": symbol,
                    "price": 100.0,
                    "volume": 10,
                    "trade_time": "2026-05-21T07:29:58+00:00",
                    "trade_time_local": "2026-05-21T14:29:58+07:00",
                    "raw": {},
                }
                for symbol in symbols
            ],
            "errors": {},
            "latency_ms": 20,
        }


class FakeFetcherService:
    def __init__(self):
        self.ingested: list[list[dict]] = []

    async def ingest_realtime_quotes(self, quotes: list[dict]) -> int:
        self.ingested.append(quotes)
        return len(quotes)


@pytest.mark.asyncio
async def test_refresh_ingests_dnse_ticks_as_realtime_quotes():
    market_client = FakeMarketClient()
    fetcher = FakeFetcherService()
    provider = DnseRealtimeProvider(
        market_client=market_client,
        fetcher=fetcher,
        enabled=True,
        cache_ttl_seconds=0,
    )

    result = await provider.refresh_symbols(["FPT", "VCB", "FPT"], in_session=True)

    assert result["status"] == "ok"
    assert result["requested_symbols"] == ["FPT", "VCB"]
    assert result["fetched_count"] == 2
    assert result["ingested_count"] == 2
    assert market_client.calls == [["FPT", "VCB"]]
    assert fetcher.ingested[0][0] == {
        "symbol": "FPT",
        "price": 100.0,
        "volume": 10,
        "time": "2026-05-21T14:29:58+07:00",
        "source": "dnse",
    }


@pytest.mark.asyncio
async def test_refresh_uses_ttl_cache_to_avoid_duplicate_dnse_calls():
    market_client = FakeMarketClient()
    fetcher = FakeFetcherService()
    provider = DnseRealtimeProvider(
        market_client=market_client,
        fetcher=fetcher,
        enabled=True,
        cache_ttl_seconds=30,
    )

    first = await provider.refresh_symbols(["FPT"], in_session=True)
    second = await provider.refresh_symbols(["FPT"], in_session=True)

    assert first["status"] == "ok"
    assert second["status"] == "cached"
    assert market_client.calls == [["FPT"]]
    assert len(fetcher.ingested) == 1


@pytest.mark.asyncio
async def test_refresh_skips_when_disabled_or_out_of_session():
    market_client = FakeMarketClient()
    fetcher = FakeFetcherService()
    disabled = DnseRealtimeProvider(market_client=market_client, fetcher=fetcher, enabled=False)

    disabled_result = await disabled.refresh_symbols(["FPT"], in_session=True)
    closed_result = await DnseRealtimeProvider(
        market_client=market_client,
        fetcher=fetcher,
        enabled=True,
    ).refresh_symbols(["FPT"], in_session=False)

    assert disabled_result["status"] == "disabled"
    assert closed_result["status"] == "market_closed"
    assert market_client.calls == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_realtime_provider.py -v
```

Expected: FAIL because `dnse_realtime_provider.py` does not exist.

- [ ] **Step 3: Add settings**

In `backend_v2/src/settings.py`, below `dnse_realtime_closed_heartbeat_seconds`, add:

```python
    dnse_realtime_enabled: bool = True
    dnse_realtime_cache_ttl_seconds: float = Field(default=2.0, ge=0.0, le=60.0)
    dnse_realtime_max_concurrency: int = Field(default=8, ge=1, le=30)
```

In `backend_v2/.env.example`, below `DNSE_REALTIME_CLOSED_HEARTBEAT_SECONDS=300`, add:

```dotenv
DNSE_REALTIME_ENABLED=true
DNSE_REALTIME_CACHE_TTL_SECONDS=2
DNSE_REALTIME_MAX_CONCURRENCY=8
```

- [ ] **Step 4: Implement provider**

Create `backend_v2/src/services/dnse_realtime_provider.py`:

```python
from __future__ import annotations

import time
from typing import Any, Protocol

from src.services.dnse_market_data import DnseMarketDataClient, get_dnse_market_client
from src.services.vnstock_fetcher import fetcher_service, is_vn30_symbol, normalize_symbol
from src.settings import get_settings


class DnseMarketClientProtocol(Protocol):
    is_configured: bool

    async def get_latest_trades(self, symbols: list[str]) -> dict[str, Any]:
        ...


class RealtimeFetcherProtocol(Protocol):
    async def ingest_realtime_quotes(self, quotes: list[dict[str, Any]]) -> int:
        ...


class DnseRealtimeProvider:
    def __init__(
        self,
        *,
        market_client: DnseMarketClientProtocol | None = None,
        fetcher: RealtimeFetcherProtocol | None = None,
        enabled: bool | None = None,
        cache_ttl_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.market_client = market_client or get_dnse_market_client()
        self.fetcher = fetcher or fetcher_service
        self.enabled = settings.dnse_realtime_enabled if enabled is None else enabled
        self.cache_ttl_seconds = (
            settings.dnse_realtime_cache_ttl_seconds
            if cache_ttl_seconds is None
            else cache_ttl_seconds
        )
        self._last_refresh_at: dict[str, float] = {}

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        output: list[str] = []
        for symbol in symbols:
            normalized = normalize_symbol(symbol)
            if normalized and normalized not in output and is_vn30_symbol(normalized):
                output.append(normalized)
        return output

    def _uncached_symbols(self, symbols: list[str], now: float) -> list[str]:
        if self.cache_ttl_seconds <= 0:
            return symbols
        return [
            symbol
            for symbol in symbols
            if now - self._last_refresh_at.get(symbol, 0.0) >= self.cache_ttl_seconds
        ]

    def _tick_to_quote(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        symbol = normalize_symbol(str(tick.get("symbol", "")))
        price = tick.get("price")
        if not symbol or price is None:
            return None

        return {
            "symbol": symbol,
            "price": price,
            "volume": tick.get("volume") or 0,
            "time": tick.get("trade_time_local") or tick.get("trade_time"),
            "source": "dnse",
        }

    async def refresh_symbols(self, symbols: list[str], *, in_session: bool) -> dict[str, Any]:
        requested = self._normalize_symbols(symbols)
        if not requested:
            return {"status": "skipped", "reason": "no_valid_symbols", "requested_symbols": []}
        if not self.enabled:
            return {"status": "disabled", "requested_symbols": requested}
        if not in_session:
            return {"status": "market_closed", "requested_symbols": requested}
        if not self.market_client.is_configured:
            return {"status": "not_configured", "requested_symbols": requested}

        now = time.monotonic()
        uncached = self._uncached_symbols(requested, now)
        if not uncached:
            return {"status": "cached", "requested_symbols": requested, "fetched_count": 0, "ingested_count": 0}

        response = await self.market_client.get_latest_trades(uncached)
        ticks = list(response.get("ticks") or [])
        quotes = [
            quote
            for tick in ticks
            if (quote := self._tick_to_quote(tick)) is not None
        ]
        ingested_count = await self.fetcher.ingest_realtime_quotes(quotes) if quotes else 0

        refreshed_at = time.monotonic()
        for quote in quotes:
            self._last_refresh_at[str(quote["symbol"])] = refreshed_at

        return {
            "status": "ok" if ticks else "error",
            "requested_symbols": requested,
            "fetched_symbols": uncached,
            "fetched_count": len(ticks),
            "ingested_count": ingested_count,
            "errors": response.get("errors") or {},
            "latency_ms": response.get("latency_ms"),
        }


dnse_realtime_provider = DnseRealtimeProvider()
```

- [ ] **Step 5: Run provider tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_dnse_realtime_provider.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend_v2/src/settings.py backend_v2/.env.example backend_v2/src/services/dnse_realtime_provider.py backend_v2/tests/test_dnse_realtime_provider.py
git commit -m "feat: bridge DNSE realtime ticks into backend cache"
```

---

### Task 3: Feed Main Snapshot and Tick Routes from DNSE Provider

**Files:**
- Modify: `backend_v2/src/routes/stocks.py`
- Test: `backend_v2/tests/test_stocks_dnse_integration.py`

- [ ] **Step 1: Write route integration tests**

Create `backend_v2/tests/test_stocks_dnse_integration.py`:

```python
from __future__ import annotations

import pytest

from src.routes import stocks


class FakeProvider:
    def __init__(self):
        self.calls: list[tuple[list[str], bool]] = []

    async def refresh_symbols(self, symbols: list[str], *, in_session: bool):
        self.calls.append((list(symbols), in_session))
        return {
            "status": "ok",
            "requested_symbols": list(symbols),
            "fetched_count": len(symbols),
            "ingested_count": len(symbols),
        }


class FakeFetcher:
    last_intraday_sync_at = "2026-05-21T14:29:58+07:00"

    def is_intraday_fetch_window(self):
        return True

    def get_snapshots(self, symbols):
        return [
            {
                "symbol": symbol,
                "companyName": symbol,
                "price": 100.0,
                "change": 0.0,
                "changePercent": 0.0,
                "volume": 10,
                "high": 100.0,
                "low": 100.0,
                "open": 100.0,
                "refPrice": 100.0,
                "lastUpdate": "2026-05-21T14:29:58+07:00",
                "syncedAt": "2026-05-21T14:29:59+07:00",
            }
            for symbol in symbols
        ]

    def get_intraday_cache_view(self, symbols=None, limit=120):
        return {
            symbol: [
                {
                    "id": f"dnse|{symbol}|1",
                    "symbol": symbol,
                    "time": "2026-05-21T14:29:58+07:00",
                    "price": 100.0,
                    "volume": 10,
                    "match_type": "manual",
                }
            ]
            for symbol in symbols
        }


@pytest.mark.asyncio
async def test_snapshots_refreshes_dnse_provider_before_returning(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(stocks, "dnse_realtime_provider", provider)
    monkeypatch.setattr(stocks, "fetcher_service", FakeFetcher())
    monkeypatch.setattr(stocks, "reject_refresh_in_snapshot_mode", lambda refresh: None)

    response = await stocks.get_snapshots(symbols="FPT,VCB", refresh=False)

    assert provider.calls == [(["FPT", "VCB"], True)]
    assert response["source"] == "dnse-realtime-cache"
    assert response["dnse_realtime"]["status"] == "ok"
    assert response["count"] == 2


@pytest.mark.asyncio
async def test_ticks_refreshes_dnse_provider_before_reading_cache(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(stocks, "dnse_realtime_provider", provider)
    monkeypatch.setattr(stocks, "fetcher_service", FakeFetcher())
    monkeypatch.setattr(stocks, "reject_refresh_in_snapshot_mode", lambda refresh: None)

    response = await stocks.get_ticks(symbol="FPT", limit=100, refresh=False, force=False)

    assert provider.calls == [(["FPT"], True)]
    assert response["source"] == "dnse-realtime-cache"
    assert response["dnse_realtime"]["status"] == "ok"
    assert response["count"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_stocks_dnse_integration.py -v
```

Expected: FAIL because routes do not call `dnse_realtime_provider`.

- [ ] **Step 3: Import provider and add helper**

In `backend_v2/src/routes/stocks.py`, add import:

```python
from src.services.dnse_realtime_provider import dnse_realtime_provider
```

Add helper near `_intraday_cache_is_stale`:

```python
async def _refresh_dnse_realtime(symbols: list[str]) -> dict[str, Any]:
    in_session = fetcher_service.is_intraday_fetch_window()
    return await dnse_realtime_provider.refresh_symbols(symbols, in_session=in_session)


def _dnse_source_label(result: dict[str, Any], fallback: str) -> str:
    return "dnse-realtime-cache" if result.get("status") in {"ok", "cached"} else fallback
```

- [ ] **Step 4: Refresh snapshots before reading cache**

In `get_snapshots`, after `target_symbols = parse_symbols_query(...)`, add:

```python
    dnse_result = await _refresh_dnse_realtime(target_symbols)
```

Change response fields:

```python
        "source": _dnse_source_label(dnse_result, "snapshot-mysql-cache"),
        "dnse_realtime": dnse_result,
```

- [ ] **Step 5: Refresh intraday bars before reading cache**

In `get_intraday`, after `normalized = _validate_vn30_symbol(symbol)`, add:

```python
    dnse_result = await _refresh_dnse_realtime([normalized])
```

Change response fields:

```python
        "source": _dnse_source_label(dnse_result, "intraday-cache"),
        "dnse_realtime": dnse_result,
```

- [ ] **Step 6: Refresh raw ticks before reading cache**

In `get_ticks`, after `in_session = fetcher_service.is_intraday_fetch_window()`, add:

```python
    dnse_result = await _refresh_dnse_realtime([normalized])
```

Change response fields:

```python
        "source": _dnse_source_label(dnse_result, "intraday-cache"),
        "dnse_realtime": dnse_result,
```

- [ ] **Step 7: Run route integration tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_stocks_dnse_integration.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend_v2/src/routes/stocks.py backend_v2/tests/test_stocks_dnse_integration.py
git commit -m "feat: refresh main stock routes from DNSE realtime"
```

---

### Task 4: Feed Existing Main WebSocket from DNSE Provider

**Files:**
- Modify: `backend_v2/src/routes/websocket.py`
- Test: extend `backend_v2/tests/test_stocks_dnse_integration.py`

- [ ] **Step 1: Add a unit-testable websocket helper**

Append this test to `backend_v2/tests/test_stocks_dnse_integration.py`:

```python
@pytest.mark.asyncio
async def test_websocket_payload_refreshes_dnse_before_snapshot(monkeypatch):
    from src.routes import websocket as ws_route

    provider = FakeProvider()
    monkeypatch.setattr(ws_route, "dnse_realtime_provider", provider)
    monkeypatch.setattr(ws_route, "fetcher_service", FakeFetcher())

    payloads = await ws_route._build_dnse_websocket_payloads({"FPT", "VCB"})

    assert provider.calls == [(["FPT", "VCB"], True)]
    assert [item["symbol"] for item in payloads] == ["FPT", "VCB"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_stocks_dnse_integration.py::test_websocket_payload_refreshes_dnse_before_snapshot -v
```

Expected: FAIL because `_build_dnse_websocket_payloads` does not exist.

- [ ] **Step 3: Implement websocket payload helper**

In `backend_v2/src/routes/websocket.py`, add import:

```python
from src.services.dnse_realtime_provider import dnse_realtime_provider
```

Add helper above `websocket_dnse_compatible`:

```python
async def _build_dnse_websocket_payloads(subscribed_symbols: set[str]) -> list[dict[str, Any]]:
    symbols = sorted(subscribed_symbols)
    in_session = fetcher_service.is_intraday_fetch_window()
    await dnse_realtime_provider.refresh_symbols(symbols, in_session=in_session)

    payloads: list[dict[str, Any]] = []
    snapshots = fetcher_service.get_snapshots(symbols)
    for snapshot in snapshots:
        if _to_float(snapshot.get("price")) <= 0:
            continue
        payloads.append(
            {
                "symbol": snapshot.get("symbol"),
                "price": _to_float(snapshot.get("price")),
                "change": _to_float(snapshot.get("change")),
                "changePercent": _to_float(snapshot.get("changePercent")),
                "volume": int(_to_float(snapshot.get("volume"))),
                "high": _to_float(snapshot.get("high")),
                "low": _to_float(snapshot.get("low")),
                "open": _to_float(snapshot.get("open")),
                "time": str(snapshot.get("lastUpdate") or datetime.now(timezone.utc).isoformat()),
                "source": "dnse-realtime-cache",
            }
        )
    return payloads
```

Update the websocket loop body from direct `fetcher_service.get_snapshots(...)` to:

```python
            for payload in await _build_dnse_websocket_payloads(subscribed_symbols):
                await websocket.send_json(payload)
```

- [ ] **Step 4: Run websocket helper test**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests/test_stocks_dnse_integration.py::test_websocket_payload_refreshes_dnse_before_snapshot -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend_v2/src/routes/websocket.py backend_v2/tests/test_stocks_dnse_integration.py
git commit -m "feat: stream DNSE-backed snapshots over main websocket"
```

---

### Task 5: Update Frontend Main-Web Types and Time Display

**Files:**
- Modify: `src/services/dnseTickSandboxApi.ts`
- Modify: `src/views/DnseTickSandbox.vue`
- Modify: `src/services/stockBackendApi.ts`
- Modify: `src/composables/useStockData.ts`

- [ ] **Step 1: Add DNSE tick local time type**

In `src/services/dnseTickSandboxApi.ts`, update `DnseTick`:

```ts
export interface DnseTick {
  symbol: string
  price: number | null
  volume: number | null
  trade_time: string | null
  trade_time_local?: string | null
  trade_time_raw?: string | null
  source: 'dnse'
  latency_ms?: number
  raw: Record<string, unknown>
}
```

- [ ] **Step 2: Display local tick time in sandbox**

In `src/views/DnseTickSandbox.vue`, replace table time display:

```vue
<span class="col-span-2 truncate text-slate-300">{{ formatTradeTime(tick) }}</span>
```

Add function near `formatSessionTime`:

```ts
function formatTradeTime(tick: DnseTick): string {
  const value = tick.trade_time_local || tick.trade_time
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
}
```

Update chart timestamp input:

```ts
    time: toUtcTimestamp(selectedTick.trade_time_local || selectedTick.trade_time),
```

- [ ] **Step 3: Add backend source metadata types**

In `src/services/stockBackendApi.ts`, find snapshot/tick/intraday response interfaces and add optional fields:

```ts
  source?: string
  dnse_realtime?: {
    status: string
    requested_symbols?: string[]
    fetched_count?: number
    ingested_count?: number
    latency_ms?: number
    errors?: Record<string, string>
  }
```

If the interfaces already have `source`, only add `dnse_realtime`.

- [ ] **Step 4: Update `useStockData` strategy comment and status behavior**

At the top of `src/composables/useStockData.ts`, replace the strategy comment:

```ts
 * Data strategy:
 * 1) FastAPI backend snapshots, now refreshed from DNSE OpenAPI during market session
 * 2) Backend WebSocket /api/ws/dnse, backed by the same DNSE-fed snapshot cache
 * 3) Direct browser DNSE fallback only when backend is unavailable
```

In `connectRealtime`, keep the existing websocket path. Do not import `dnseTickSandboxApi`.

- [ ] **Step 5: Run frontend typecheck**

Run:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/services/dnseTickSandboxApi.ts src/views/DnseTickSandbox.vue src/services/stockBackendApi.ts src/composables/useStockData.ts
git commit -m "feat: surface DNSE-backed realtime metadata in frontend"
```

---

### Task 6: End-to-End Verification

**Files:**
- No code changes unless verification reveals a defect.

- [ ] **Step 1: Run backend tests**

Run:

```bash
.\.venv\Scripts\python.exe -m pytest backend_v2/tests -v
```

Expected: PASS.

- [ ] **Step 2: Run frontend checks**

Run:

```bash
npm run type-check
```

Expected: PASS.

- [ ] **Step 3: Start backend**

Run:

```bash
.\.venv\Scripts\python.exe backend_v2\run.py
```

Expected: backend starts on `http://localhost:8000`.

- [ ] **Step 4: Verify main snapshots route during session**

Run during market session:

```bash
.\.venv\Scripts\python.exe -c "import httpx, json; r=httpx.get('http://localhost:8000/api/stocks/snapshots?symbols=FPT,VCB,VIC', timeout=15); print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:4000])"
```

Expected:

```json
{
  "source": "dnse-realtime-cache",
  "dnse_realtime": {
    "status": "ok",
    "fetched_count": 3,
    "ingested_count": 3
  }
}
```

If market is closed, expected `dnse_realtime.status` is `market_closed` and source remains `snapshot-mysql-cache`.

- [ ] **Step 5: Verify main raw ticks route**

Run:

```bash
.\.venv\Scripts\python.exe -c "import httpx, json; r=httpx.get('http://localhost:8000/api/stocks/FPT/ticks?limit=5', timeout=15); print(json.dumps(r.json(), ensure_ascii=False, indent=2)[:3000])"
```

Expected: `ticks[0].time` is timezone-aware local ISO such as `2026-05-21T14:29:58+07:00`.

- [ ] **Step 6: Start frontend**

Run:

```bash
npm run dev
```

Expected: Vite serves the app, usually on `http://localhost:5173` or the next available port.

- [ ] **Step 7: Browser verify main dashboard**

Open `/` while logged in or with current app auth state. Expected:

- Stock cards update from backend snapshots.
- Connection status becomes connected when `VITE_ENABLE_REALTIME=true`, or polling refreshes snapshots when realtime disabled.
- No browser calls to `https://openapi.dnse.com.vn`.
- Network tab shows calls to `/api/stocks/snapshots` and/or websocket `/api/ws/dnse`.

- [ ] **Step 8: Browser verify sandbox remains diagnostic**

Open `/dnse-ticks`. Expected:

- It still calls `/api/dnse/ticks/latest`.
- Table displays Vietnam local time, not raw `07:xx` UTC-like strings.
- Raw JSON still includes `trade_time`, `trade_time_local`, and `trade_time_raw`.

- [ ] **Step 9: Commit verification-only fixes if needed**

Only if a defect is found and fixed:

```bash
git add <changed-files>
git commit -m "fix: stabilize DNSE realtime main web integration"
```

---

## Self-Review

**Spec coverage:** This plan promotes DNSE realtime ticks to the main web through backend snapshots, raw ticks, intraday bars, and websocket routes. It keeps sandbox available and fixes timestamp ambiguity.

**Placeholder scan:** No TBD/TODO/fill-later steps remain. Each implementation step names exact files and code.

**Type consistency:** Backend provider emits quote payloads accepted by `fetcher_service.ingest_realtime_quotes(...)`. Frontend keeps the existing `RealtimeQuote` websocket contract and only adds optional response metadata.
