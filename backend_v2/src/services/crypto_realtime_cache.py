from __future__ import annotations

import copy
import threading
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any


class RealtimeMarketCache:
    def __init__(self, symbols: list[str]):
        self._symbols = [symbol.upper() for symbol in symbols]
        self._prices: dict[str, float] = {}
        self._price_times: dict[str, int] = {}
        self._candles: dict[str, dict[str, Any]] = {}
        self._orderbooks: dict[str, dict[str, Any]] = {}
        self._status: dict[str, Any] = {
            "status": "starting",
            "connected_at": None,
            "last_event_at": None,
            "reconnect_count": 0,
            "symbols": {
                symbol: {
                    "orderbook_synced": False,
                    "last_price_at": None,
                    "last_candle_at": None,
                }
                for symbol in self._symbols
            },
        }
        self._lock = threading.RLock()

    def update_price(self, symbol: str, price: float, event_time_ms: int) -> None:
        normalized = symbol.upper()
        with self._lock:
            self._prices[normalized] = float(price)
            self._price_times[normalized] = int(event_time_ms)
            self._status["last_event_at"] = int(event_time_ms)
            self._symbol_status(normalized)["last_price_at"] = int(event_time_ms)

    def update_candle(self, candle: Any) -> None:
        payload = asdict(candle) if hasattr(candle, "__dataclass_fields__") else dict(candle)
        normalized = str(payload["symbol"]).upper()
        payload["symbol"] = normalized
        with self._lock:
            self._candles[normalized] = copy.deepcopy(payload)
            self._status["last_event_at"] = int(payload["event_time_ms"])
            self._symbol_status(normalized)["last_candle_at"] = int(
                payload["open_time"].timestamp() * 1000
                if isinstance(payload["open_time"], datetime)
                else payload["event_time_ms"]
            )

    def update_orderbook(self, symbol: str, snapshot: dict[str, Any]) -> None:
        normalized = symbol.upper()
        with self._lock:
            self._orderbooks[normalized] = copy.deepcopy(snapshot)
            self._symbol_status(normalized)["orderbook_synced"] = True

    def mark_orderbook_unsynced(self, symbol: str) -> None:
        normalized = symbol.upper()
        with self._lock:
            self._symbol_status(normalized)["orderbook_synced"] = False

    def mark_connected(self, event_time_ms: int | None = None) -> None:
        now_ms = event_time_ms or int(datetime.now(timezone.utc).timestamp() * 1000)
        with self._lock:
            self._status["status"] = "connected"
            self._status["connected_at"] = now_ms
            self._status["last_event_at"] = now_ms

    def mark_reconnecting(self) -> None:
        with self._lock:
            self._status["status"] = "reconnecting"
            self._status["reconnect_count"] = int(self._status["reconnect_count"]) + 1

    def mark_stopped(self) -> None:
        with self._lock:
            self._status["status"] = "stopped"

    def get_prices(self) -> dict[str, float]:
        with self._lock:
            return dict(self._prices)

    def get_candle(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            candle = self._candles.get(symbol.upper())
            return copy.deepcopy(candle) if candle is not None else None

    def get_orderbook(self, symbol: str) -> dict[str, Any] | None:
        with self._lock:
            orderbook = self._orderbooks.get(symbol.upper())
            return copy.deepcopy(orderbook) if orderbook is not None else None

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "prices": dict(self._prices),
                "connection": copy.deepcopy(self._status),
            }

    def status(self) -> dict[str, Any]:
        with self._lock:
            return copy.deepcopy(self._status)

    def _symbol_status(self, symbol: str) -> dict[str, Any]:
        return self._status["symbols"].setdefault(
            symbol,
            {
                "orderbook_synced": False,
                "last_price_at": None,
                "last_candle_at": None,
            },
        )
