from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

from src.database.crypto_market_duckdb import crypto_market_repo
from src.services.binance_market_data import get_klines_page

DEFAULT_SYMBOLS = (
    "BTCUSDT",
    "ETHUSDT",
    "SOLUSDT",
    "XRPUSDT",
    "BNBUSDT",
)


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _floor_minute(value: datetime) -> datetime:
    return _utc(value).replace(second=0, microsecond=0)


class CryptoMarketBackfillService:
    def __init__(
        self,
        repo=crypto_market_repo,
        fetch_page: Callable = get_klines_page,
        *,
        now_provider: Callable[[], datetime] | None = None,
    ):
        self.repo = repo
        self.fetch_page = fetch_page
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def backfill_symbol(
        self,
        symbol: str,
        *,
        days: int = 365,
        start_time: datetime | None = None,
        page_limit: int = 1000,
    ) -> dict:
        normalized = symbol.upper()
        now = _utc(self.now_provider())
        final_open_time = _floor_minute(now) - timedelta(minutes=1)
        state = self.repo.get_ingestion_state(normalized, "1m")
        if state and state.get("last_closed_open_time"):
            cursor = _utc(state["last_closed_open_time"]) + timedelta(minutes=1)
        elif start_time is not None:
            cursor = _floor_minute(start_time)
        else:
            cursor = _floor_minute(now - timedelta(days=max(1, days)))

        stored = 0
        pages = 0
        last_closed = state.get("last_closed_open_time") if state else None
        try:
            while cursor <= final_open_time:
                rows = self.fetch_page(
                    normalized,
                    "1m",
                    min(max(page_limit, 1), 1000),
                    cursor,
                    final_open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
                )
                if not rows:
                    break

                pages += 1
                closed_rows = [
                    row
                    for row in rows
                    if row.get("is_closed", True)
                    and _utc(row["open_time"]) <= final_open_time
                ]
                if closed_rows:
                    stored += self.repo.upsert_candles(
                        normalized,
                        "1m",
                        closed_rows,
                    )
                    last_closed = _utc(closed_rows[-1]["open_time"])
                    self.repo.update_ingestion_state(
                        normalized,
                        "1m",
                        last_closed,
                        status="running",
                    )

                cursor = max(_utc(row["open_time"]) for row in rows) + timedelta(minutes=1)
                if len(rows) < min(max(page_limit, 1), 1000):
                    break

            self.repo.materialize_intervals(normalized)
            self.repo.update_ingestion_state(
                normalized,
                "1m",
                last_closed,
                status="success",
            )
            return {
                "symbol": normalized,
                "stored": stored,
                "pages": pages,
                "last_closed_open_time": last_closed,
            }
        except Exception as exc:
            self.repo.update_ingestion_state(
                normalized,
                "1m",
                last_closed,
                status="failed",
                last_error=str(exc),
            )
            raise

    def backfill_all(
        self,
        *,
        symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
        days: int = 365,
        page_limit: int = 1000,
    ) -> list[dict]:
        return [
            self.backfill_symbol(
                symbol,
                days=days,
                page_limit=page_limit,
            )
            for symbol in symbols
        ]
