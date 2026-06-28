from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.crypto_accounts import ContestNotFoundError, CryptoAccountService
from src.services.crypto_execution import AccountUnavailableError, CryptoOrderService


class FakeLiquidityProvider:
    def __init__(self):
        self.called = False

    def get_order_book(self, symbol: str, limit: int) -> dict:
        self.called = True
        return {
            "asks": [{"price": "100", "quantity": "1"}],
            "bids": [{"price": "99", "quantity": "1"}],
            "mid_price": "99.5",
        }


class FakeRepo:
    def __init__(self, contest):
        self.contest = contest
        participant = SimpleNamespace(status="active", contest=contest)
        self.account = SimpleNamespace(status="active", participant=participant)
        self.rolled_back = False

    def get_order_by_client_id(self, user_id, contest_slug, client_order_id):
        return None

    def lock_account_for_user(self, contest_slug, user_id):
        return self.account

    def rollback(self):
        self.rolled_back = True


class FakeJoinRepo:
    def __init__(self, contest):
        self.contest = contest
        self.committed = False

    def get_active_contest(self, contest_slug):
        return self.contest

    def get_participant(self, contest_id, user_id):
        return None

    def commit(self):
        self.committed = True


def make_contest(**overrides):
    values = {
        "slug": "summer-cup",
        "status": "active",
        "starts_at": datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc),
        "ends_at": datetime(2026, 7, 2, 0, 0, tzinfo=timezone.utc),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_market_order_rejects_scheduled_contest_even_when_account_is_active():
    repo = FakeRepo(make_contest(status="scheduled"))
    liquidity = FakeLiquidityProvider()
    service = CryptoOrderService(
        repo,
        liquidity,
        now_provider=lambda: datetime(2026, 7, 1, 12, 0, tzinfo=timezone.utc),
    )

    with pytest.raises(AccountUnavailableError, match="Contest is not open for trading"):
        service.place_market_order(
            user_id=1,
            contest_slug="summer-cup",
            client_order_id="order-1",
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.01"),
        )

    assert liquidity.called is False
    assert repo.rolled_back is True


def test_market_order_rejects_contest_after_end_time():
    repo = FakeRepo(make_contest())
    liquidity = FakeLiquidityProvider()
    service = CryptoOrderService(
        repo,
        liquidity,
        now_provider=lambda: datetime(2026, 7, 2, 0, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(AccountUnavailableError, match="Contest is not open for trading"):
        service.place_market_order(
            user_id=1,
            contest_slug="summer-cup",
            client_order_id="order-2",
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.01"),
        )

    assert liquidity.called is False
    assert repo.rolled_back is True


def test_join_contest_rejects_contest_after_end_time():
    repo = FakeJoinRepo(make_contest(id=10))
    service = CryptoAccountService(
        repo,
        now_provider=lambda: datetime(2026, 7, 2, 0, 1, tzinfo=timezone.utc),
    )

    with pytest.raises(ContestNotFoundError, match="Contest is not available"):
        service.join_contest(user_id=1, contest_slug="summer-cup")

    assert repo.committed is False
