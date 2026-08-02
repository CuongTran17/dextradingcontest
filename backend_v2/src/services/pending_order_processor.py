from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable

from src.database.crypto_market_duckdb import CryptoMarketDuckDB
from src.repositories.crypto_trading import CryptoTradingRepository
from src.services.crypto_execution import CryptoOrderService

logger = logging.getLogger(__name__)


class PendingOrderProcessor:
    def __init__(
        self,
        *,
        db_session_factory: Callable[[], Any],
        market_repo: CryptoMarketDuckDB | None = None,
        market_repo_factory: Callable[[], Any] = CryptoMarketDuckDB,
        enabled: bool = True,
        interval_seconds: int = 30,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        self.db_session_factory = db_session_factory
        self._market_repo = market_repo
        self._market_repo_factory = market_repo_factory
        self.enabled = enabled
        self.interval_seconds = interval_seconds
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()
        self._status = "idle" if enabled else "disabled"
        self._last_result: dict[str, Any] | None = None
        self._last_error: str | None = None

    async def start(self) -> dict[str, Any]:
        if not self.enabled:
            self._status = "disabled"
            return {"status": "disabled", "checked": 0, "filled": 0}
        result = await self.reconcile_once()
        if self._task is None:
            self._task = asyncio.create_task(
                self._run_loop(),
                name="crypto-order-reconcile",
            )
        return result

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None

    async def reconcile_once(self) -> dict[str, Any]:
        if not self.enabled:
            self._status = "disabled"
            return {"status": "disabled", "checked": 0, "filled": 0}
        async with self._lock:
            self._status = "reconciling"
            self._last_error = None
            try:
                result = await asyncio.to_thread(self._reconcile_once_sync)
            except Exception as exc:
                self._status = "failed"
                self._last_error = str(exc)
                logger.exception("Pending order reconciliation failed")
                raise
            self._status = "success"
            self._last_result = result
            return result

    def status(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "enabled": self.enabled,
            "interval_seconds": self.interval_seconds,
            "last_result": self._last_result,
            "last_error": self._last_error,
        }

    @property
    def market_repo(self) -> Any:
        if self._market_repo is None:
            self._market_repo = self._market_repo_factory()
        return self._market_repo

    async def _run_loop(self) -> None:
        while True:
            await asyncio.sleep(self.interval_seconds)
            try:
                await self.reconcile_once()
            except Exception:
                pass

    def _reconcile_once_sync(self) -> dict[str, Any]:
        pending_checked = 0
        pending_filled = 0
        pending_skipped = 0
        exit_checked = 0
        exit_filled = 0
        exit_skipped = 0
        errors: list[dict[str, Any]] = []

        with self.db_session_factory() as db:
            repo = CryptoTradingRepository(db)
            service = CryptoOrderService(repo, liquidity_provider=None)

            for order in repo.list_pending_limit_orders():
                pending_checked += 1
                try:
                    if not self._order_was_triggered(order):
                        pending_skipped += 1
                        continue
                    service.fill_pending_limit_order(
                        order_id=order.id,
                        fill_price=Decimal(order.limit_price),
                        liquidity_source="historical_candle",
                    )
                    pending_filled += 1
                except Exception as exc:
                    repo.rollback()
                    errors.append({"order_id": order.id, "error": str(exc)})
                    logger.exception("Failed to reconcile pending order %s", order.id)

            for order in repo.list_open_exit_trigger_orders():
                exit_checked += 1
                try:
                    trigger = self._exit_trigger_for_order(order)
                    if trigger is None:
                        exit_skipped += 1
                        continue
                    trigger_type, trigger_price = trigger
                    service.fill_exit_trigger_order(
                        entry_order_id=order.id,
                        trigger_type=trigger_type,
                        trigger_price=trigger_price,
                        liquidity_source="historical_candle",
                    )
                    exit_filled += 1
                except Exception as exc:
                    repo.rollback()
                    errors.append({"order_id": order.id, "error": str(exc)})
                    logger.exception("Failed to reconcile exit trigger %s", order.id)

        return {
            "status": "success",
            "checked": pending_checked + exit_checked,
            "filled": pending_filled + exit_filled,
            "skipped": pending_skipped + exit_skipped,
            "pending_checked": pending_checked,
            "pending_filled": pending_filled,
            "pending_skipped": pending_skipped,
            "exit_checked": exit_checked,
            "exit_filled": exit_filled,
            "exit_skipped": exit_skipped,
            "errors": errors,
        }

    def _order_was_triggered(self, order) -> bool:
        submitted_at = _as_aware_utc(order.submitted_at)
        end_time = _as_aware_utc(self.now_provider())
        start_time = _floor_minute(submitted_at)
        if end_time <= start_time:
            return False

        minutes = int((end_time - start_time).total_seconds() // 60) + 5
        candles = self.market_repo.load_candles(
            order.asset.symbol,
            "1m",
            limit=minutes,
            start_time=start_time,
            end_time=end_time,
        )
        limit_price = Decimal(order.limit_price)
        if order.side == "buy":
            return any(Decimal(str(candle["low"])) <= limit_price for candle in candles)
        return any(Decimal(str(candle["high"])) >= limit_price for candle in candles)

    def _exit_trigger_for_order(self, order) -> tuple[str, Decimal] | None:
        completed_at = getattr(order, "completed_at", None) or order.submitted_at
        start_time = _floor_minute(_as_aware_utc(completed_at))
        end_time = _as_aware_utc(self.now_provider())
        if end_time <= start_time:
            return None

        minutes = int((end_time - start_time).total_seconds() // 60) + 5
        candles = self.market_repo.load_candles(
            order.asset.symbol,
            "1m",
            limit=minutes,
            start_time=start_time,
            end_time=end_time,
        )
        stop_loss_price = (
            Decimal(order.stop_loss_price)
            if getattr(order, "stop_loss_price", None) is not None
            else None
        )
        take_profit_price = (
            Decimal(order.take_profit_price)
            if getattr(order, "take_profit_price", None) is not None
            else None
        )
        for candle in candles:
            low = Decimal(str(candle["low"]))
            high = Decimal(str(candle["high"]))
            if stop_loss_price is not None and low <= stop_loss_price:
                return "stop_loss", stop_loss_price
            if take_profit_price is not None and high >= take_profit_price:
                return "take_profit", take_profit_price
        return None


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _floor_minute(value: datetime) -> datetime:
    return value.replace(second=0, microsecond=0)
