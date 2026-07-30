from datetime import datetime, timedelta, timezone
from typing import Protocol

from src.database.crypto_models import CryptoFaucetClaim
from src.database.user_models import User  # noqa: F401


class FaucetCooldownError(ValueError):
    pass


class FaucetUnavailableError(ValueError):
    pass


class SolanaSender(Protocol):
    def send_lamports(self, wallet_address: str, amount_lamports: int) -> str:
        ...


class UnconfiguredSolanaSender:
    def send_lamports(self, wallet_address: str, amount_lamports: int) -> str:
        del wallet_address, amount_lamports
        raise FaucetUnavailableError("Solana faucet sender is not configured")


class SolanaFaucetService:
    def __init__(
        self,
        repo,
        sender: SolanaSender | None = None,
        amount_lamports: int = 10_000_000,
        cooldown_hours: int = 24,
        now_provider=None,
    ):
        self.repo = repo
        self.sender = sender or UnconfiguredSolanaSender()
        self.amount_lamports = amount_lamports
        self.cooldown_hours = cooldown_hours
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def claim(self, user_id: int, wallet_address: str, ip_hash: str) -> dict:
        now = self._as_aware_utc(self.now_provider())
        latest_claim = self.repo.get_latest_faucet_claim(user_id, wallet_address)
        if latest_claim is not None:
            claimed_at = self._as_aware_utc(latest_claim.claimed_at)
            if claimed_at + timedelta(hours=self.cooldown_hours) > now:
                raise FaucetCooldownError("Solana faucet cooldown is still active")

        tx_signature = self.sender.send_lamports(wallet_address, self.amount_lamports)
        claim = CryptoFaucetClaim(
            user_id=user_id,
            wallet_address=wallet_address,
            amount_lamports=self.amount_lamports,
            tx_signature=tx_signature,
            ip_hash=ip_hash,
            claimed_at=now,
        )
        self.repo.add_faucet_claim(claim)
        self.repo.commit()
        return {
            "wallet_address": wallet_address,
            "amount_lamports": self.amount_lamports,
            "tx_signature": tx_signature,
            "claimed_at": now.isoformat(),
        }

    @staticmethod
    def _as_aware_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
