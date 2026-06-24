from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.crypto_accounts import (
    AccountNotFoundError,
    CryptoAccountService,
)


class FakeRepository:
    def __init__(self):
        self.participant = None
        self.account = None
        self.participant_create_count = 0
        self.account_create_count = 0
        self.commit_count = 0

    def get_active_contest(self, slug):
        return SimpleNamespace(
            id=1,
            slug=slug,
            title="Practice Arena",
            initial_balance=Decimal("10000"),
            quote_asset="USDT_TEST",
        )

    def get_participant(self, contest_id, user_id):
        return self.participant

    def create_participant(self, contest_id, user_id):
        self.participant_create_count += 1
        self.participant = SimpleNamespace(
            id=7,
            contest_id=contest_id,
            user_id=user_id,
            status="active",
        )
        return self.participant

    def get_account_for_participant(self, participant_id):
        return self.account

    def create_account(self, participant_id, initial_balance, quote_asset):
        self.account_create_count += 1
        self.account = SimpleNamespace(
            id=9,
            contest_participant_id=participant_id,
            status="active",
            initial_equity=initial_balance,
            current_equity=initial_balance,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            balances=[
                SimpleNamespace(
                    asset=quote_asset,
                    available=initial_balance,
                    locked=Decimal("0"),
                )
            ],
            positions=[],
            orders=[],
        )
        return self.account

    def get_account_for_user(self, contest_slug, user_id):
        return self.account

    def commit(self):
        self.commit_count += 1


def test_join_contest_creates_one_isolated_account_and_is_idempotent():
    repo = FakeRepository()
    service = CryptoAccountService(repo)

    first = service.join_contest(user_id=3, contest_slug="practice-arena")
    second = service.join_contest(user_id=3, contest_slug="practice-arena")

    assert first["account_id"] == second["account_id"] == 9
    assert first["cash"] == 10000.0
    assert first["positions"] == []
    assert repo.participant_create_count == 1
    assert repo.account_create_count == 1


def test_get_account_rejects_user_who_has_not_joined():
    service = CryptoAccountService(FakeRepository())

    with pytest.raises(AccountNotFoundError, match="Trading account not found"):
        service.get_account(user_id=3, contest_slug="practice-arena")
