import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Callable
from urllib import request


class SolanaJoinError(ValueError):
    pass


class SolanaJoinVerificationError(SolanaJoinError):
    pass


class WalletAlreadyBoundError(SolanaJoinError):
    pass


class ContestUnavailableForSolanaJoinError(SolanaJoinError):
    pass


class AdminWalletCannotJoinContestError(SolanaJoinError):
    pass


TxVerifier = Callable[[str, str, str], bool]
RpcPost = Callable[[dict[str, Any]], dict[str, Any]]


def default_tx_verifier(
    join_tx_signature: str,
    wallet_address: str,
    contest_slug: str,
) -> bool:
    return False


class SolanaRpcTransactionVerifier:
    def __init__(
        self,
        rpc_url: str | None,
        program_id: str | None = None,
        rpc_post: RpcPost | None = None,
    ):
        self.rpc_url = rpc_url
        self.program_id = program_id
        self.rpc_post = rpc_post or self._post

    def __call__(
        self,
        join_tx_signature: str,
        wallet_address: str,
        contest_slug: str,
    ) -> bool:
        if not self.rpc_url or not self.program_id:
            return False

        response = self.rpc_post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [
                    join_tx_signature,
                    {
                        "encoding": "jsonParsed",
                        "commitment": "confirmed",
                        "maxSupportedTransactionVersion": 0,
                    },
                ],
            }
        )
        result = response.get("result")
        if not result or result.get("meta", {}).get("err") is not None:
            return False

        account_keys = (
            result.get("transaction", {})
            .get("message", {})
            .get("accountKeys", [])
        )
        wallet_signed = any(
            self._account_pubkey(account) == wallet_address
            and self._account_is_signer(account)
            for account in account_keys
        )
        if not wallet_signed:
            return False

        if not any(
            self._account_pubkey(account) == self.program_id
            for account in account_keys
        ):
            return False

        log_messages = result.get("meta", {}).get("logMessages") or []
        if not any(contest_slug in message for message in log_messages):
            return False

        return True

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        http_request = request.Request(
            self.rpc_url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(http_request, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    @staticmethod
    def _account_pubkey(account) -> str | None:
        if isinstance(account, str):
            return account
        if isinstance(account, dict):
            return account.get("pubkey")
        return None

    @staticmethod
    def _account_is_signer(account) -> bool:
        return isinstance(account, dict) and account.get("signer") is True


class SolanaJoinService:
    def __init__(
        self,
        repo,
        tx_verifier: TxVerifier | None = None,
        now_provider=None,
    ):
        self.repo = repo
        self.tx_verifier = tx_verifier or default_tx_verifier
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def get_wallet(self, user_id: int, contest_slug: str) -> dict[str, Any]:
        participant = self.repo.get_participant_wallet(contest_slug, user_id)
        return self._serialize_wallet(contest_slug, participant)

    def confirm_join(
        self,
        user_id: int,
        contest_slug: str,
        wallet_address: str,
        join_tx_signature: str,
    ) -> dict[str, Any]:
        participant = self.repo.get_participant_wallet(contest_slug, user_id)
        if participant is not None and getattr(participant, "wallet_address", None):
            return self._confirm_existing_binding(
                contest_slug,
                participant,
                wallet_address,
                join_tx_signature,
            )

        contest = self._get_joinable_contest(contest_slug)
        if getattr(contest, "onchain_admin_wallet", None) == wallet_address:
            raise AdminWalletCannotJoinContestError(
                "The admin wallet that initialized this contest cannot join it"
            )

        if not self.tx_verifier(join_tx_signature, wallet_address, contest_slug):
            raise SolanaJoinVerificationError("Solana join transaction could not be verified")

        if participant is None:
            participant = self.repo.get_participant(contest.id, user_id)
        if participant is None:
            participant = self.repo.create_participant(contest.id, user_id)

        account = self.repo.get_account_for_participant(participant.id)
        if account is None:
            self.repo.create_account(
                participant.id,
                Decimal(contest.initial_balance),
                contest.quote_asset,
            )

        joined_onchain_at = self.now_provider()
        self.repo.set_participant_wallet(
            participant,
            wallet_address=wallet_address,
            wallet_type="solana",
            join_tx_signature=join_tx_signature,
            joined_onchain_at=joined_onchain_at,
        )
        self.repo.commit()
        return self._serialize_wallet(contest_slug, participant)

    def _confirm_existing_binding(
        self,
        contest_slug: str,
        participant,
        wallet_address: str,
        join_tx_signature: str,
    ) -> dict[str, Any]:
        if (
            participant.wallet_address == wallet_address
            and participant.join_tx_signature == join_tx_signature
        ):
            return self._serialize_wallet(contest_slug, participant)
        raise WalletAlreadyBoundError("Contest participant wallet is already bound")

    def _get_joinable_contest(self, contest_slug: str):
        contest = self.repo.get_active_contest(contest_slug)
        if contest is None or not self._contest_is_open(contest):
            raise ContestUnavailableForSolanaJoinError("Contest is not available")
        return contest

    def _contest_is_open(self, contest) -> bool:
        if getattr(contest, "status", None) not in {"scheduled", "active"}:
            return False

        ends_at = self._as_aware_utc(getattr(contest, "ends_at", None))
        if ends_at is not None and self._as_aware_utc(self.now_provider()) >= ends_at:
            return False
        return True

    @staticmethod
    def _as_aware_utc(value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _serialize_wallet(self, contest_slug: str, participant) -> dict[str, Any]:
        joined_onchain_at = (
            participant.joined_onchain_at.isoformat()
            if participant is not None
            and getattr(participant, "joined_onchain_at", None) is not None
            else None
        )
        return {
            "contest_id": contest_slug,
            "wallet_address": (
                getattr(participant, "wallet_address", None)
                if participant is not None
                else None
            ),
            "wallet_type": (
                getattr(participant, "wallet_type", None)
                if participant is not None
                else None
            ),
            "join_tx_signature": (
                getattr(participant, "join_tx_signature", None)
                if participant is not None
                else None
            ),
            "joined_onchain_at": joined_onchain_at,
        }
