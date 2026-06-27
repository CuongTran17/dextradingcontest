from contextlib import asynccontextmanager
from typing import Any, Callable

from src.services.binance_realtime import BinanceRealtimeService
from src.services.crypto_market_repair import CryptoMarketRepairService
from src.settings import get_settings


def build_lifespan(
    *,
    init_db: Callable[[], None],
    realtime_factory: Callable[[], Any] = BinanceRealtimeService,
    repair_factory: Callable[[], Any] | None = None,
):
    @asynccontextmanager
    async def lifespan(app: Any):
        init_db()
        settings = get_settings()
        realtime = realtime_factory()
        repair = repair_factory() if repair_factory is not None else CryptoMarketRepairService(
            lookback_days=settings.crypto_repair_lookback_days,
            interval_seconds=settings.crypto_repair_interval_seconds,
            enabled=settings.crypto_repair_on_startup,
        )
        app.state.crypto_realtime = realtime
        app.state.crypto_market_repair = repair
        await realtime.start()
        await repair.start()
        try:
            yield
        finally:
            await repair.stop()
            await realtime.stop()

    return lifespan
