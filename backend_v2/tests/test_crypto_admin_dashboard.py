from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradingAccount,
    TradingOrder,
)
from src.database.user_models import User
from src.api import admin
from src.repositories.crypto_trading import CryptoTradingRepository
from src.services.crypto_admin_dashboard import CryptoAdminDashboardService


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_for_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def seed_account(db_session):
    user = User(
        id=1,
        email="student@example.com",
        password_hash="hash",
        fullname="Student One",
        role="user",
    )
    btc = CryptoAsset(
        id=1,
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=6,
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        is_active=True,
    )
    contest = Contest(
        id=1,
        slug="practice-arena",
        title="Practice Arena",
        mode="practice",
        status="active",
        initial_balance=Decimal("10000"),
        quote_asset="USDT_TEST",
        fee_rate=Decimal("0.001"),
        rules_json="{}",
    )
    participant = ContestParticipant(
        id=1,
        contest_id=1,
        user_id=1,
        status="active",
    )
    account = TradingAccount(
        id=1,
        contest_participant_id=1,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10100"),
        realized_pnl=Decimal("100"),
        unrealized_pnl=Decimal("0"),
    )
    account.balances.append(
        AccountBalance(
            id=1,
            asset="USDT_TEST",
            available=Decimal("9500"),
            locked=Decimal("100"),
        )
    )
    account.positions.append(
        Position(
            id=1,
            asset=btc,
            quantity=Decimal("0.01"),
            average_entry_price=Decimal("50000"),
            cost_basis=Decimal("500"),
            realized_pnl=Decimal("0"),
        )
    )
    account.orders.append(
        TradingOrder(
            id=1,
            client_order_id="web-1",
            asset=btc,
            side="buy",
            order_type="market",
            status="filled",
            requested_quantity=Decimal("0.01"),
            filled_quantity=Decimal("0.01"),
            average_fill_price=Decimal("50000"),
            estimated_notional=Decimal("500"),
            executed_notional=Decimal("500"),
            fee_amount=Decimal("0.5"),
            fee_asset="USDT_TEST",
            market_price_at_submission=Decimal("50000"),
            submitted_at=datetime(2026, 6, 28, tzinfo=timezone.utc),
        )
    )
    db_session.add_all([user, btc, contest, participant, account])
    db_session.commit()
    return account.id


def test_repository_lists_admin_accounts_with_user_and_contest(db_session):
    seed_account(db_session)
    repo = CryptoTradingRepository(db_session)

    rows, total = repo.list_admin_accounts(
        contest_slug="practice-arena",
        page=1,
        per_page=20,
    )

    assert total == 1
    assert rows[0].id == 1
    assert rows[0].participant.user.email == "student@example.com"
    assert rows[0].participant.contest.slug == "practice-arena"


def test_repository_loads_admin_account_detail(db_session):
    account_id = seed_account(db_session)
    repo = CryptoTradingRepository(db_session)

    account = repo.get_admin_account_detail(account_id)

    assert account.id == account_id
    assert account.balances[0].asset == "USDT_TEST"
    assert account.positions[0].asset.symbol == "BTCUSDT"
    assert account.orders[0].client_order_id == "web-1"


def test_service_serializes_admin_account_rows(db_session):
    seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    result = service.list_accounts(contest_id="practice-arena", page=1, per_page=20)

    assert result["total"] == 1
    row = result["accounts"][0]
    assert row["user"]["email"] == "student@example.com"
    assert row["contest"]["id"] == "practice-arena"
    assert row["cash"] == 9500.0
    assert row["locked_cash"] == 100.0
    assert row["position_count"] == 1
    assert row["order_count"] == 1


def test_service_serializes_admin_account_detail(db_session):
    account_id = seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    result = service.get_account(account_id)

    assert result["account_id"] == account_id
    assert result["balances"] == [
        {"asset": "USDT_TEST", "available": 9500.0, "locked": 100.0}
    ]
    assert result["positions"][0]["symbol"] == "BTCUSDT"
    assert result["orders"][0]["client_order_id"] == "web-1"


class FakeAdminDashboardService:
    def list_accounts(self, **kwargs):
        return {
            "total": 1,
            "page": kwargs["page"],
            "per_page": kwargs["per_page"],
            "accounts": [{"account_id": 1, "status": "active"}],
        }

    def get_account(self, account_id):
        return {"account_id": account_id, "status": "active", "balances": []}


def test_admin_account_routes_call_dashboard_service():
    app = FastAPI()
    app.include_router(admin.router)
    app.dependency_overrides[admin._require_admin] = lambda: User(
        id=99,
        email="admin@example.com",
        password_hash="hash",
        fullname="Admin",
        role="admin",
    )
    app.dependency_overrides[
        admin.get_crypto_admin_dashboard_service
    ] = lambda: FakeAdminDashboardService()
    client = TestClient(app)

    list_response = client.get(
        "/api/admin/crypto/accounts?contest_id=practice-arena&page=1&per_page=20"
    )
    detail_response = client.get("/api/admin/crypto/accounts/1")

    assert list_response.status_code == 200
    assert list_response.json()["accounts"][0]["account_id"] == 1
    assert detail_response.status_code == 200
    assert detail_response.json()["account_id"] == 1


def test_service_builds_admin_overview(db_session):
    seed_account(db_session)
    service = CryptoAdminDashboardService(CryptoTradingRepository(db_session))

    overview = service.overview()

    assert overview["users"]["total"] == 1
    assert overview["users"]["admins"] == 0
    assert overview["contests"]["total"] == 1
    assert overview["contests"]["active"] == 1
    assert overview["accounts"]["total"] == 1
    assert overview["accounts"]["active"] == 1
    assert overview["accounts"]["total_equity"] == 10100.0
