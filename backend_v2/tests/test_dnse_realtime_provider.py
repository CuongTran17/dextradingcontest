from __future__ import annotations

import pytest

from src.services.dnse_realtime_provider import DnseRealtimeProvider


@pytest.fixture
def anyio_backend():
    return "asyncio"


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
                    "match_type": "buy",
                    "side_source": "dnse",
                    "side_confidence": "source",
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


@pytest.mark.anyio
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
        "match_type": "buy",
        "side_source": "dnse",
        "side_confidence": "source",
        "source": "dnse",
    }


def test_tick_to_quote_preserves_side_metadata():
    provider = DnseRealtimeProvider(
        market_client=FakeMarketClient(),
        fetcher=FakeFetcherService(),
        enabled=True,
    )

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

    assert quote is not None
    assert quote["match_type"] == "buy"
    assert quote["side_source"] == "dnse"
    assert quote["side_confidence"] == "source"


@pytest.mark.anyio
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


@pytest.mark.anyio
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
