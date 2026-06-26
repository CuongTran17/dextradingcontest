from contextlib import asynccontextmanager
from typing import Any, Callable

from src.services.binance_realtime import BinanceRealtimeService


def build_lifespan(*, init_db: Callable[[], None]):
    @asynccontextmanager
    async def lifespan(app: Any):
        init_db()
        realtime = BinanceRealtimeService()
        app.state.crypto_realtime = realtime
        await realtime.start()
        try:
            yield
        finally:
            await realtime.stop()

    return lifespan
