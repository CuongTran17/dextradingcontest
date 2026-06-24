from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import require_auth
from src.routes.crypto_trading import (
    get_account_service,
    get_order_service,
    router,
)


ACCOUNT = {
    "account_id": 9,
    "contest_id": "practice-arena",
    "status": "active",
    "cash": 10000.0,
    "initial_equity": 10000.0,
    "equity": 10000.0,
    "realized_pnl": 0.0,
    "unrealized_pnl": 0.0,
    "positions": [],
    "orders": [],
}

ORDER = {
    "order_id": 12,
    "client_order_id": "web-001",
    "symbol": "ETHUSDT",
    "side": "buy",
    "status": "filled",
    "filled_quantity": 1.0,
    "average_fill_price": 3000.0,
    "executed_notional": 3000.0,
    "fee": 3.0,
    "created_at": "2026-06-25T00:00:00+00:00",
}


class FakeAccountService:
    def join_contest(self, user_id, contest_slug):
        assert user_id == 3
        assert contest_slug == "practice-arena"
        return ACCOUNT

    def get_account(self, user_id, contest_slug):
        assert user_id == 3
        assert contest_slug == "practice-arena"
        return ACCOUNT


class FakeOrderService:
    def __init__(self):
        self.arguments = None

    def place_market_order(self, **arguments):
        self.arguments = arguments
        return ORDER


def _make_app(authenticated=False):
    app = FastAPI()
    app.include_router(router)
    account_service = FakeAccountService()
    order_service = FakeOrderService()
    app.dependency_overrides[get_account_service] = lambda: account_service
    app.dependency_overrides[get_order_service] = lambda: order_service
    if authenticated:
        app.dependency_overrides[require_auth] = lambda: SimpleNamespace(id=3)
    return app, order_service


def test_join_contest_requires_auth():
    app, _order_service = _make_app()
    client = TestClient(app)

    response = client.post("/api/crypto/contests/practice-arena/join")

    assert response.status_code == 401


def test_join_contest_returns_persistent_account():
    app, _order_service = _make_app(authenticated=True)
    client = TestClient(app)

    response = client.post("/api/crypto/contests/practice-arena/join")

    assert response.status_code == 200
    assert response.json()["contest_id"] == "practice-arena"
    assert response.json()["cash"] == 10000.0


def test_market_order_does_not_pass_client_portfolio_to_service():
    app, order_service = _make_app(authenticated=True)
    client = TestClient(app)

    response = client.post(
        "/api/crypto/orders/market",
        json={
            "contest_id": "practice-arena",
            "client_order_id": "web-001",
            "symbol": "ETHUSDT",
            "side": "buy",
            "quantity": 1,
            "portfolio": {"cash": 999999999},
        },
    )

    assert response.status_code == 200
    assert order_service.arguments == {
        "user_id": 3,
        "contest_slug": "practice-arena",
        "client_order_id": "web-001",
        "symbol": "ETHUSDT",
        "side": "buy",
        "quantity": 1,
    }
