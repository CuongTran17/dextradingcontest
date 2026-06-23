from __future__ import annotations

import pytest

from src.routes import stocks


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
    last_history_sync_at: dict[str, str] = {}

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


@pytest.mark.anyio
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


@pytest.mark.anyio
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


@pytest.mark.anyio
async def test_websocket_payload_refreshes_dnse_before_snapshot(monkeypatch):
    from src.routes import websocket as ws_route

    provider = FakeProvider()
    monkeypatch.setattr(ws_route, "dnse_realtime_provider", provider)
    monkeypatch.setattr(ws_route, "fetcher_service", FakeFetcher())

    payloads = await ws_route._build_dnse_websocket_payloads({"FPT", "VCB"})

    assert provider.calls == [(["FPT", "VCB"], True)]
    assert [item["symbol"] for item in payloads] == ["FPT", "VCB"]
    assert all(item["source"] == "dnse-realtime-cache" for item in payloads)
