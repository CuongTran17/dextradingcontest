import asyncio

import pytest

from src.services.crypto_market_repair import CryptoMarketRepairService


class FakeBackfill:
    def __init__(self):
        self.calls = []

    def backfill_symbol(self, symbol, *, days, page_limit=1000):
        self.calls.append((symbol, days, page_limit))
        return {"symbol": symbol, "stored": 0, "pages": 0, "last_closed_open_time": None}


@pytest.mark.anyio
async def test_repair_runs_incremental_backfill_for_configured_symbols_once():
    backfill = FakeBackfill()
    service = CryptoMarketRepairService(
        backfill_service=backfill,
        symbols=("BTCUSDT", "ETHUSDT"),
        lookback_days=365,
        interval_seconds=300,
    )

    result = await service.run_once()

    assert [call[0] for call in backfill.calls] == ["BTCUSDT", "ETHUSDT"]
    assert {call[1] for call in backfill.calls} == {365}
    assert result["symbols"] == ["BTCUSDT", "ETHUSDT"]
    assert service.status()["status"] == "success"


@pytest.mark.anyio
async def test_disabled_repair_does_not_call_backfill():
    backfill = FakeBackfill()
    service = CryptoMarketRepairService(
        backfill_service=backfill,
        symbols=("BTCUSDT",),
        enabled=False,
    )

    result = await service.run_once()

    assert backfill.calls == []
    assert result["status"] == "disabled"
    assert service.status()["status"] == "disabled"


@pytest.mark.anyio
async def test_start_runs_repair_in_background_without_blocking():
    started = asyncio.Event()
    release = asyncio.Event()

    class SlowBackfill(FakeBackfill):
        def backfill_symbol(self, symbol, *, days, page_limit=1000):
            self.calls.append((symbol, days, page_limit))
            loop = asyncio.run_coroutine_threadsafe(started.set(), event_loop)
            loop.result(timeout=1)
            asyncio.run_coroutine_threadsafe(release.wait(), event_loop).result(timeout=1)
            return {"symbol": symbol, "stored": 0, "pages": 0, "last_closed_open_time": None}

    event_loop = asyncio.get_running_loop()
    backfill = SlowBackfill()
    service = CryptoMarketRepairService(
        backfill_service=backfill,
        symbols=("BTCUSDT",),
        interval_seconds=3600,
    )

    await service.start()
    await asyncio.wait_for(started.wait(), timeout=1)

    assert service.status()["status"] == "repairing"
    release.set()
    await service.stop()
    assert backfill.calls == [("BTCUSDT", 365, 1000)]
