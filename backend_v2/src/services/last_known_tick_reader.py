from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from src.database.data_lake import read_latest_tick_from_parquet
from src.services.vnstock_fetcher import fetcher_service, normalize_symbol


@dataclass
class LastKnownTickResult:
    ticks: list[dict[str, Any]]
    missing_symbols: list[str]


class LastKnownTickReader:
    def __init__(
        self,
        *,
        fetcher=fetcher_service,
        parquet_reader: Callable[[str], dict[str, Any] | None] = read_latest_tick_from_parquet,
    ) -> None:
        self.fetcher = fetcher
        self.parquet_reader = parquet_reader

    def read(self, symbols: list[str]) -> LastKnownTickResult:
        requested = [normalize_symbol(symbol) for symbol in symbols if normalize_symbol(symbol)]
        cache = self.fetcher.get_intraday_cache_view(symbols=requested, limit=1)
        ticks: list[dict[str, Any]] = []
        missing_symbols: list[str] = []

        for symbol in requested:
            cached = (cache.get(symbol) or [None])[0]
            tick = self._normalize(cached, symbol, "cache") if cached else None
            if tick is None:
                parquet_tick = self.parquet_reader(symbol)
                tick = self._normalize(parquet_tick, symbol, "parquet") if parquet_tick else None

            if tick is None:
                missing_symbols.append(symbol)
            else:
                ticks.append(tick)

        return LastKnownTickResult(ticks=ticks, missing_symbols=missing_symbols)

    def _normalize(self, tick: dict[str, Any], symbol: str, storage_source: str) -> dict[str, Any] | None:
        price = tick.get("price")
        if price is None:
            return None

        trade_time = tick.get("trade_time") or tick.get("time")
        trade_time_local = tick.get("trade_time_local") or trade_time
        return {
            "symbol": normalize_symbol(str(tick.get("symbol") or symbol)),
            "price": price,
            "volume": tick.get("volume"),
            "trade_time": trade_time,
            "trade_time_local": trade_time_local,
            "trade_time_raw": tick.get("trade_time_raw") or trade_time,
            "match_type": tick.get("match_type") or "unknown",
            "side_source": tick.get("side_source") or "missing",
            "side_confidence": tick.get("side_confidence") or "unknown",
            "source": "dnse",
            "storage_source": storage_source,
        }


last_known_tick_reader = LastKnownTickReader()
