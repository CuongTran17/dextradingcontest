from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.repositories.crypto_trading import CryptoTradingRepository


class AdminAccountNotFoundError(Exception):
    pass


class CryptoAdminDashboardService:
    def __init__(self, repository: CryptoTradingRepository):
        self.repository = repository

    def list_accounts(
        self,
        *,
        contest_id: str | None = None,
        q: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> dict[str, Any]:
        rows, total = self.repository.list_admin_accounts(
            contest_slug=contest_id,
            q=q,
            status=status,
            page=page,
            per_page=per_page,
        )
        return {
            "total": total,
            "page": page,
            "per_page": per_page,
            "accounts": [self._account_row(account) for account in rows],
        }

    def get_account(self, account_id: int) -> dict[str, Any]:
        account = self.repository.get_admin_account_detail(account_id)
        if account is None:
            raise AdminAccountNotFoundError("Trading account not found")
        return self._account_detail(account)

    def overview(self) -> dict[str, Any]:
        counts = self.repository.admin_overview_counts()
        return {
            "users": {
                "total": counts["users_total"],
                "locked": counts["users_locked"],
                "admins": counts["users_admins"],
            },
            "contests": {
                "total": counts["contests_total"],
                "active": counts["contests_active"],
                "participants": counts["participants_total"],
            },
            "accounts": {
                "total": counts["accounts_total"],
                "active": counts["accounts_active"],
                "total_equity": counts["total_equity"],
            },
        }

    def _account_row(self, account) -> dict[str, Any]:
        participant = account.participant
        contest = participant.contest
        user = participant.user
        cash = sum(
            float(balance.available)
            for balance in account.balances
            if balance.asset == contest.quote_asset
        )
        locked_cash = sum(
            float(balance.locked)
            for balance in account.balances
            if balance.asset == contest.quote_asset
        )
        initial = float(account.initial_equity)
        equity = float(account.current_equity)
        pnl = equity - initial
        return {
            "account_id": account.id,
            "status": account.status,
            "participant_status": participant.status,
            "user": self._user(user),
            "contest": {
                "id": contest.slug,
                "title": contest.title,
                "status": contest.status,
            },
            "cash": round(cash, 2),
            "locked_cash": round(locked_cash, 2),
            "initial_equity": round(initial, 2),
            "equity": round(equity, 2),
            "realized_pnl": round(float(account.realized_pnl), 2),
            "unrealized_pnl": round(float(account.unrealized_pnl), 2),
            "roi": round((pnl / initial) * 100, 4) if initial else 0,
            "position_count": len(account.positions),
            "order_count": len(account.orders),
            "updated_at": _iso(account.updated_at),
        }

    def _account_detail(self, account) -> dict[str, Any]:
        row = self._account_row(account)
        return {
            **row,
            "balances": [
                {
                    "asset": balance.asset,
                    "available": float(balance.available),
                    "locked": float(balance.locked),
                }
                for balance in account.balances
            ],
            "positions": [
                {
                    "symbol": position.asset.symbol,
                    "quantity": float(position.quantity),
                    "average_entry_price": float(position.average_entry_price),
                    "cost_basis": float(position.cost_basis),
                    "realized_pnl": float(position.realized_pnl),
                    "updated_at": _iso(position.updated_at),
                }
                for position in account.positions
            ],
            "orders": [
                {
                    "order_id": order.id,
                    "client_order_id": order.client_order_id,
                    "symbol": order.asset.symbol,
                    "side": order.side,
                    "order_type": order.order_type,
                    "status": order.status,
                    "requested_quantity": float(order.requested_quantity),
                    "filled_quantity": float(order.filled_quantity),
                    "average_fill_price": float(order.average_fill_price or 0),
                    "executed_notional": float(order.executed_notional),
                    "fee_amount": float(order.fee_amount),
                    "fee_asset": order.fee_asset,
                    "submitted_at": _iso(order.submitted_at),
                    "completed_at": _iso(order.completed_at),
                    "fills": [
                        {
                            "fill_sequence": fill.fill_sequence,
                            "price": float(fill.price),
                            "quantity": float(fill.quantity),
                            "notional": float(fill.notional),
                            "fee_amount": float(fill.fee_amount),
                            "fee_asset": fill.fee_asset,
                            "executed_at": _iso(fill.executed_at),
                        }
                        for fill in order.fills
                    ],
                }
                for order in sorted(
                    account.orders,
                    key=lambda item: item.submitted_at,
                    reverse=True,
                )
            ],
        }

    def _user(self, user) -> dict[str, Any]:
        return {
            "id": user.id,
            "email": user.email,
            "fullname": user.fullname,
            "role": user.role,
            "is_locked": user.is_locked,
        }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()
