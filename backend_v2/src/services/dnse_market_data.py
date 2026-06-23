from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from datetime import date, datetime, time as datetime_time, timezone
from typing import Any
from urllib import parse
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx

try:
    from src.settings import get_settings
except ModuleNotFoundError:
    from backend_v2.src.settings import get_settings


class DnseMarketDataConfigError(RuntimeError):
    """Raised when DNSE market data credentials are missing."""


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def build_signature(
    *,
    secret: str,
    method: str,
    path: str,
    date_value: str,
    algorithm: str = "hmac-sha256",
    nonce: str | None = None,
    header_name: str = "Date",
) -> tuple[str, str]:
    header_key = header_name.lower()
    headers = f"(request-target) {header_key}"
    signature_string = f"(request-target): {method.lower()} {path}\n{header_key}: {date_value}"
    if nonce:
        signature_string += f"\nnonce: {nonce}"

    digestmod = {
        "hmac-sha256": hashlib.sha256,
        "hmac-sha384": hashlib.sha384,
        "hmac-sha512": hashlib.sha512,
    }.get(algorithm, hashlib.sha1)
    mac = hmac.new(secret.encode("utf-8"), signature_string.encode("utf-8"), digestmod)
    encoded = base64.b64encode(mac.digest()).decode("utf-8")
    return headers, parse.quote(encoded, safe="")


def _first_number(raw: dict[str, Any], keys: tuple[str, ...]) -> float | None:
    for key in keys:
        value = raw.get(key)
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_text(raw: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = raw.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return None


def _normalize_side(raw: dict[str, Any]) -> tuple[str, str, str]:
    text = _first_text(raw, ("side", "matchType", "match_type", "tradeType", "bsType", "type"))
    value = (text or "").strip().lower()
    buy_values = {"b", "buy", "bu", "mua", "bid"}
    sell_values = {"s", "sell", "sd", "ban", "bán", "ask"}
    if value in buy_values:
        return "buy", "dnse", "source"
    if value in sell_values:
        return "sell", "dnse", "source"
    return "unknown", "missing", "unknown"


def _normalize_dnse_trade_time(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    raw = str(value).strip()
    if not raw:
        return None, None

    try:
        if raw.endswith("Z"):
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(raw)
    except ValueError:
        try:
            parsed = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return raw, raw

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=VN_TZ)

    utc_value = parsed.astimezone(timezone.utc).isoformat()
    local_value = parsed.astimezone(VN_TZ).isoformat()
    return utc_value, local_value


def normalize_latest_trade(symbol: str, raw: dict[str, Any]) -> dict[str, Any]:
    trade = raw
    wrapped_trades = raw.get("trades")
    if isinstance(wrapped_trades, list) and wrapped_trades and isinstance(wrapped_trades[0], dict):
        trade = wrapped_trades[0]

    price = _first_number(trade, ("price", "matchedPrice", "lastPrice", "matchPrice", "p"))
    volume = _first_number(trade, ("volume", "matchedVolume", "matchVolume", "matchQtty", "vol", "v"))
    trade_time_raw = _first_text(trade, ("time", "tradeTime", "tradingTime", "createdAt", "t"))
    trade_time, trade_time_local = _normalize_dnse_trade_time(trade_time_raw)
    match_type, side_source, side_confidence = _normalize_side(trade)
    return {
        "symbol": symbol.strip().upper(),
        "price": price,
        "volume": int(volume) if volume is not None else None,
        "trade_time": trade_time,
        "trade_time_local": trade_time_local,
        "trade_time_raw": trade_time_raw,
        "match_type": match_type,
        "side_source": side_source,
        "side_confidence": side_confidence,
        "source": "dnse",
        "raw": raw,
    }


def normalize_historical_trade(symbol: str, raw: dict[str, Any]) -> dict[str, Any] | None:
    normalized = symbol.strip().upper()
    price = _first_number(raw, ("price", "matchedPrice", "lastPrice", "matchPrice", "p"))
    volume = _first_number(raw, ("volume", "matchedVolume", "matchVolume", "matchQtty", "vol", "v"))
    trade_time_raw = _first_text(raw, ("time", "tradeTime", "tradingTime", "createdAt", "t"))
    _trade_time, trade_time_local = _normalize_dnse_trade_time(trade_time_raw)
    if price is None or volume is None or not trade_time_local:
        return None

    match_type, side_source, side_confidence = _normalize_side(raw)
    volume_int = int(volume)
    return {
        "id": f"dnse-historical|{normalized}|{trade_time_local}|{price}|{volume_int}",
        "symbol": normalized,
        "time": trade_time_local,
        "price": price,
        "volume": volume_int,
        "match_type": match_type,
        "side_source": side_source,
        "side_confidence": side_confidence,
        "source": "dnse_historical",
    }


class DnseMarketDataClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        api_secret: str | None = None,
        base_url: str | None = None,
        board_id: str | None = None,
        timeout_seconds: float = 10.0,
        max_concurrency: int | None = None,
    ):
        settings = get_settings()
        self.api_key = (api_key if api_key is not None else settings.dnse_market_api_key).strip()
        self.api_secret = (api_secret if api_secret is not None else settings.dnse_market_api_secret).strip()
        self.base_url = (base_url or settings.dnse_market_base_url).rstrip("/")
        self.board_id = (board_id if board_id is not None else settings.dnse_market_board_id).strip()
        self.timeout_seconds = timeout_seconds
        configured_concurrency = getattr(settings, "dnse_realtime_max_concurrency", 8)
        self.max_concurrency = max(1, int(max_concurrency or configured_concurrency))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_secret)

    def latest_trade_url(self, symbol: str) -> str:
        normalized = symbol.strip().upper()
        path = f"/price/{parse.quote(normalized, safe='')}/trades/latest"
        query = {"boardId": self.board_id} if self.board_id else None
        if query:
            return f"{self.base_url}{path}?{parse.urlencode(query)}"
        return f"{self.base_url}{path}"

    def build_headers(self, method: str, path: str) -> dict[str, str]:
        if not self.is_configured:
            raise DnseMarketDataConfigError("DNSE market data credentials are not configured.")

        date_value = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S %z")
        nonce = uuid4().hex
        headers_list, signature = build_signature(
            secret=self.api_secret,
            method=method,
            path=path,
            date_value=date_value,
            nonce=nonce,
        )
        signature_header = (
            f'Signature keyId="{self.api_key}",algorithm="hmac-sha256",'
            f'headers="{headers_list}",signature="{signature}",nonce="{nonce}"'
        )
        return {
            "Date": date_value,
            "X-Signature": signature_header,
            "x-api-key": self.api_key,
        }

    async def get_latest_trade(
        self,
        symbol: str,
        client: httpx.AsyncClient | None = None,
    ) -> dict[str, Any]:
        normalized = symbol.strip().upper()
        path = f"/price/{parse.quote(normalized, safe='')}/trades/latest"
        url = self.latest_trade_url(normalized)
        headers = self.build_headers("GET", path)
        started = time.perf_counter()
        if client is None:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as scoped_client:
                response = await scoped_client.get(url, headers=headers)
        else:
            response = await client.get(url, headers=headers)
        latency_ms = round((time.perf_counter() - started) * 1000, 1)
        response.raise_for_status()
        raw = response.json()
        if not isinstance(raw, dict):
            raw = {"data": raw}
        tick = normalize_latest_trade(normalized, raw)
        tick["latency_ms"] = latency_ms
        return tick

    async def get_latest_trades(self, symbols: list[str]) -> dict[str, Any]:
        requested_symbols: list[str] = []
        for symbol in symbols:
            normalized = symbol.strip().upper()
            if normalized and normalized not in requested_symbols:
                requested_symbols.append(normalized)

        ticks: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        started = time.perf_counter()
        semaphore = asyncio.Semaphore(self.max_concurrency)

        async def fetch_one(
            symbol: str,
            http_client: httpx.AsyncClient,
        ) -> tuple[str, dict[str, Any] | None, str | None]:
            try:
                async with semaphore:
                    return symbol, await self.get_latest_trade(symbol, client=http_client), None
            except Exception as exc:
                return symbol, None, str(exc)

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as http_client:
            results = await asyncio.gather(
                *(fetch_one(symbol, http_client) for symbol in requested_symbols),
            )

        for symbol, tick, error in results:
            if tick is not None:
                ticks.append(tick)
            elif error:
                errors[symbol] = error

        return {
            "status": "ok" if ticks else "error",
            "source": "dnse",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "symbols": requested_symbols,
            "ticks": ticks,
            "errors": errors,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
        }

    async def get_historical_trades(
        self,
        symbol: str,
        *,
        from_ts: int,
        to_ts: int,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        normalized = symbol.strip().upper()
        path = f"/price/{parse.quote(normalized, safe='')}/trades"
        ticks: list[dict[str, Any]] = []
        next_page_token: str | None = None

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            while True:
                query: dict[str, Any] = {
                    "boardId": self.board_id,
                    "from": int(from_ts),
                    "to": int(to_ts),
                    "limit": int(limit),
                    "order": "ASC",
                }
                if next_page_token:
                    query["nextPageToken"] = next_page_token
                url = f"{self.base_url}{path}?{parse.urlencode(query)}"
                response = await client.get(url, headers=self.build_headers("GET", path))
                response.raise_for_status()
                raw = response.json()
                if not isinstance(raw, dict):
                    break

                trades = raw.get("trades") or raw.get("data") or raw.get("items") or []
                if not isinstance(trades, list):
                    break
                for trade in trades:
                    if not isinstance(trade, dict):
                        continue
                    tick = normalize_historical_trade(normalized, trade)
                    if tick is not None:
                        ticks.append(tick)

                next_page_token = raw.get("nextPageToken") or raw.get("next_page_token")
                if not next_page_token or not trades:
                    break

        return ticks

    async def get_historical_trades_for_session(
        self,
        symbol: str,
        session_date: date,
        *,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        start = datetime.combine(session_date, datetime_time(hour=9), tzinfo=VN_TZ)
        end = datetime.combine(session_date, datetime_time(hour=15), tzinfo=VN_TZ)
        return await self.get_historical_trades(
            symbol,
            from_ts=int(start.timestamp()),
            to_ts=int(end.timestamp()),
            limit=limit,
        )


def get_dnse_market_client() -> DnseMarketDataClient:
    return DnseMarketDataClient()
