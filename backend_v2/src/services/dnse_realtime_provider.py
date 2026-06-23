from __future__ import annotations

import time
from typing import Any, Protocol

from src.services.dnse_market_data import get_dnse_market_client
from src.services.vnstock_fetcher import fetcher_service, is_vn30_symbol, normalize_symbol
from src.settings import get_settings


class DnseMarketClientProtocol(Protocol):
    is_configured: bool

    async def get_latest_trades(self, symbols: list[str]) -> dict[str, Any]:
        ...


class RealtimeFetcherProtocol(Protocol):
    async def ingest_realtime_quotes(self, quotes: list[dict[str, Any]]) -> int:
        ...


class DnseRealtimeProvider:
    def __init__(
        self,
        *,
        market_client: DnseMarketClientProtocol | None = None,
        fetcher: RealtimeFetcherProtocol | None = None,
        enabled: bool | None = None,
        cache_ttl_seconds: float | None = None,
    ) -> None:
        settings = get_settings()
        self.market_client = market_client or get_dnse_market_client()
        self.fetcher = fetcher or fetcher_service
        self.enabled = settings.dnse_realtime_enabled if enabled is None else enabled
        self.cache_ttl_seconds = (
            settings.dnse_realtime_cache_ttl_seconds
            if cache_ttl_seconds is None
            else cache_ttl_seconds
        )
        self._last_refresh_at: dict[str, float] = {}

    def _normalize_symbols(self, symbols: list[str]) -> list[str]:
        output: list[str] = []
        for symbol in symbols:
            normalized = normalize_symbol(symbol)
            if normalized and normalized not in output and is_vn30_symbol(normalized):
                output.append(normalized)
        return output

    def _uncached_symbols(self, symbols: list[str], now: float) -> list[str]:
        if self.cache_ttl_seconds <= 0:
            return symbols
        return [
            symbol
            for symbol in symbols
            if now - self._last_refresh_at.get(symbol, 0.0) >= self.cache_ttl_seconds
        ]

    def tick_to_quote(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        symbol = normalize_symbol(str(tick.get("symbol", "")))
        price = tick.get("price")
        if not symbol or price is None:
            return None

        return {
            "symbol": symbol,
            "price": price,
            "volume": tick.get("volume") or 0,
            "time": tick.get("trade_time_local") or tick.get("trade_time"),
            "match_type": tick.get("match_type") or "unknown",
            "side_source": tick.get("side_source") or "missing",
            "side_confidence": tick.get("side_confidence") or "unknown",
            "source": "dnse",
        }

    def _tick_to_quote(self, tick: dict[str, Any]) -> dict[str, Any] | None:
        return self.tick_to_quote(tick)

    async def refresh_symbols(self, symbols: list[str], *, in_session: bool) -> dict[str, Any]:
        requested = self._normalize_symbols(symbols)
        if not requested:
            return {"status": "skipped", "reason": "no_valid_symbols", "requested_symbols": []}
        if not self.enabled:
            return {"status": "disabled", "requested_symbols": requested}
        if not in_session:
            return {"status": "market_closed", "requested_symbols": requested}
        if not self.market_client.is_configured:
            return {"status": "not_configured", "requested_symbols": requested}

        now = time.monotonic()
        uncached = self._uncached_symbols(requested, now)
        if not uncached:
            return {
                "status": "cached",
                "requested_symbols": requested,
                "fetched_count": 0,
                "ingested_count": 0,
            }

        response = await self.market_client.get_latest_trades(uncached)
        ticks = list(response.get("ticks") or [])
        quotes = [
            quote
            for tick in ticks
            if (quote := self.tick_to_quote(tick)) is not None
        ]
        ingested_count = await self.fetcher.ingest_realtime_quotes(quotes) if quotes else 0

        refreshed_at = time.monotonic()
        for quote in quotes:
            self._last_refresh_at[str(quote["symbol"])] = refreshed_at

        return {
            "status": "ok" if ticks else "error",
            "requested_symbols": requested,
            "fetched_symbols": uncached,
            "fetched_count": len(ticks),
            "ingested_count": ingested_count,
            "errors": response.get("errors") or {},
            "latency_ms": response.get("latency_ms"),
        }


dnse_realtime_provider = DnseRealtimeProvider()
