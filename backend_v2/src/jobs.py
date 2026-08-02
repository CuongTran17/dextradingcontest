from contextlib import asynccontextmanager
import logging
import time
from typing import Any, Callable

from src.database.db import SessionLocal
from src.services.binance_realtime import BinanceRealtimeService
from src.services.crypto_market_repair import CryptoMarketRepairService
from src.services.leaderboard_broadcast import LeaderboardBroadcastService
from src.services.pending_order_processor import PendingOrderProcessor
from src.settings import get_settings

logger = logging.getLogger(__name__)


def build_lifespan(
    *,
    init_db: Callable[[], None],
    realtime_factory: Callable[[], Any] = BinanceRealtimeService,
    repair_factory: Callable[[], Any] | None = None,
    pending_processor_factory: Callable[[], Any] | None = None,
):
    @asynccontextmanager
    async def lifespan(app: Any):
        startup_started_at = time.perf_counter()
        logger.info("backend startup: init_db start")
        init_db()
        logger.info("backend startup: init_db done duration_ms=%.1f", _elapsed_ms(startup_started_at))
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
        step_started_at = time.perf_counter()
        logger.info("backend startup: realtime start")
        await realtime.start()
        logger.info("backend startup: realtime done duration_ms=%.1f", _elapsed_ms(step_started_at))
        step_started_at = time.perf_counter()
        logger.info("backend startup: pending processor start")
        await pending_processor.start()
        logger.info("backend startup: pending processor done duration_ms=%.1f", _elapsed_ms(step_started_at))
        step_started_at = time.perf_counter()
        logger.info("backend startup: repair loop start")
        await repair.start()
        logger.info("backend startup: repair loop done duration_ms=%.1f", _elapsed_ms(step_started_at))
        step_started_at = time.perf_counter()
        logger.info("backend startup: leaderboard start")
        await leaderboard.start()
        logger.info(
            "backend startup complete duration_ms=%.1f",
            _elapsed_ms(startup_started_at),
        )
        try:
            yield
        finally:
            await leaderboard.stop()
            await pending_processor.stop()
            await repair.stop()
            await realtime.stop()

    return lifespan


def _elapsed_ms(started_at: float) -> float:
    return (time.perf_counter() - started_at) * 1000
