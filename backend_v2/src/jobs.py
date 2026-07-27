from contextlib import asynccontextmanager
from typing import Any, Callable

from src.database.db import SessionLocal
from src.services.binance_realtime import BinanceRealtimeService
from src.services.crypto_market_repair import CryptoMarketRepairService
from src.services.leaderboard_broadcast import LeaderboardBroadcastService
from src.services.pending_order_processor import PendingOrderProcessor
from src.settings import get_settings


def build_lifespan(
    *,
    init_db: Callable[[], None],
    realtime_factory: Callable[[], Any] = BinanceRealtimeService,
    repair_factory: Callable[[], Any] | None = None,
    pending_processor_factory: Callable[[], Any] | None = None,
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
        pending_processor = (
            pending_processor_factory()
            if pending_processor_factory is not None
            else PendingOrderProcessor(
                db_session_factory=SessionLocal,
                enabled=settings.crypto_pending_order_reconcile_on_startup,
                interval_seconds=settings.crypto_order_reconcile_interval_seconds,
            )
        )
        app.state.crypto_realtime = realtime
        app.state.crypto_market_repair = repair
        app.state.leaderboard_broadcast = leaderboard
        app.state.pending_order_processor = pending_processor
        await realtime.start()
        await repair.run_once()
        await pending_processor.start()
        await repair.start()
        await leaderboard.start()
        try:
            yield
        finally:
            await leaderboard.stop()
            await pending_processor.stop()
            await repair.stop()
            await realtime.stop()

    return lifespan
