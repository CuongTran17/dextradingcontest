from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.crypto import router


def make_client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_assets_include_btcusdt():
    client = make_client()

    response = client.get("/api/crypto/assets")

    assert response.status_code == 200
    assert any(asset["symbol"] == "BTCUSDT" for asset in response.json())


def test_market_order_executes_virtual_eth_buy():
    client = make_client()

    response = client.post(
      "/api/crypto/orders/market",
      json={
        "portfolio": {"contest_id": "practice-arena", "cash": 10000.0, "positions": [], "orders": []},
        "symbol": "ETHUSDT",
        "side": "buy",
        "quantity": 1.0,
      },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["portfolio"]["positions"][0]["symbol"] == "ETHUSDT"
    assert body["metrics"]["trade_count"] == 1
