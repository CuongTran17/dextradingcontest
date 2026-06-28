from decimal import Decimal
from datetime import datetime, timezone
from typing import Any


class ContestNotFoundError(ValueError):
    pass


class AccountNotFoundError(ValueError):
    pass


class CryptoAccountService:
    def __init__(self, repo, now_provider=None):
        self.repo = repo
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def join_contest(self, user_id: int, contest_slug: str) -> dict[str, Any]:
        contest = self.repo.get_active_contest(contest_slug)
        if contest is None or not self._contest_is_open_for_join(contest):
            raise ContestNotFoundError("Contest is not available")

        participant = self.repo.get_participant(contest.id, user_id)
        if participant is None:
            participant = self.repo.create_participant(contest.id, user_id)

        account = self.repo.get_account_for_participant(participant.id)
        if account is None:
            account = self.repo.create_account(
                participant.id,
                Decimal(contest.initial_balance),
                contest.quote_asset,
            )

        self.repo.commit()
        return serialize_account(account, contest.slug)

    def _contest_is_open_for_join(self, contest) -> bool:
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

    def get_account(self, user_id: int, contest_slug: str) -> dict[str, Any]:
        account = self.repo.get_account_for_user(contest_slug, user_id)
        if account is None:
            raise AccountNotFoundError("Trading account not found")
        return serialize_account(account, contest_slug)


def serialize_account(account, contest_slug: str) -> dict[str, Any]:
    quote_balance = next(
        (
            balance
            for balance in account.balances
            if balance.asset == "USDT_TEST"
        ),
        account.balances[0] if account.balances else None,
    )
    cash = Decimal(quote_balance.available) if quote_balance else Decimal("0")
    positions = [
        {
            "symbol": position.asset.symbol,
            "quantity": float(position.quantity),
            "average_entry": float(position.average_entry_price),
            "realized_pnl": float(position.realized_pnl),
        }
        for position in account.positions
        if Decimal(position.quantity) > 0
    ]
    orders = [
        serialize_order(order)
        for order in sorted(
            account.orders,
            key=lambda item: item.submitted_at,
            reverse=True,
        )[:50]
    ]

    return {
        "account_id": account.id,
        "contest_id": contest_slug,
        "status": account.status,
        "cash": float(cash),
        "initial_equity": float(account.initial_equity),
        "equity": float(account.current_equity),
        "realized_pnl": float(account.realized_pnl),
        "unrealized_pnl": float(account.unrealized_pnl),
        "positions": positions,
        "orders": orders,
    }


def serialize_order(order) -> dict[str, Any]:
    average_fill_price = (
        float(order.average_fill_price)
        if order.average_fill_price is not None
        else 0.0
    )
    created_at = (
        order.submitted_at.isoformat()
        if hasattr(order.submitted_at, "isoformat")
        else str(order.submitted_at)
    )

    return {
        "order_id": order.id,
        "client_order_id": order.client_order_id,
        "symbol": order.asset.symbol,
        "side": order.side,
        "status": order.status,
        "filled_quantity": float(order.filled_quantity),
        "average_fill_price": average_fill_price,
        "executed_notional": float(order.executed_notional),
        "fee": float(order.fee_amount),
        "created_at": created_at,
    }
