from contextlib import asynccontextmanager
from typing import Any, Callable

from src.database.db import SessionLocal
from src.services.binance_realtime import BinanceRealtimeService
from src.services.crypto_market_repair import CryptoMarketRepairService
from src.services.leaderboard_broadcast import LeaderboardBroadcastService
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
        leaderboard = LeaderboardBroadcastService(
            realtime_service=realtime,
            db_session_factory=SessionLocal,
        )
        app.state.crypto_realtime = realtime
        app.state.crypto_market_repair = repair
        app.state.leaderboard_broadcast = leaderboard
        await realtime.start()
        await repair.start()
        await leaderboard.start()
        try:
            yield
        finally:
            await leaderboard.stop()
            await repair.stop()
            await realtime.stop()

    return lifespan
