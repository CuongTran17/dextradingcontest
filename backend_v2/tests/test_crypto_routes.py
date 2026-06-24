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
