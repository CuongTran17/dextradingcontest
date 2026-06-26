from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest

from src.services.binance_realtime import (
    CandlePersistenceWorker,
    LocalOrderBook,
    OrderBookSynchronizer,
    build_combined_stream_url,
    normalize_kline_event,
    normalize_ticker_event,
)
from src.services.crypto_realtime_cache import RealtimeMarketCache


SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT"]


def test_combined_stream_url_contains_ticker_kline_and_depth_for_all_symbols():
    url = build_combined_stream_url(SYMBOLS)

    assert url.startswith("wss://data-stream.binance.vision/stream?streams=")
    for symbol in SYMBOLS:
        lower = symbol.lower()
        assert f"{lower}@miniTicker" in url
        assert f"{lower}@kline_1m" in url
        assert f"{lower}@depth@100ms" in url
    streams = url.removeprefix("wss://data-stream.binance.vision/stream?streams=").split("/")
    assert len(streams) == 15


def test_normalizes_ticker_and_kline_events():
    ticker = normalize_ticker_event(
        {"e": "24hrMiniTicker", "E": 1710000000000, "s": "ETHUSDT", "c": "1567.25"}
    )
    candle = normalize_kline_event(
        {
            "e": "kline",
            "E": 1710000060000,
            "s": "ETHUSDT",
            "k": {
                "t": 1710000000000,
                "T": 1710000059999,
                "i": "1m",
                "o": "1560.0",
                "h": "1570.0",
                "l": "1559.0",
                "c": "1567.25",
                "v": "12.5",
                "q": "19590.625",
                "n": 120,
                "V": "6.0",
                "Q": "9403.5",
                "x": True,
            },
        }
    )

    assert ticker.symbol == "ETHUSDT"
    assert ticker.price == 1567.25
    assert ticker.event_time_ms == 1710000000000
    assert candle.symbol == "ETHUSDT"
    assert candle.interval == "1m"
    assert candle.open_time == datetime(2024, 3, 9, 16, 0, tzinfo=timezone.utc)
    assert candle.is_closed is True
    assert candle.close == 1567.25
    assert candle.trade_count == 120


def test_realtime_cache_returns_immutable_price_and_orderbook_snapshots():
    cache = RealtimeMarketCache(SYMBOLS)
    cache.update_price("ETHUSDT", 1567.25, 1710000000000)
    book = LocalOrderBook("ETHUSDT", depth_limit=2)
    book.reset_from_snapshot(
        10,
        bids=[["1567.00", "1.5"], ["1566.50", "2.0"], ["1566.00", "3.0"]],
        asks=[["1567.50", "1.0"], ["1568.00", "2.0"], ["1568.50", "3.0"]],
    )
    cache.update_orderbook("ETHUSDT", book.snapshot())

    prices = cache.get_prices()
    prices["ETHUSDT"] = 1
    orderbook = cache.get_orderbook("ETHUSDT")
    assert orderbook is not None
    orderbook["bids"][0]["price"] = 1

    assert cache.get_prices()["ETHUSDT"] == 1567.25
    assert cache.get_orderbook("ETHUSDT")["bids"][0]["price"] == 1567.0


def test_local_orderbook_applies_updates_deletes_zero_quantities_and_trims_to_limit():
    book = LocalOrderBook("ETHUSDT", depth_limit=2)
    book.reset_from_snapshot(
        100,
        bids=[["100.0", "1"], ["99.0", "1"], ["98.0", "1"]],
        asks=[["101.0", "1"], ["102.0", "1"], ["103.0", "1"]],
    )

    book.apply_diff(
        first_update_id=101,
        final_update_id=101,
        bids=[["100.0", "0"], ["99.5", "2"]],
        asks=[["101.0", "3"], ["102.0", "0"], ["100.5", "1"]],
    )
    snapshot = book.snapshot()

    assert snapshot["last_update_id"] == 101
    assert snapshot["bids"] == [
        {"price": 99.5, "quantity": 2.0, "total": 199.0},
        {"price": 99.0, "quantity": 1.0, "total": 99.0},
    ]
    assert snapshot["asks"] == [
        {"price": 100.5, "quantity": 1.0, "total": 100.5},
        {"price": 101.0, "quantity": 3.0, "total": 303.0},
    ]
    assert snapshot["spread"] == 1.0
    assert snapshot["source"] == "binance-websocket"


def test_orderbook_synchronizer_bridges_snapshot_and_detects_sequence_gaps():
    async def snapshot_loader(_symbol: str):
        return {
            "lastUpdateId": 100,
            "bids": [["100.0", "1"]],
            "asks": [["101.0", "1"]],
        }

    sync = OrderBookSynchronizer("ETHUSDT", snapshot_loader=snapshot_loader, depth_limit=100)
    sync.buffer_event({"U": 98, "u": 99, "b": [["100.0", "2"]], "a": []})
    sync.buffer_event({"U": 100, "u": 101, "b": [["100.5", "1"]], "a": []})

    asyncio.run(sync.synchronize())

    assert sync.is_synced is True
    assert sync.snapshot()["last_update_id"] == 101
    assert sync.snapshot()["bids"][0]["price"] == 100.5

    sync.apply_event({"U": 103, "u": 103, "b": [], "a": []})

    assert sync.is_synced is False


def test_candle_persistence_worker_writes_only_closed_candles_and_materializes_intervals():
    class Repo:
        def __init__(self):
            self.upserts = []
            self.states = []
            self.materialized = []

        def upsert_candles(self, symbol, interval, rows, source="binance"):
            self.upserts.append((symbol, interval, list(rows), source))
            return len(self.upserts[-1][2])

        def update_ingestion_state(self, symbol, interval, last_closed_open_time, status, last_error=None):
            self.states.append((symbol, interval, last_closed_open_time, status, last_error))

        def materialize_intervals(self, symbol):
            self.materialized.append(symbol)
            return 4

    async def run_worker(repo):
        worker = CandlePersistenceWorker(repo=repo, max_queue_size=4)
        await worker.enqueue(
            normalize_kline_event(
                {
                    "e": "kline",
                    "E": 1710000060000,
                    "s": "ETHUSDT",
                    "k": {
                        "t": 1710000000000,
                        "T": 1710000059999,
                        "i": "1m",
                        "o": "1560.0",
                        "h": "1570.0",
                        "l": "1559.0",
                        "c": "1567.25",
                        "v": "12.5",
                        "q": "19590.625",
                        "n": 120,
                        "V": "6.0",
                        "Q": "9403.5",
                        "x": False,
                    },
                }
            )
        )
        await worker.enqueue(
            normalize_kline_event(
                {
                    "e": "kline",
                    "E": 1710000060000,
                    "s": "ETHUSDT",
                    "k": {
                        "t": 1710000000000,
                        "T": 1710000059999,
                        "i": "1m",
                        "o": "1560.0",
                        "h": "1570.0",
                        "l": "1559.0",
                        "c": "1567.25",
                        "v": "12.5",
                        "q": "19590.625",
                        "n": 120,
                        "V": "6.0",
                        "Q": "9403.5",
                        "x": True,
                    },
                }
            )
        )
        await worker.drain_once()

    repo = Repo()
    asyncio.run(run_worker(repo))

    assert len(repo.upserts) == 1
    assert repo.upserts[0][0:2] == ("ETHUSDT", "1m")
    assert repo.upserts[0][3] == "binance-websocket"
    assert repo.states[0][0:2] == ("ETHUSDT", "1m")
    assert repo.states[0][3] == "ok"
    assert repo.materialized == ["ETHUSDT"]
