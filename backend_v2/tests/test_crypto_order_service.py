from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.services.crypto_execution import (
    CryptoOrderService,
    InsufficientPositionError,
)


class FixedLiquidityProvider:
    def get_order_book(self, symbol, limit):
        assert symbol == "BTCUSDT"
        assert limit == 100
        return {
            "symbol": symbol,
            "mid_price": 101000.0,
            "bids": [
                {"price": 100000.0, "quantity": 0.01},
                {"price": 99000.0, "quantity": 0.01},
            ],
            "asks": [
                {"price": 100000.0, "quantity": 0.01},
                {"price": 102000.0, "quantity": 0.01},
            ],
        }


class FakeRepository:
    def __init__(self):
        self.contest = SimpleNamespace(
            id=1,
            slug="practice-arena",
            quote_asset="USDT_TEST",
            fee_rate=Decimal("0.001"),
            status="active",
        )
        self.asset = SimpleNamespace(
            id=2,
            symbol="BTCUSDT",
            min_quantity=Decimal("0.000001"),
            min_notional=Decimal("5"),
        )
        self.account = SimpleNamespace(
            id=3,
            status="active",
            participant=SimpleNamespace(status="active", contest=self.contest),
            current_equity=Decimal("10000"),
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
            version=1,
            orders=[],
        )
        self.balance = SimpleNamespace(
            available=Decimal("10000"),
            locked=Decimal("0"),
        )
        self.position = None
        self.orders = {}
        self.saved_fills = []
        self.debit_count = 0
        self.commit_count = 0
        self.rollback_count = 0

    def get_order_by_client_id(
        self,
        user_id,
        contest_slug,
        client_order_id,
    ):
        return self.orders.get(client_order_id)

    def lock_account_for_user(self, contest_slug, user_id):
        return self.account

    def get_enabled_asset(self, contest_slug, symbol):
        return self.asset, self.contest

    def lock_balance(self, account_id, asset):
        return self.balance

    def lock_position(self, account_id, asset_id):
        return self.position

    def lock_order(self, order_id):
        return next(
            (order for order in self.orders.values() if order.id == order_id),
            None,
        )

    def add_position(self, position):
        self.position = position
        return position

    def delete_position(self, position):
        self.position = None

    def add_order(self, order):
        order.id = len(self.orders) + 1
        order.asset = self.asset
        order._pending_account = self.account
        order.submitted_at = datetime.now(timezone.utc)
        self.orders[order.client_order_id] = order
        self.account.orders.append(order)
        return order

    def add_fill(self, fill):
        self.saved_fills.append(fill)
        return fill

    def flush(self):
        return None

    def commit(self):
        self.commit_count += 1

    def rollback(self):
        self.rollback_count += 1


def _service(repo=None):
    repository = repo or FakeRepository()
    return CryptoOrderService(
        repository,
        FixedLiquidityProvider(),
    ), repository


def _buy(service, client_order_id="web-001"):
    return service.place_market_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id=client_order_id,
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
    )


def test_buy_debits_cash_creates_position_order_and_fills():
    service, repo = _service()

    result = _buy(service)

    assert result["status"] == "filled"
    assert result["filled_quantity"] == 0.02
    assert repo.balance.available == Decimal("7977.98000")
    assert repo.position.quantity == Decimal("0.02")
    assert repo.position.average_entry_price == Decimal("101101.000")
    assert len(repo.saved_fills) == 2
    assert repo.commit_count == 1


def test_duplicate_client_order_id_returns_existing_order_without_second_debit():
    service, repo = _service()

    first = _buy(service)
    first_balance = repo.balance.available
    second = _buy(service)

    assert second["order_id"] == first["order_id"]
    assert repo.balance.available == first_balance
    assert repo.commit_count == 1


def test_sell_rejects_when_position_is_too_small():
    service, repo = _service()
    repo.position = SimpleNamespace(
        quantity=Decimal("0.01"),
        average_entry_price=Decimal("90000"),
        cost_basis=Decimal("900"),
        realized_pnl=Decimal("0"),
    )

    with pytest.raises(
        InsufficientPositionError,
        match="Insufficient BTCUSDT position",
    ):
        service.place_market_order(
            user_id=3,
            contest_slug="practice-arena",
            client_order_id="web-002",
            symbol="BTCUSDT",
            side="sell",
            quantity=Decimal("0.02"),
        )

    assert repo.rollback_count == 1
    assert repo.balance.available == Decimal("10000")


def test_pending_limit_buy_moves_cash_to_locked_until_cancelled():
    service, repo = _service()

    order = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="limit-buy-001",
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
        order_type="limit",
        limit_price=Decimal("90000"),
    )

    assert order["status"] == "pending"
    assert order["requested_quantity"] == 0.02
    assert repo.balance.available == Decimal("8198.20000")
    assert repo.balance.locked == Decimal("1801.80000")

    cancelled = service.cancel_order(
        user_id=3,
        contest_slug="practice-arena",
        order_id=order["order_id"],
    )

    assert cancelled["status"] == "cancelled"
    assert repo.balance.available == Decimal("10000.00000")
    assert repo.balance.locked == Decimal("0.00000")


def test_pending_limit_sell_locks_position_quantity():
    service, repo = _service()
    repo.position = SimpleNamespace(
        asset_id=2,
        quantity=Decimal("0.02"),
        locked_quantity=Decimal("0"),
        average_entry_price=Decimal("90000"),
        cost_basis=Decimal("1800"),
        realized_pnl=Decimal("0"),
    )

    order = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="limit-sell-001",
        symbol="BTCUSDT",
        side="sell",
        quantity=Decimal("0.015"),
        order_type="limit",
        limit_price=Decimal("120000"),
    )

    assert order["status"] == "pending"
    assert repo.position.locked_quantity == Decimal("0.015")

    with pytest.raises(
        InsufficientPositionError,
        match="Insufficient BTCUSDT position",
    ):
        service.place_order(
            user_id=3,
            contest_slug="practice-arena",
            client_order_id="limit-sell-002",
            symbol="BTCUSDT",
            side="sell",
            quantity=Decimal("0.01"),
            order_type="limit",
            limit_price=Decimal("121000"),
        )


def test_cancel_pending_limit_sell_releases_position_quantity():
    service, repo = _service()
    repo.position = SimpleNamespace(
        asset_id=2,
        quantity=Decimal("0.02"),
        locked_quantity=Decimal("0"),
        average_entry_price=Decimal("90000"),
        cost_basis=Decimal("1800"),
        realized_pnl=Decimal("0"),
    )

    order = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="limit-sell-003",
        symbol="BTCUSDT",
        side="sell",
        quantity=Decimal("0.015"),
        order_type="limit",
        limit_price=Decimal("120000"),
    )
    service.cancel_order(
        user_id=3,
        contest_slug="practice-arena",
        order_id=order["order_id"],
    )

    assert repo.position.locked_quantity == Decimal("0.000")


def test_fill_pending_limit_buy_uses_locked_cash_and_creates_fill():
    service, repo = _service()
    order = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="limit-buy-fill-001",
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
        order_type="limit",
        limit_price=Decimal("90000"),
    )

    filled = service.fill_pending_limit_order(
        order_id=order["order_id"],
        fill_price=Decimal("90000"),
    )

    assert filled["status"] == "filled"
    assert repo.balance.available == Decimal("8198.20000")
    assert repo.balance.locked == Decimal("0.00000")
    assert repo.position.quantity == Decimal("0.02")
    assert repo.position.average_entry_price == Decimal("90090.000")
    assert repo.saved_fills[-1].liquidity_source == "historical_candle"


def test_fill_pending_limit_sell_releases_locked_position_quantity():
    service, repo = _service()
    repo.position = SimpleNamespace(
        asset_id=2,
        quantity=Decimal("0.02"),
        locked_quantity=Decimal("0"),
        average_entry_price=Decimal("90000"),
        cost_basis=Decimal("1800"),
        realized_pnl=Decimal("0"),
    )
    order = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="limit-sell-fill-001",
        symbol="BTCUSDT",
        side="sell",
        quantity=Decimal("0.015"),
        order_type="limit",
        limit_price=Decimal("120000"),
    )

    filled = service.fill_pending_limit_order(
        order_id=order["order_id"],
        fill_price=Decimal("120000"),
    )

    assert filled["status"] == "filled"
    assert repo.position.quantity == Decimal("0.005")
    assert repo.position.locked_quantity == Decimal("0.000")
    assert repo.balance.available == Decimal("11798.200000")
    assert repo.account.realized_pnl == Decimal("448.200000")


def test_fill_stop_loss_exit_creates_sell_order_and_marks_entry_triggered():
    service, repo = _service()
    entry = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="entry-with-sl-001",
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
        order_type="market",
        stop_loss_price=Decimal("90000"),
    )

    exit_order = service.fill_exit_trigger_order(
        entry_order_id=entry["order_id"],
        trigger_type="stop_loss",
        trigger_price=Decimal("90000"),
    )
    entry_order = repo.lock_order(entry["order_id"])

    assert exit_order["side"] == "sell"
    assert exit_order["order_type"] == "stop_loss"
    assert exit_order["status"] == "filled"
    assert entry_order.exit_trigger_type == "stop_loss"
    assert entry_order.exit_order_id == exit_order["order_id"]
    assert repo.position is None
    assert repo.saved_fills[-1].liquidity_source == "historical_candle"


def test_fill_take_profit_exit_only_sells_available_quantity_once():
    service, repo = _service()
    entry = service.place_order(
        user_id=3,
        contest_slug="practice-arena",
        client_order_id="entry-with-tp-001",
        symbol="BTCUSDT",
        side="buy",
        quantity=Decimal("0.02"),
        order_type="market",
        take_profit_price=Decimal("120000"),
    )
    repo.position.locked_quantity = Decimal("0.005")

    exit_order = service.fill_exit_trigger_order(
        entry_order_id=entry["order_id"],
        trigger_type="take_profit",
        trigger_price=Decimal("120000"),
    )
    repeated = service.fill_exit_trigger_order(
        entry_order_id=entry["order_id"],
        trigger_type="take_profit",
        trigger_price=Decimal("120000"),
    )

    assert exit_order["order_type"] == "take_profit"
    assert exit_order["filled_quantity"] == 0.015
    assert repeated["order_id"] == entry["order_id"]
    assert repo.position.quantity == Decimal("0.005")
    assert repo.position.locked_quantity == Decimal("0.005")
