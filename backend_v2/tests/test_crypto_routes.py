from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.crypto import router


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_assets_include_all_supported_spot_symbols():
    client = make_client()

    response = client.get("/api/crypto/assets")

    assert response.status_code == 200
    assert {asset["symbol"] for asset in response.json()} == {
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "BNBUSDT",
    }


def test_orderbook_returns_market_depth(monkeypatch):
    from src.routes import crypto

    monkeypatch.setattr(
        crypto,
        "get_binance_order_book",
        lambda symbol, limit: {
            "symbol": symbol,
            "last_update_id": 123,
            "bids": [{"price": 100.0, "quantity": 1.0, "total": 100.0}],
            "asks": [{"price": 101.0, "quantity": 1.0, "total": 101.0}],
            "spread": 1.0,
            "mid_price": 100.5,
            "source": "binance",
        },
    )
    client = make_client()

    response = client.get("/api/crypto/orderbook?symbol=BTCUSDT&limit=20")

    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "binance"
    assert body["bids"][0]["price"] == 100.0
    assert body["asks"][0]["price"] == 101.0


def test_candles_use_duckdb_before_binance(monkeypatch):
    from src.routes import crypto

    expected = [
        {
            "time": 1,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 10.0,
        }
    ]
    monkeypatch.setattr(
        crypto.crypto_market_repo,
        "load_candles",
        lambda symbol, interval, *, limit: expected,
    )
    monkeypatch.setattr(
        crypto,
        "get_binance_candles",
        lambda *args: (_ for _ in ()).throw(AssertionError("Binance should not be called")),
    )
    client = make_client()

    response = client.get("/api/crypto/candles?symbol=BTCUSDT&timeframe=1m&limit=10")

    assert response.status_code == 200
    assert response.json() == expected


def test_latest_prices_fall_back_to_latest_duckdb_closes(monkeypatch):
    from src.routes import crypto

    monkeypatch.setattr(
        crypto,
        "get_binance_latest_prices",
        lambda symbols: (_ for _ in ()).throw(RuntimeError("Binance unavailable")),
    )
    monkeypatch.setattr(
        crypto.crypto_market_repo,
        "load_candles",
        lambda symbol, interval, *, limit: [
            {
                "time": 1,
                "open": 1500.0,
                "high": 1510.0,
                "low": 1490.0,
                "close": 1505.0 if symbol == "ETHUSDT" else 100.0,
                "volume": 10.0,
            }
        ],
    )
    client = make_client()

    response = client.get("/api/crypto/prices/latest")

    assert response.status_code == 200
    assert response.json()["ETHUSDT"] == 1505.0


def test_orderbook_returns_503_instead_of_mock_depth(monkeypatch):
    from src.routes import crypto

    monkeypatch.setattr(
        crypto,
        "get_binance_order_book",
        lambda symbol, limit: (_ for _ in ()).throw(RuntimeError("Binance unavailable")),
    )
    client = make_client()

    response = client.get("/api/crypto/orderbook?symbol=ETHUSDT&limit=20")

    assert response.status_code == 503
