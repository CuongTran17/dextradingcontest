from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.solana_join import (
    SolanaRpcTransactionVerifier,
    SolanaJoinService,
    SolanaJoinVerificationError,
    WalletAlreadyBoundError,
    default_tx_verifier,
)


class FakeRepo:
    def __init__(self, participant=None):
        self.participant = participant
        self.created_participant = None
        self.created_account = None
        self.committed = False

    def get_participant_wallet(self, contest_slug, user_id):
        return self.participant

    def get_active_contest(self, contest_slug):
        return SimpleNamespace(
            id=11,
            slug=contest_slug,
            status="active",
            ends_at=None,
            initial_balance=Decimal("10000"),
            quote_asset="USDT_TEST",
        )

    def get_participant(self, contest_id, user_id):
        return self.participant

    def create_participant(self, contest_id, user_id):
        self.created_participant = SimpleNamespace(
            id=23,
            contest_id=contest_id,
            user_id=user_id,
            wallet_address=None,
            wallet_type=None,
            join_tx_signature=None,
            joined_onchain_at=None,
        )
        self.participant = self.created_participant
        return self.created_participant

    def get_account_for_participant(self, participant_id):
        return self.created_account

    def create_account(self, participant_id, initial_balance, quote_asset):
        self.created_account = SimpleNamespace(
            id=31,
            contest_participant_id=participant_id,
            initial_balance=initial_balance,
            quote_asset=quote_asset,
        )
        return self.created_account

    def set_participant_wallet(
        self,
        participant,
        wallet_address,
        wallet_type,
        join_tx_signature,
        joined_onchain_at,
    ):
        participant.wallet_address = wallet_address
        participant.wallet_type = wallet_type
        participant.join_tx_signature = join_tx_signature
        participant.joined_onchain_at = joined_onchain_at
        return participant

    def commit(self):
        self.committed = True


def test_confirm_join_locks_wallet_after_onchain_signature():
    joined_at = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    repo = FakeRepo()
    service = SolanaJoinService(
        repo,
        tx_verifier=lambda sig, wallet, contest: True,
        now_provider=lambda: joined_at,
    )

    result = service.confirm_join(
        user_id=1,
        contest_slug="summer-cup",
        wallet_address="So11111111111111111111111111111111111111112",
        join_tx_signature="5" * 88,
    )

    assert result == {
        "contest_id": "summer-cup",
        "wallet_address": "So11111111111111111111111111111111111111112",
        "wallet_type": "solana",
        "join_tx_signature": "5" * 88,
        "joined_onchain_at": "2026-07-28T12:00:00+00:00",
    }
    assert repo.created_participant is repo.participant
    assert repo.created_account is not None
    assert repo.committed is True


def test_confirm_join_rejects_different_wallet_after_binding():
    participant = SimpleNamespace(
        wallet_address="So11111111111111111111111111111111111111112",
        wallet_type="solana",
        join_tx_signature="5" * 88,
        joined_onchain_at=datetime(2026, 7, 28, tzinfo=timezone.utc),
    )
    service = SolanaJoinService(FakeRepo(participant), tx_verifier=lambda *_: True)

    with pytest.raises(WalletAlreadyBoundError):
        service.confirm_join(
            user_id=1,
            contest_slug="summer-cup",
            wallet_address="So22222222222222222222222222222222222222222",
            join_tx_signature="5" * 88,
        )


def test_confirm_join_rejects_unverified_transaction():
    service = SolanaJoinService(FakeRepo(), tx_verifier=lambda *_: False)

    with pytest.raises(SolanaJoinVerificationError):
        service.confirm_join(
            user_id=1,
            contest_slug="summer-cup",
            wallet_address="So11111111111111111111111111111111111111112",
            join_tx_signature="5" * 88,
        )


def test_default_tx_verifier_rejects_without_rpc_configuration():
    assert (
        default_tx_verifier(
            "5" * 88,
            "So11111111111111111111111111111111111111112",
            "summer-cup",
        )
        is False
    )


def test_rpc_transaction_verifier_requires_confirmed_wallet_signer_and_program():
    requests = []

    def fake_rpc(payload):
        requests.append(payload)
        return {
            "result": {
                "meta": {
                    "err": None,
                    "logMessages": ["Program log: join_contest contest=summer-cup"],
                },
                "transaction": {
                    "message": {
                        "accountKeys": [
                            {
                                "pubkey": "So11111111111111111111111111111111111111112",
                                "signer": True,
                            },
                            {
                                "pubkey": "Contest111111111111111111111111111111111111",
                                "signer": False,
                            },
                        ]
                    }
                },
            }
        }

    verifier = SolanaRpcTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        program_id="Contest111111111111111111111111111111111111",
        rpc_post=fake_rpc,
    )

    assert (
        verifier(
            "5" * 88,
            "So11111111111111111111111111111111111111112",
            "summer-cup",
        )
        is True
    )
    assert requests[0]["method"] == "getTransaction"


def test_rpc_transaction_verifier_rejects_without_program_configuration():
    verifier = SolanaRpcTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        program_id=None,
        rpc_post=lambda _: {"result": {}},
    )

    assert (
        verifier(
            "5" * 88,
            "So11111111111111111111111111111111111111112",
            "summer-cup",
        )
        is False
    )


def test_rpc_transaction_verifier_rejects_transaction_without_contest_log():
    def fake_rpc(_payload):
        return {
            "result": {
                "meta": {"err": None, "logMessages": ["Program log: join_contest"]},
                "transaction": {
                    "message": {
                        "accountKeys": [
                            {
                                "pubkey": "So11111111111111111111111111111111111111112",
                                "signer": True,
                            },
                            {
                                "pubkey": "Contest111111111111111111111111111111111111",
                                "signer": False,
                            },
                        ]
                    }
                },
            }
        }

    verifier = SolanaRpcTransactionVerifier(
        rpc_url="https://api.devnet.solana.com",
        program_id="Contest111111111111111111111111111111111111",
        rpc_post=fake_rpc,
    )

    assert (
        verifier(
            "5" * 88,
            "So11111111111111111111111111111111111111112",
            "summer-cup",
        )
        is False
    )
