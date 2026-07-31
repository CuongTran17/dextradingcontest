from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.crypto_settlement import (
    CryptoSettlementService,
    SettlementPriceUnavailableError,
)


class FakeMarketRepo:
    def __init__(self, prices):
        self.prices = prices

    def latest_closed_price_at_or_before(self, symbol, at):
        price = self.prices.get(symbol)
        if price is None:
            return None
        return {
            "symbol": symbol,
            "time": int(at.timestamp()),
            "close": float(price),
        }


class FakeSettlementRepository:
    def __init__(self):
        self.contest = SimpleNamespace(
            id=1,
            slug="summer-cup",
            title="Summer Cup",
            status="active",
            mode="contest",
            quote_asset="USDT_TEST",
            initial_balance=Decimal("10000"),
            ends_at=datetime(2026, 7, 28, 10, 0, tzinfo=timezone.utc),
        )
        self.asset = SimpleNamespace(id=2, symbol="BTCUSDT")
        self.pending_buy = SimpleNamespace(
            id=11,
            account_id=101,
            asset_id=2,
            asset=self.asset,
            side="buy",
            order_type="limit",
            status="pending",
            requested_quantity=Decimal("0.01"),
            limit_price=Decimal("90000"),
            fee_asset="USDT_TEST",
        )
        self.pending_sell = SimpleNamespace(
            id=12,
            account_id=101,
            asset_id=2,
            asset=self.asset,
            side="sell",
            order_type="limit",
            status="pending",
            requested_quantity=Decimal("0.005"),
            limit_price=Decimal("120000"),
            fee_asset="USDT_TEST",
        )
        self.filled_buy = SimpleNamespace(
            id=13,
            account_id=101,
            asset_id=2,
            asset=self.asset,
            side="buy",
            order_type="market",
            status="filled",
            requested_quantity=Decimal("0.02"),
            filled_quantity=Decimal("0.02"),
            executed_notional=Decimal("2000"),
            fee_asset="USDT_TEST",
        )
        self.account = SimpleNamespace(
            id=101,
            status="active",
            initial_equity=Decimal("10000"),
            current_equity=Decimal("10000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            balances=[
                SimpleNamespace(
                    asset="USDT_TEST",
                    available=Decimal("5000"),
                    locked=Decimal("900.9"),
                )
            ],
            positions=[
                SimpleNamespace(
                    asset_id=2,
                    asset=self.asset,
                    quantity=Decimal("0.02"),
                    locked_quantity=Decimal("0.005"),
                    average_entry_price=Decimal("100000"),
                    cost_basis=Decimal("2000"),
                    realized_pnl=Decimal("0"),
                )
            ],
            orders=[self.pending_buy, self.pending_sell, self.filled_buy],
        )
        self.participant = SimpleNamespace(
            id=201,
            contest_id=1,
            user_id=301,
            status="active",
            joined_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
            final_rank=None,
            final_equity=None,
            final_roi=None,
            account=self.account,
            user=SimpleNamespace(id=301, fullname="Alice", email="alice@test.local"),
        )
        self.settlements = []
        self.account_events = []
        self.order_events = []
        self.commit_count = 0
        self.rollback_count = 0

    def get_contest_for_settlement(self, slug):
        return self.contest if slug == self.contest.slug else None

    def list_contest_participants(self, slug):
        assert slug == self.contest.slug
        return [self.participant]

    def get_latest_settlement(self, slug):
        assert slug == self.contest.slug
        return self.settlements[-1] if self.settlements else None

    def add_settlement(self, settlement):
        settlement.id = len(self.settlements) + 1
        self.settlements.append(settlement)
        return settlement

    def add_account_event(self, event):
        self.account_events.append(event)
        return event

    def add_order_event(self, event):
        self.order_events.append(event)
        return event

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def test_settlement_releases_locks_marks_positions_to_market_without_forced_sell():
    repo = FakeSettlementRepository()
    service = CryptoSettlementService(
        repo,
        market_repo=FakeMarketRepo({"BTCUSDT": Decimal("110000")}),
    )

    result = service.settle_contest("summer-cup", settled_by=9)

    assert result["status"] == "completed"
    assert result["version"] == 1
    assert result["settlement_prices"]["BTCUSDT"]["price"] == 110000.0
    assert repo.pending_buy.status == "cancelled"
    assert repo.pending_sell.status == "cancelled"
    assert repo.account.balances[0].available == Decimal("5900.9")
    assert repo.account.balances[0].locked == Decimal("0")
    assert repo.account.positions[0].locked_quantity == Decimal("0")
    assert repo.participant.final_equity == Decimal("8100.900000000000000000")
    assert repo.participant.final_roi == Decimal("-18.99100000")
    assert repo.participant.final_rank == 1
    assert repo.account.status == "frozen"
    assert repo.contest.status == "completed"
    assert not any(order.order_type == "settlement_sell" for order in repo.account.orders)
    assert repo.account_events
    assert repo.order_events
    assert result["snapshot_hash"]


def test_settlement_fails_when_open_position_price_is_missing():
    repo = FakeSettlementRepository()
    service = CryptoSettlementService(repo, market_repo=FakeMarketRepo({}))

    with pytest.raises(SettlementPriceUnavailableError):
        service.settle_contest("summer-cup")

    assert repo.rollback_count == 1
    assert repo.contest.status == "active"


def test_settle_is_idempotent_but_resettle_creates_new_version():
    repo = FakeSettlementRepository()
    service = CryptoSettlementService(
        repo,
        market_repo=FakeMarketRepo({"BTCUSDT": Decimal("110000")}),
    )

    first = service.settle_contest("summer-cup")
    second = service.settle_contest("summer-cup")
    resettled = service.settle_contest("summer-cup", force=True)

    assert first["version"] == 1
    assert second["version"] == 1
    assert resettled["version"] == 2
    assert len(repo.settlements) == 2
