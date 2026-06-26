from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

import httpx
import websockets
from starlette.websockets import WebSocket, WebSocketDisconnect

from src.database.crypto_market_duckdb import crypto_market_repo
from src.services.crypto_realtime_cache import RealtimeMarketCache


BINANCE_WS_BASE_URL = "wss://data-stream.binance.vision/stream?streams="
BINANCE_REST_BASE_URL = "https://data-api.binance.vision"
DEFAULT_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickerEvent:
    symbol: str
    price: float
    event_time_ms: int


@dataclass(frozen=True)
class KlineEvent:
    symbol: str
    interval: str
    event_time_ms: int
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float
    trade_count: int
    taker_buy_base_volume: float
    taker_buy_quote_volume: float
    is_closed: bool

    def to_duckdb_row(self) -> dict[str, Any]:
        return {
            "open_time": self.open_time,
            "close_time": self.close_time,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "quote_volume": self.quote_volume,
            "trade_count": self.trade_count,
            "taker_buy_base_volume": self.taker_buy_base_volume,
            "taker_buy_quote_volume": self.taker_buy_quote_volume,
            "is_closed": self.is_closed,
        }


def build_combined_stream_url(symbols: list[str]) -> str:
    streams: list[str] = []
    for symbol in symbols:
        lower = symbol.lower()
        streams.extend(
            [
                f"{lower}@miniTicker",
                f"{lower}@kline_1m",
                f"{lower}@depth@100ms",
            ]
        )
    return BINANCE_WS_BASE_URL + "/".join(streams)


def normalize_ticker_event(payload: dict[str, Any]) -> TickerEvent:
    return TickerEvent(
        symbol=str(payload["s"]).upper(),
        price=float(payload["c"]),
        event_time_ms=int(payload["E"]),
    )


def normalize_kline_event(payload: dict[str, Any]) -> KlineEvent:
    kline = payload["k"]
    return KlineEvent(
        symbol=str(payload["s"]).upper(),
        interval=str(kline["i"]),
        event_time_ms=int(payload["E"]),
        open_time=_from_milliseconds(kline["t"]),
        close_time=_from_milliseconds(kline["T"]),
        open=float(kline["o"]),
        high=float(kline["h"]),
        low=float(kline["l"]),
        close=float(kline["c"]),
        volume=float(kline["v"]),
        quote_volume=float(kline.get("q", 0)),
        trade_count=int(kline.get("n", 0)),
        taker_buy_base_volume=float(kline.get("V", 0)),
        taker_buy_quote_volume=float(kline.get("Q", 0)),
        is_closed=bool(kline["x"]),
    )


class LocalOrderBook:
    def __init__(self, symbol: str, depth_limit: int = 100):
        self.symbol = symbol.upper()
        self.depth_limit = max(1, int(depth_limit))
        self.last_update_id: int | None = None
        self._bids: dict[float, float] = {}
        self._asks: dict[float, float] = {}

    def reset_from_snapshot(
        self,
        last_update_id: int,
        *,
        bids: list[list[str]],
        asks: list[list[str]],
    ) -> None:
        self.last_update_id = int(last_update_id)
        self._bids = _levels_to_map(bids)
        self._asks = _levels_to_map(asks)
        self._trim()

    def apply_diff(
        self,
        *,
        first_update_id: int,
        final_update_id: int,
        bids: list[list[str]],
        asks: list[list[str]],
    ) -> None:
        if self.last_update_id is not None and first_update_id > self.last_update_id + 1:
            raise ValueError("orderbook_sequence_gap")
        self._apply_levels(self._bids, bids)
        self._apply_levels(self._asks, asks)
        self.last_update_id = int(final_update_id)
        self._trim()

    def snapshot(self) -> dict[str, Any]:
        bid_rows = _sorted_levels(self._bids, reverse=True, limit=self.depth_limit)
        ask_rows = _sorted_levels(self._asks, reverse=False, limit=self.depth_limit)
        best_bid = bid_rows[0]["price"] if bid_rows else 0.0
        best_ask = ask_rows[0]["price"] if ask_rows else 0.0
        return {
            "symbol": self.symbol,
            "last_update_id": self.last_update_id,
            "bids": bid_rows,
            "asks": ask_rows,
            "spread": best_ask - best_bid if best_bid and best_ask else 0.0,
            "mid_price": (best_bid + best_ask) / 2 if best_bid and best_ask else 0.0,
            "source": "binance-websocket",
        }

    def _apply_levels(self, side: dict[float, float], levels: list[list[str]]) -> None:
        for raw_price, raw_quantity in levels:
            price = float(raw_price)
            quantity = float(raw_quantity)
            if quantity == 0:
                side.pop(price, None)
            else:
                side[price] = quantity

    def _trim(self) -> None:
        self._bids = {
            level["price"]: level["quantity"]
            for level in _sorted_levels(self._bids, reverse=True, limit=self.depth_limit)
        }
        self._asks = {
            level["price"]: level["quantity"]
            for level in _sorted_levels(self._asks, reverse=False, limit=self.depth_limit)
        }


class OrderBookSynchronizer:
    def __init__(
        self,
        symbol: str,
        *,
        snapshot_loader: Callable[[str], Awaitable[dict[str, Any]]],
        depth_limit: int = 100,
    ):
        self.symbol = symbol.upper()
        self._snapshot_loader = snapshot_loader
        self._book = LocalOrderBook(symbol, depth_limit=depth_limit)
        self._buffer: list[dict[str, Any]] = []
        self.is_synced = False

    def buffer_event(self, event: dict[str, Any]) -> None:
        self._buffer.append(event)

    async def synchronize(self) -> None:
        snapshot = await self._snapshot_loader(self.symbol)
        last_update_id = int(snapshot["lastUpdateId"])
        self._book.reset_from_snapshot(
            last_update_id,
            bids=snapshot.get("bids", []),
            asks=snapshot.get("asks", []),
        )
        buffered = [event for event in self._buffer if int(event["u"]) > last_update_id]
        self._buffer = []
        bridge_index = None
        for index, event in enumerate(buffered):
            if int(event["U"]) <= last_update_id + 1 <= int(event["u"]):
                bridge_index = index
                break
        if bridge_index is None:
            self.is_synced = True
            return
        for event in buffered[bridge_index:]:
            self.apply_event(event)
        self.is_synced = True

    def apply_event(self, event: dict[str, Any]) -> None:
        if not self.is_synced and self._book.last_update_id is None:
            self.buffer_event(event)
            return
        try:
            self._book.apply_diff(
                first_update_id=int(event["U"]),
                final_update_id=int(event["u"]),
                bids=event.get("b", []),
                asks=event.get("a", []),
            )
            self.is_synced = True
        except ValueError:
            self.is_synced = False
            self._buffer = [event]

    def snapshot(self) -> dict[str, Any]:
        return self._book.snapshot()


class CandlePersistenceWorker:
    def __init__(self, *, repo: Any, max_queue_size: int = 1000):
        self._repo = repo
        self._queue: asyncio.Queue[KlineEvent] = asyncio.Queue(maxsize=max_queue_size)

    async def enqueue(self, candle: KlineEvent) -> bool:
        if not candle.is_closed:
            return False
        try:
            self._queue.put_nowait(candle)
            return True
        except asyncio.QueueFull:
            return False

    async def drain_once(self) -> int:
        written = 0
        while not self._queue.empty():
            candle = self._queue.get_nowait()
            self._repo.upsert_candles(
                candle.symbol,
                candle.interval,
                [candle.to_duckdb_row()],
                source="binance-websocket",
            )
            self._repo.update_ingestion_state(
                candle.symbol,
                candle.interval,
                candle.open_time,
                status="ok",
            )
            self._repo.materialize_intervals(candle.symbol)
            self._queue.task_done()
            written += 1
        return written


class BinanceRealtimeService:
    def __init__(
        self,
        *,
        symbols: list[str] | None = None,
        repo: Any = crypto_market_repo,
        depth_limit: int = 100,
    ):
        self.symbols = [symbol.upper() for symbol in (symbols or DEFAULT_SYMBOLS)]
        self.cache = RealtimeMarketCache(self.symbols)
        self._repo = repo
        self._depth_limit = depth_limit
        self._persistence = CandlePersistenceWorker(repo=repo)
        self._syncs = {
            symbol: OrderBookSynchronizer(
                symbol,
                snapshot_loader=self._load_depth_snapshot,
                depth_limit=depth_limit,
            )
            for symbol in self.symbols
        }
        self._clients: set[WebSocket] = set()
        self._client_symbols: dict[WebSocket, str | None] = {}
        self._tasks: list[asyncio.Task[Any]] = []
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._tasks:
            return
        self.cache.mark_connected()
        self._stopping.clear()
        self._tasks = [
            asyncio.create_task(self._persistence_loop(), name="crypto-candle-persistence"),
            asyncio.create_task(self._stream_loop(), name="binance-spot-realtime"),
        ]

    async def stop(self) -> None:
        self._stopping.set()
        self.cache.mark_stopped()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks = []
        await self._persistence.drain_once()

    async def handle_client(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._clients.add(websocket)
        self._client_symbols[websocket] = None
        try:
            await websocket.send_json({"type": "snapshot", **self.cache.snapshot()})
            while True:
                message = await websocket.receive_json()
                await self._handle_client_message(websocket, message)
        except WebSocketDisconnect:
            pass
        finally:
            self._clients.discard(websocket)
            self._client_symbols.pop(websocket, None)

    def status(self) -> dict[str, Any]:
        return self.cache.status()

    async def _handle_client_message(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        if message.get("type") != "subscribe":
            await websocket.send_json({"type": "error", "message": "Unsupported realtime message"})
            return
        symbol = str(message.get("symbol", "")).upper()
        if symbol not in self.symbols:
            await websocket.send_json({"type": "error", "message": "Unsupported crypto symbol"})
            return
        self._client_symbols[websocket] = symbol
        candle = self.cache.get_candle(symbol)
        orderbook = self.cache.get_orderbook(symbol)
        if candle is not None:
            await websocket.send_json(_candle_message(candle))
        if orderbook is not None:
            await websocket.send_json({"type": "orderbook", **orderbook})

    async def _stream_loop(self) -> None:
        delay = 1.0
        while not self._stopping.is_set():
            try:
                async with websockets.connect(build_combined_stream_url(self.symbols), ping_interval=20) as socket:
                    self.cache.mark_connected()
                    delay = 1.0
                    async for raw_message in socket:
                        if self._stopping.is_set():
                            break
                        await self._process_raw_message(raw_message)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Binance realtime stream disconnected")
                self.cache.mark_reconnecting()
                await asyncio.sleep(delay + random.uniform(0, 0.25))
                delay = min(delay * 2, 30.0)

    async def _process_raw_message(self, raw_message: str | bytes) -> None:
        envelope = json.loads(raw_message)
        payload = envelope.get("data", envelope)
        event_type = payload.get("e")
        if event_type == "24hrMiniTicker":
            ticker = normalize_ticker_event(payload)
            self.cache.update_price(ticker.symbol, ticker.price, ticker.event_time_ms)
            await self._broadcast({"type": "prices", "prices": self.cache.get_prices(), "event_time": ticker.event_time_ms})
        elif event_type == "kline":
            candle = normalize_kline_event(payload)
            self.cache.update_price(candle.symbol, candle.close, candle.event_time_ms)
            self.cache.update_candle(candle)
            await self._persistence.enqueue(candle)
            await self._broadcast_to_symbol(candle.symbol, _candle_message(candle))
        elif event_type == "depthUpdate":
            symbol = str(payload["s"]).upper()
            sync = self._syncs[symbol]
            if not sync.is_synced:
                sync.buffer_event(payload)
                await sync.synchronize()
            else:
                sync.apply_event(payload)
            if sync.is_synced:
                snapshot = sync.snapshot()
                self.cache.update_orderbook(symbol, snapshot)
                await self._broadcast_to_symbol(symbol, {"type": "orderbook", **snapshot})
            else:
                self.cache.mark_orderbook_unsynced(symbol)

    async def _persistence_loop(self) -> None:
        while not self._stopping.is_set():
            await self._persistence.drain_once()
            await asyncio.sleep(0.25)

    async def _load_depth_snapshot(self, symbol: str) -> dict[str, Any]:
        async with httpx.AsyncClient(base_url=BINANCE_REST_BASE_URL, timeout=8.0) as client:
            response = await client.get("/api/v3/depth", params={"symbol": symbol, "limit": self._depth_limit})
            response.raise_for_status()
            return response.json()

    async def _broadcast(self, message: dict[str, Any]) -> None:
        clients = list(self._clients)
        if not clients:
            return
        await asyncio.gather(
            *(self._safe_send(client, message) for client in clients),
            return_exceptions=True,
        )

    async def _broadcast_to_symbol(self, symbol: str, message: dict[str, Any]) -> None:
        clients = [
            client
            for client in self._clients
            if self._client_symbols.get(client) == symbol
        ]
        if not clients:
            return
        await asyncio.gather(
            *(self._safe_send(client, message) for client in clients),
            return_exceptions=True,
        )

    async def _safe_send(self, websocket: WebSocket, message: dict[str, Any]) -> None:
        try:
            await websocket.send_json(message)
        except Exception:
            self._clients.discard(websocket)
            self._client_symbols.pop(websocket, None)


def _from_milliseconds(value: int | str) -> datetime:
    return datetime.fromtimestamp(int(value) / 1000, tz=timezone.utc)


def _candle_message(candle: KlineEvent | dict[str, Any]) -> dict[str, Any]:
    if isinstance(candle, KlineEvent):
        return {
            "type": "candle",
            "symbol": candle.symbol,
            "interval": candle.interval,
            "closed": candle.is_closed,
            "candle": {
                "time": int(candle.open_time.timestamp()),
                "open": candle.open,
                "high": candle.high,
                "low": candle.low,
                "close": candle.close,
                "volume": candle.volume,
            },
        }
    open_time = candle["open_time"]
    if isinstance(open_time, datetime):
        time_value = int(open_time.timestamp())
    else:
        time_value = int(open_time)
    return {
        "type": "candle",
        "symbol": candle["symbol"],
        "interval": candle["interval"],
        "closed": candle["is_closed"],
        "candle": {
            "time": time_value,
            "open": candle["open"],
            "high": candle["high"],
            "low": candle["low"],
            "close": candle["close"],
            "volume": candle["volume"],
        },
    }


def _levels_to_map(levels: list[list[str]]) -> dict[float, float]:
    return {
        float(price): float(quantity)
        for price, quantity in levels
        if float(quantity) > 0
    }


def _sorted_levels(side: dict[float, float], *, reverse: bool, limit: int) -> list[dict[str, float]]:
    return [
        {"price": price, "quantity": quantity, "total": price * quantity}
        for price, quantity in sorted(side.items(), reverse=reverse)[:limit]
    ]
