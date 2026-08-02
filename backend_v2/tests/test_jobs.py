from types import SimpleNamespace

import pytest

from src.jobs import build_lifespan


@pytest.mark.anyio
async def test_lifespan_starts_and_stops_crypto_market_repair():
    events = []

    class FakeRealtime:
        async def start(self):
            events.append("realtime_start")

        async def stop(self):
            events.append("realtime_stop")

    class FakeRepair:
        async def start(self):
            events.append("repair_start")

        async def stop(self):
            events.append("repair_stop")

    class FakePendingProcessor:
        async def start(self):
            events.append("pending_start")

        async def stop(self):
            events.append("pending_stop")

    realtime = FakeRealtime()
    repair = FakeRepair()
    app = SimpleNamespace(state=SimpleNamespace())
    lifespan = build_lifespan(
        init_db=lambda: events.append("init_db"),
        realtime_factory=lambda: realtime,
        repair_factory=lambda: repair,
        pending_processor_factory=lambda: FakePendingProcessor(),
    )

    async with lifespan(app):
        assert app.state.crypto_realtime is realtime
        assert app.state.crypto_market_repair is repair
        assert events == [
            "init_db",
            "realtime_start",
            "pending_start",
            "repair_start",
        ]

    assert events == [
        "init_db",
        "realtime_start",
        "pending_start",
        "repair_start",
        "pending_stop",
        "repair_stop",
        "realtime_stop",
    ]
