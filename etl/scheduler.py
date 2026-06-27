"""APScheduler entrypoint for ETL jobs."""
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import date, timedelta
from functools import partial
from typing import Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from etl.config import (
    CACHE_REFRESH_CRON,
    DAILY_ETL_CRON,
    DEFAULT_SYMBOLS,
    FUNDAMENTAL_REFRESH_CRON,
    HEALTH_CHECK_INTERVAL_MINUTES,
    SCHEDULE_TIMEZONE,
    EtlConfig,
)
from etl.execution import run_etl_in_process, shutdown_etl_process_pool
from etl.health import check_etl_health
from etl.load_to_mysql import load_financial_cache

log = logging.getLogger(__name__)


def default_cfg_factory(
    *,
    symbols: list[str] | None = None,
    enable_fundamental: bool = True,
    enable_google_news: bool = True,
    enable_mysql_load: bool = True,
) -> EtlConfig:
    today = date.today()
    return EtlConfig.from_args(
        start_date=today - timedelta(days=365),
        end_date=today,
        symbols=symbols or list(DEFAULT_SYMBOLS),
        enable_fundamental=enable_fundamental,
        enable_google_news=enable_google_news,
        enable_mysql_load=enable_mysql_load,
        run_mode="incremental",
    )


class EtlScheduler:
    """Manage ETL cron jobs for standalone or embedded use."""

    def __init__(self, timezone: str = SCHEDULE_TIMEZONE, scheduler: AsyncIOScheduler | None = None):
        self.scheduler = scheduler or AsyncIOScheduler(timezone=timezone)

    def register_jobs(
        self,
        cfg_factory: Callable[[], EtlConfig] = default_cfg_factory,
        *,
        cache_refresh: Callable[[], object] | None = None,
    ) -> None:
        self.scheduler.add_job(
            self._run_daily_etl,
            "cron",
            id="etl-daily-full",
            replace_existing=True,
            kwargs={"cfg_factory": cfg_factory},
            **DAILY_ETL_CRON,
        )
        self.scheduler.add_job(
            self._refresh_caches,
            "cron",
            id="etl-cache-refresh",
            replace_existing=True,
            kwargs={"cfg_factory": cfg_factory, "cache_refresh": cache_refresh},
            **CACHE_REFRESH_CRON,
        )
        self.scheduler.add_job(
            self._run_fundamental_refresh,
            "cron",
            id="etl-weekly-fundamental",
            replace_existing=True,
            kwargs={"cfg_factory": cfg_factory},
            **FUNDAMENTAL_REFRESH_CRON,
        )
        self.scheduler.add_job(
            self._health_check,
            "interval",
            id="etl-health-check",
            replace_existing=True,
            minutes=HEALTH_CHECK_INTERVAL_MINUTES,
            kwargs={"cfg_factory": cfg_factory},
        )

    async def _run_daily_etl(self, cfg_factory: Callable[[], EtlConfig]) -> None:
        cfg = cfg_factory()
        log.info("Daily ETL started run_id=%s symbols=%d", cfg.run_id, len(cfg.symbols))
        await run_etl_in_process(cfg)
        log.info("Daily ETL completed run_id=%s", cfg.run_id)

    async def _refresh_caches(
        self,
        cfg_factory: Callable[[], EtlConfig],
        cache_refresh: Callable[[], object] | None = None,
    ) -> None:
        if cache_refresh is not None:
            result = cache_refresh()
            if asyncio.iscoroutine(result):
                await result
            return
        cfg = cfg_factory()
        await asyncio.get_running_loop().run_in_executor(None, partial(load_financial_cache, cfg))

    async def _run_fundamental_refresh(self, cfg_factory: Callable[[], EtlConfig]) -> None:
        cfg = cfg_factory()
        fundamental_cfg = EtlConfig.from_args(
            start_date=cfg.user_start,
            end_date=cfg.user_end,
            symbols=cfg.symbols,
            enable_fundamental=True,
            enable_google_news=False,
            enable_mysql_load=False,
            run_mode="backfill",
        )
        from etl.extract.extract_fundamental import extract_all_fundamentals

        def _extract_and_load() -> None:
            for symbol in fundamental_cfg.symbols:
                extract_all_fundamentals(symbol, fundamental_cfg)
            load_financial_cache(fundamental_cfg)

        await asyncio.get_running_loop().run_in_executor(None, _extract_and_load)

    async def _health_check(self, cfg_factory: Callable[[], EtlConfig]) -> None:
        health = check_etl_health(cfg_factory())
        if health["status"] != "healthy":
            log.warning("ETL health check: %s", health)
        else:
            log.info("ETL health check: healthy")

    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        shutdown_etl_process_pool()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ETL scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Register jobs and print them without starting the scheduler loop")
    return parser.parse_args()


async def _main() -> None:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args()
    scheduler = EtlScheduler()
    scheduler.register_jobs()
    if args.dry_run:
        for job in scheduler.scheduler.get_jobs():
            print(f"{job.id}: {job.trigger}")
        return
    scheduler.start()
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        scheduler.shutdown()


if __name__ == "__main__":
    asyncio.run(_main())
