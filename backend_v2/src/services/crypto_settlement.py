from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from src.database.crypto_market_duckdb import CryptoMarketDuckDB
from src.database.crypto_models import (
    CryptoAccountEvent,
    CryptoContestSettlement,
    CryptoOrderEvent,
)
from src.database.user_models import User  # noqa: F401


class ContestSettlementError(ValueError):
    pass


class ContestSettlementNotFoundError(ContestSettlementError):
    pass


class ContestSettlementValidationError(ContestSettlementError):
    pass


class SettlementPriceUnavailableError(ContestSettlementError):
    pass


class CryptoSettlementService:
    def __init__(self, repo, market_repo: CryptoMarketDuckDB | None = None):
        self.repo = repo
        self.market_repo = market_repo or CryptoMarketDuckDB()

    def settle_contest(
        self,
        slug: str,
        *,
        settled_by: int | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        contest = self.repo.get_contest_for_settlement(slug)
        if contest is None:
            raise ContestSettlementNotFoundError(f"Contest '{slug}' not found")

        latest = self.repo.get_latest_settlement(slug)
        if latest is not None and getattr(contest, "status", None) == "completed" and not force:
            return self._settlement_to_response(latest)

        original_status = contest.status
        try:
            if contest.status not in {"active", "settling", "completed"}:
                raise ContestSettlementValidationError(
                    "Contest must be active or settling before settlement"
                )
            if contest.status == "completed" and not force:
                raise ContestSettlementValidationError("Contest is already completed")
            if contest.ends_at is None:
                raise ContestSettlementValidationError("Contest ends_at is required")

            participants = self.repo.list_contest_participants(slug)
            prices = self._resolve_settlement_prices(contest, participants)
            contest.status = "settling"

            rows = []
            cancelled_orders = []
            for participant in participants:
                account = getattr(participant, "account", None)
                if account is None:
                    continue

                cancelled_orders.extend(self._cancel_pending_orders(account, contest))
                self._release_account_locks(account, contest)
                final_equity = self._compute_account_equity(account, contest, prices)
                initial = Decimal(account.initial_equity)
                final_roi = (
                    ((final_equity - initial) / initial) * Decimal("100")
                    if initial
                    else Decimal("0")
                )
                account.current_equity = final_equity
                account.unrealized_pnl = final_equity - Decimal(account.initial_equity) - Decimal(account.realized_pnl)
                account.status = "frozen"
                participant.final_equity = _quantize_money(final_equity)
                participant.final_roi = _quantize_roi(final_roi)

                self._add_account_event(
                    account_id=account.id,
                    event_type="equity_recomputed",
                    payload={
                        "contest_id": contest.slug,
                        "final_equity": str(participant.final_equity),
                        "final_roi": str(participant.final_roi),
                    },
                )
                rows.append(self._snapshot_row(contest, participant, account, prices))

            rows.sort(
                key=lambda row: (
                    -Decimal(str(row["final_equity"])),
                    -Decimal(str(row["realized_pnl"])),
                    row["joined_at"] or "",
                    row["participant_id"],
                )
            )
            for rank, row in enumerate(rows, start=1):
                row["rank"] = rank
                participant = row["_participant"]
                participant.final_rank = rank
                del row["_participant"]

            version = self._next_version(contest.id)
            snapshot = {
                "contest": {
                    "id": contest.slug,
                    "title": contest.title,
                    "status": "completed",
                    "ends_at": _iso(contest.ends_at),
                    "quote_asset": contest.quote_asset,
                },
                "version": version,
                "settled_by": settled_by,
                "settled_at": _iso(_now()),
                "settlement_prices": prices,
                "cancelled_orders": cancelled_orders,
                "rows": rows,
            }
            snapshot_hash = _hash_snapshot(snapshot)
            settlement = CryptoContestSettlement(
                contest_id=contest.id,
                version=version,
                status="completed",
                snapshot_json=json.dumps(snapshot, sort_keys=True),
                snapshot_hash=snapshot_hash,
                settled_by=settled_by,
                settled_at=_now(),
            )
            self.repo.add_settlement(settlement)
            contest.status = "completed"
            self.repo.commit()
            return self._snapshot_to_response(snapshot, snapshot_hash)
        except Exception:
            contest.status = original_status
            self.repo.rollback()
            raise

    def get_latest_settlement(self, slug: str) -> dict[str, Any]:
        settlement = self.repo.get_latest_settlement(slug)
        if settlement is None:
            raise ContestSettlementNotFoundError(
                f"Settlement for contest '{slug}' not found"
            )
        return self._settlement_to_response(settlement)

    def _resolve_settlement_prices(self, contest, participants) -> dict[str, dict[str, Any]]:
        symbols = sorted(
            {
                position.asset.symbol
                for participant in participants
                if getattr(participant, "account", None) is not None
                for position in participant.account.positions
                if Decimal(position.quantity) > 0
            }
        )
        prices: dict[str, dict[str, Any]] = {}
        for symbol in symbols:
            row = self.market_repo.latest_closed_price_at_or_before(
                symbol,
                _as_aware_utc(contest.ends_at),
            )
            if row is None:
                raise SettlementPriceUnavailableError(
                    f"Missing settlement price for {symbol}"
                )
            prices[symbol] = {
                "price": float(row["close"]),
                "time": int(row["time"]),
            }
        return prices

    def _cancel_pending_orders(self, account, contest) -> list[dict[str, Any]]:
        rows = []
        for order in account.orders:
            if order.status != "pending":
                continue
            order.status = "cancelled"
            order.completed_at = _now()
            rows.append(
                {
                    "order_id": order.id,
                    "symbol": order.asset.symbol,
                    "side": order.side,
                    "order_type": order.order_type,
                    "requested_quantity": float(order.requested_quantity),
                }
            )
            self._add_order_event(
                order_id=order.id,
                account_id=account.id,
                event_type="settlement_cancelled",
                payload={
                    "contest_id": contest.slug,
                    "side": order.side,
                    "order_type": order.order_type,
                },
            )
        return rows

    def _release_account_locks(self, account, contest) -> None:
        for balance in account.balances:
            if Decimal(balance.locked) <= 0:
                continue
            released = Decimal(balance.locked)
            balance.available = Decimal(balance.available) + released
            balance.locked = Decimal("0")
            self._add_account_event(
                account_id=account.id,
                event_type="cash_lock_released",
                payload={
                    "contest_id": contest.slug,
                    "asset": balance.asset,
                    "released": str(released),
                },
            )

        for position in account.positions:
            locked_quantity = Decimal(
                getattr(position, "locked_quantity", Decimal("0")) or Decimal("0")
            )
            if locked_quantity <= 0:
                continue
            position.locked_quantity = Decimal("0")
            self._add_account_event(
                account_id=account.id,
                event_type="position_lock_released",
                payload={
                    "contest_id": contest.slug,
                    "symbol": position.asset.symbol,
                    "released_quantity": str(locked_quantity),
                },
            )

    def _compute_account_equity(self, account, contest, prices) -> Decimal:
        cash = sum(
            (
                Decimal(balance.available)
                for balance in account.balances
                if balance.asset == contest.quote_asset
            ),
            Decimal("0"),
        )
        position_value = sum(
            (
                Decimal(position.quantity)
                * Decimal(str(prices[position.asset.symbol]["price"]))
                for position in account.positions
                if Decimal(position.quantity) > 0
            ),
            Decimal("0"),
        )
        return cash + position_value

    def _snapshot_row(self, contest, participant, account, prices) -> dict[str, Any]:
        positions = [
            {
                "symbol": position.asset.symbol,
                "quantity": float(position.quantity),
                "settlement_price": prices[position.asset.symbol]["price"],
                "value": float(
                    Decimal(position.quantity)
                    * Decimal(str(prices[position.asset.symbol]["price"]))
                ),
            }
            for position in account.positions
            if Decimal(position.quantity) > 0
        ]
        filled_orders = [
            order for order in account.orders if getattr(order, "status", None) == "filled"
        ]
        return {
            "_participant": participant,
            "rank": 0,
            "participant_id": participant.id,
            "user_id": participant.user_id,
            "user": _user_name(participant),
            "account_id": account.id,
            "cash": float(
                sum(
                    (
                        Decimal(balance.available)
                        for balance in account.balances
                        if balance.asset == contest.quote_asset
                    ),
                    Decimal("0"),
                )
            ),
            "positions": positions,
            "final_equity": float(participant.final_equity),
            "final_roi": float(participant.final_roi),
            "realized_pnl": float(account.realized_pnl),
            "volume": float(
                sum((Decimal(order.executed_notional) for order in filled_orders), Decimal("0"))
            ),
            "trade_count": len(filled_orders),
            "joined_at": _iso(participant.joined_at),
        }

    def _next_version(self, contest_id: int) -> int:
        return len(self.repo.list_settlements(contest_id)) + 1 if hasattr(self.repo, "list_settlements") else len(getattr(self.repo, "settlements", [])) + 1

    def _add_account_event(self, *, account_id: int, event_type: str, payload: dict[str, Any]) -> None:
        self.repo.add_account_event(
            CryptoAccountEvent(
                account_id=account_id,
                event_type=event_type,
                payload_json=json.dumps(payload, sort_keys=True),
                created_at=_now(),
            )
        )

    def _add_order_event(
        self,
        *,
        order_id: int,
        account_id: int,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        self.repo.add_order_event(
            CryptoOrderEvent(
                order_id=order_id,
                account_id=account_id,
                event_type=event_type,
                payload_json=json.dumps(payload, sort_keys=True),
                created_at=_now(),
            )
        )

    def _settlement_to_response(self, settlement) -> dict[str, Any]:
        snapshot = json.loads(settlement.snapshot_json)
        return self._snapshot_to_response(snapshot, settlement.snapshot_hash)

    @staticmethod
    def _snapshot_to_response(snapshot: dict[str, Any], snapshot_hash: str) -> dict[str, Any]:
        return {
            "status": snapshot["contest"]["status"],
            "contest_id": snapshot["contest"]["id"],
            "version": snapshot["version"],
            "snapshot_hash": snapshot_hash,
            "settlement_prices": snapshot["settlement_prices"],
            "rows": snapshot["rows"],
            "cancelled_orders": snapshot["cancelled_orders"],
            "settled_at": snapshot["settled_at"],
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _as_aware_utc(value).isoformat()


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000000000000000001"), rounding=ROUND_HALF_UP)


def _quantize_roi(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)


def _hash_snapshot(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _user_name(participant) -> str:
    user = getattr(participant, "user", None)
    if user is None:
        return f"user-{participant.user_id}"
    return getattr(user, "fullname", None) or getattr(user, "email", None) or f"user-{participant.user_id}"
