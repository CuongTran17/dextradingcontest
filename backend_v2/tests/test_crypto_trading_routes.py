from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth import require_auth
from src.routes.crypto_trading import (
    get_account_service,
    get_contest_service,
    get_order_service,
    get_solana_join_service,
    router,
)
from src.services.solana_join import AdminWalletCannotJoinContestError


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
    "order_type": "market",
    "status": "filled",
    "requested_quantity": 1.0,
    "filled_quantity": 1.0,
    "average_fill_price": 3000.0,
    "executed_notional": 3000.0,
    "fee": 3.0,
    "created_at": "2026-06-25T00:00:00+00:00",
}

CONTEST = {
    "id": "practice-arena",
    "title": "Practice Arena",
    "status": "practice",
    "raw_status": "active",
    "mode": "practice",
    "initial_capital": 10000.0,
    "quote_asset": "USDT_TEST",
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "starts_at": "2026-06-01T00:00:00+00:00",
    "ends_at": "2026-07-01T00:00:00+00:00",
    "participant_count": 3,
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

    def place_order(self, **arguments):
        self.arguments = arguments
        return ORDER

    def cancel_order(self, **arguments):
        self.arguments = arguments
        return ORDER


class FakeContestService:
    def list_contests(self):
        return [CONTEST]

    def get_contest(self, slug):
        assert slug == "practice-arena"
        return CONTEST

    def get_leaderboard(self, slug, force_refresh=False):
        assert slug == "practice-arena"
        return [
            {
                "rank": 1,
                "user": "Student B",
                "equity": 11000.0,
                "pnl": 1000.0,
                "roi": 10.0,
                "volume": 2500.0,
                "trade_count": 1,
                "last_trade": "BTCUSDT buy",
            }
        ]


class FakeSolanaJoinService:
    def __init__(self):
        self.confirmed = None

    def get_wallet(self, user_id, contest_slug):
        return {
            "contest_id": contest_slug,
            "wallet_address": "So11111111111111111111111111111111111111112",
            "wallet_type": "solana",
            "join_tx_signature": "5" * 88,
            "joined_onchain_at": "2026-07-28T12:00:00+00:00",
        }

    def confirm_join(self, user_id, contest_slug, wallet_address, join_tx_signature):
        self.confirmed = {
            "user_id": user_id,
            "contest_slug": contest_slug,
            "wallet_address": wallet_address,
            "join_tx_signature": join_tx_signature,
        }
        return {
            "contest_id": contest_slug,
            "wallet_address": wallet_address,
            "wallet_type": "solana",
            "join_tx_signature": join_tx_signature,
            "joined_onchain_at": "2026-07-28T12:00:00+00:00",
        }


class FakeAdminWalletBlockedSolanaJoinService:
    def get_wallet(self, user_id, contest_slug):
        return {
            "contest_id": contest_slug,
            "wallet_address": None,
            "wallet_type": None,
            "join_tx_signature": None,
            "joined_onchain_at": None,
        }

    def confirm_join(self, user_id, contest_slug, wallet_address, join_tx_signature):
        raise AdminWalletCannotJoinContestError(
            "The admin wallet that initialized this contest cannot join it"
        )


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


def test_list_public_contests_does_not_require_auth():
    app, _order_service = _make_app()
    app.dependency_overrides[get_contest_service] = lambda: FakeContestService()
    client = TestClient(app)

    response = client.get("/api/crypto/contests")

    assert response.status_code == 200
    assert response.json() == [CONTEST]


def test_get_public_contest_detail_does_not_require_auth():
    app, _order_service = _make_app()
    app.dependency_overrides[get_contest_service] = lambda: FakeContestService()
    client = TestClient(app)

    response = client.get("/api/crypto/contests/practice-arena")

    assert response.status_code == 200
    assert response.json()["id"] == "practice-arena"


def test_get_public_contest_leaderboard_does_not_require_auth():
    app, _order_service = _make_app()
    app.dependency_overrides[get_contest_service] = lambda: FakeContestService()
    client = TestClient(app)

    response = client.get("/api/crypto/contests/practice-arena/leaderboard")

    assert response.status_code == 200
    assert response.json()[0]["equity"] == 11000.0


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
        "order_type": "market",
        "limit_price": None,
        "stop_loss_price": None,
        "take_profit_price": None,
    }


def test_solana_wallet_routes_return_bound_wallet_and_confirm_join():
    app, _order_service = _make_app(authenticated=True)
    service = FakeSolanaJoinService()
    app.dependency_overrides[get_solana_join_service] = lambda: service
    client = TestClient(app)

    wallet_response = client.get("/api/crypto/contests/summer-cup/wallet")
    assert wallet_response.status_code == 200
    assert wallet_response.json()["wallet_address"] == (
        "So11111111111111111111111111111111111111112"
    )

    confirm_response = client.post(
        "/api/crypto/contests/summer-cup/join/confirm",
        json={
            "wallet_address": "So11111111111111111111111111111111111111112",
            "join_tx_signature": "5" * 88,
        },
    )

    assert confirm_response.status_code == 200
    assert confirm_response.json()["wallet_type"] == "solana"
    assert service.confirmed == {
        "user_id": 3,
        "contest_slug": "summer-cup",
        "wallet_address": "So11111111111111111111111111111111111111112",
        "join_tx_signature": "5" * 88,
    }


def test_solana_join_confirm_returns_conflict_for_contest_admin_wallet():
    app, _order_service = _make_app(authenticated=True)
    app.dependency_overrides[get_solana_join_service] = (
        lambda: FakeAdminWalletBlockedSolanaJoinService()
    )
    client = TestClient(app)

    response = client.post(
        "/api/crypto/contests/summer-cup/join/confirm",
        json={
            "wallet_address": "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB",
            "join_tx_signature": "5" * 88,
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The admin wallet that initialized this contest cannot join it"
    )
