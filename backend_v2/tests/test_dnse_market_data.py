from __future__ import annotations

import asyncio
import time
from datetime import date
from datetime import datetime

import httpx
import pytest

from src.services.dnse_market_data import (
    DnseMarketDataClient,
    normalize_historical_trade,
    normalize_latest_trade,
)
from src.database.data_lake import dump_ticks_to_parquet_for_date, read_ticks_from_parquet


@pytest.fixture
def anyio_backend():
    return "asyncio"


def test_normalize_latest_trade_treats_dnse_naive_time_as_vietnam_time():
    tick = normalize_latest_trade(
        "FPT",
        {
            "trades": [
                {
                    "symbol": "FPT",
                    "matchPrice": 76.9,
                    "matchQtty": 40,
                    "time": "2026-05-21 07:29:58",
                }
            ]
        },
    )

    assert tick["trade_time"] == "2026-05-21T00:29:58+00:00"
    assert tick["trade_time_local"] == "2026-05-21T07:29:58+07:00"
    assert datetime.fromisoformat(tick["trade_time_local"]).tzinfo is not None
    assert tick["price"] == 76.9
    assert tick["volume"] == 40


def test_normalize_latest_trade_maps_buy_side_fields():
    tick = normalize_latest_trade(
        "FPT",
        {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21", "side": "B"},
    )

    assert tick["match_type"] == "buy"
    assert tick["side_source"] == "dnse"
    assert tick["side_confidence"] == "source"


def test_normalize_latest_trade_maps_sell_side_fields():
    tick = normalize_latest_trade(
        "FPT",
        {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21", "matchType": "S"},
    )

    assert tick["match_type"] == "sell"
    assert tick["side_source"] == "dnse"
    assert tick["side_confidence"] == "source"


def test_normalize_latest_trade_marks_missing_side_unknown():
    tick = normalize_latest_trade(
        "FPT",
        {"matchPrice": 74.5, "matchQtty": 100, "time": "2026-05-29 10:20:21"},
    )

    assert tick["match_type"] == "unknown"
    assert tick["side_source"] == "missing"
    assert tick["side_confidence"] == "unknown"


def test_normalize_historical_trade_uses_intraday_tick_shape():
    tick = normalize_historical_trade(
        "FPT",
        {
            "symbol": "FPT",
            "matchPrice": 118.7,
            "matchQtty": 300,
            "time": "2026-06-08 14:45:02.802",
            "side": "BUY",
        },
    )

    assert tick == {
        "id": "dnse-historical|FPT|2026-06-08T14:45:02.802000+07:00|118.7|300",
        "symbol": "FPT",
        "time": "2026-06-08T14:45:02.802000+07:00",
        "price": 118.7,
        "volume": 300,
        "match_type": "buy",
        "side_source": "dnse",
        "side_confidence": "source",
        "source": "dnse_historical",
    }


def test_dump_and_read_ticks_for_explicit_session_date(tmp_path):
    ticks = [
        {
            "symbol": "FPT",
            "time": "2026-06-08T09:01:00+07:00",
            "price": 118.5,
            "volume": 100,
        }
    ]

    output = dump_ticks_to_parquet_for_date("FPT", ticks, date(2026, 6, 8), base_dir=tmp_path)
    loaded = read_ticks_from_parquet("FPT", date(2026, 6, 8), base_dir=tmp_path)

    assert output == tmp_path / "2026-06-08" / "FPT.parquet"
    assert loaded == ticks


@pytest.mark.anyio
async def test_get_latest_trades_reuses_client_and_fetches_concurrently(monkeypatch):
    request_started_at: list[float] = []

    async def fake_get(self, url, headers=None):
        request_started_at.append(time.perf_counter())
        await asyncio.sleep(0.15)
        symbol = url.split("/price/")[1].split("/")[0]
        return httpx.Response(
            200,
            json={
                "trades": [
                    {
                        "symbol": symbol,
                        "matchPrice": 10,
                        "matchQtty": 1,
                        "time": "2026-05-21 07:29:58",
                    }
                ]
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = DnseMarketDataClient(
        api_key="key",
        api_secret="secret",
        base_url="https://openapi.dnse.test",
        board_id="G1",
        timeout_seconds=2,
        max_concurrency=5,
    )

    response = await client.get_latest_trades(["FPT", "VCB", "VIC", "HPG", "SSI"])

    assert response["status"] == "ok"
    assert len(response["ticks"]) == 5
    assert response["errors"] == {}
    assert max(request_started_at) - min(request_started_at) < 0.12


@pytest.mark.anyio
async def test_get_historical_trades_paginates_with_from_to(monkeypatch):
    requested_urls: list[str] = []

    async def fake_get(self, url, headers=None):
        requested_urls.append(url)
        payload = (
            {
                "trades": [
                    {
                        "symbol": "FPT",
                        "matchPrice": 118.7,
                        "matchQtty": 300,
                        "time": "2026-06-08 14:45:02.802",
                        "side": "BUY",
                    }
                ],
                "nextPageToken": "page-2",
            }
            if len(requested_urls) == 1
            else {
                "trades": [
                    {
                        "symbol": "FPT",
                        "matchPrice": 118.8,
                        "matchQtty": 200,
                        "time": "2026-06-08 14:45:03.001",
                        "side": "SELL",
                    }
                ]
            }
        )
        return httpx.Response(200, json=payload, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    client = DnseMarketDataClient(
        api_key="key",
        api_secret="secret",
        base_url="https://openapi.dnse.test",
        board_id="G1",
        timeout_seconds=2,
    )

    ticks = await client.get_historical_trades("FPT", from_ts=1717812000, to_ts=1717833600, limit=1)

    assert [tick["price"] for tick in ticks] == [118.7, 118.8]
    assert "from=1717812000" in requested_urls[0]
    assert "to=1717833600" in requested_urls[0]
    assert "limit=1" in requested_urls[0]
    assert "order=ASC" in requested_urls[0]
    assert "nextPageToken=page-2" in requested_urls[1]
