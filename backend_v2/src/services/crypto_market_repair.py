from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from src.services.crypto_market_backfill import (
    DEFAULT_SYMBOLS,
    CryptoMarketBackfillService,
)

logger = logging.getLogger(__name__)


class CryptoMarketRepairService:
    def __init__(
        self,
        backfill_service: CryptoMarketBackfillService | None = None,
        *,
        symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
        lookback_days: int = 365,
        interval_seconds: int = 300,
        enabled: bool = True,
    ) -> None:
        self.backfill_service = backfill_service or CryptoMarketBackfillService()
        self.symbols = tuple(symbol.upper() for symbol in symbols)
        self.lookback_days = lookback_days
        self.interval_seconds = interval_seconds
        self.enabled = enabled
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._status = "idle" if enabled else "disabled"
        self._last_started_at: str | None = None
        self._last_finished_at: str | None = None
        self._last_error: str | None = None
        self._last_result: dict[str, Any] | None = None

    async def start(self) -> None:
        if not self.enabled or self._task is not None:
            return
        self._task = asyncio.create_task(self._run_loop(), name="crypto-market-repair")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def run_once(self) -> dict[str, Any]:
        if not self.enabled:
            self._status = "disabled"
            return {"status": "disabled", "symbols": []}
        async with self._lock:
            self._status = "repairing"
            self._last_started_at = _utc_now()
            self._last_error = None
            try:
                result = await asyncio.to_thread(self._run_once_sync)
            except Exception as exc:
                self._status = "failed"
                self._last_error = str(exc)
                self._last_finished_at = _utc_now()
                logger.exception("Crypto market repair failed")
                raise
            self._status = "success"
            self._last_result = result
            self._last_finished_at = _utc_now()
            return result

    def status(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "enabled": self.enabled,
            "symbols": list(self.symbols),
            "lookback_days": self.lookback_days,
            "interval_seconds": self.interval_seconds,
            "last_started_at": self._last_started_at,
            "last_finished_at": self._last_finished_at,
            "last_error": self._last_error,
            "last_result": self._last_result,
        }

    def _run_once_sync(self) -> dict[str, Any]:
        results = [
            self.backfill_service.backfill_symbol(
                symbol,
                days=self.lookback_days,
                page_limit=1000,
            )
            for symbol in self.symbols
        ]
        return {
            "status": "success",
            "symbols": list(self.symbols),
            "results": results,
        }

    async def _run_loop(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                pass
            await asyncio.sleep(self.interval_seconds)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
