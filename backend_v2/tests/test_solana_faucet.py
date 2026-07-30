from datetime import datetime, timedelta, timezone

import pytest

from src.services.solana_faucet import FaucetCooldownError, SolanaFaucetService


class FakeSolanaSender:
    def __init__(self, signature: str):
        self.signature = signature
        self.sent = []

    def send_lamports(self, wallet_address: str, amount_lamports: int) -> str:
        self.sent.append((wallet_address, amount_lamports))
        return self.signature


class FakeFaucetRepo:
    def __init__(self):
        self.claims = []
        self.committed = False

    def get_latest_faucet_claim(self, user_id: int, wallet_address: str):
        matches = [
            claim
            for claim in self.claims
            if claim.user_id == user_id and claim.wallet_address == wallet_address
        ]
        return matches[-1] if matches else None

    def add_faucet_claim(self, claim):
        claim.id = len(self.claims) + 1
        self.claims.append(claim)
        return claim

    def commit(self):
        self.committed = True


def test_faucet_rejects_second_claim_within_cooldown():
    now = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    sender = FakeSolanaSender(signature="5" * 88)
    repo = FakeFaucetRepo()
    service = SolanaFaucetService(
        repo,
        sender=sender,
        amount_lamports=10_000_000,
        cooldown_hours=24,
        now_provider=lambda: now,
    )

    first = service.claim(
        user_id=1,
        wallet_address="So11111111111111111111111111111111111111112",
        ip_hash="hash",
    )

    assert first["tx_signature"] == "5" * 88
    assert sender.sent == [("So11111111111111111111111111111111111111112", 10_000_000)]
    with pytest.raises(FaucetCooldownError):
        service.claim(
            user_id=1,
            wallet_address="So11111111111111111111111111111111111111112",
            ip_hash="hash",
        )


def test_faucet_allows_claim_after_cooldown():
    current = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)
    sender = FakeSolanaSender(signature="5" * 88)
    repo = FakeFaucetRepo()
    service = SolanaFaucetService(
        repo,
        sender=sender,
        amount_lamports=10_000_000,
        cooldown_hours=24,
        now_provider=lambda: current,
    )

    service.claim(
        user_id=1,
        wallet_address="So11111111111111111111111111111111111111112",
        ip_hash="hash",
    )
    current = current + timedelta(hours=25)

    second = service.claim(
        user_id=1,
        wallet_address="So11111111111111111111111111111111111111112",
        ip_hash="hash",
    )

    assert second["tx_signature"] == "5" * 88
    assert len(sender.sent) == 2
