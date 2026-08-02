from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from src.services.pending_order_processor import PendingOrderProcessor


class FakeMarketRepo:
    def __init__(self, candles):
        self.candles = candles
        self.calls = []

    def load_candles(self, symbol, interval, *, limit, start_time, end_time):
        self.calls.append(
            {
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
        return self.candles


class ExplodingMarketRepo:
    def load_candles(self, *args, **kwargs):
        raise AssertionError("disabled processor should not open the market repo")


def _order(side, limit_price):
    return SimpleNamespace(
        side=side,
        limit_price=Decimal(str(limit_price)),
        submitted_at=datetime(2026, 7, 28, 10, 0, 30, tzinfo=timezone.utc),
        asset=SimpleNamespace(symbol="BTCUSDT"),
    )


def _entry_order(*, stop_loss_price=None, take_profit_price=None):
    return SimpleNamespace(
        side="buy",
        submitted_at=datetime(2026, 7, 28, 10, 0, 30, tzinfo=timezone.utc),
        completed_at=datetime(2026, 7, 28, 10, 0, 40, tzinfo=timezone.utc),
        stop_loss_price=(
            Decimal(str(stop_loss_price)) if stop_loss_price is not None else None
        ),
        take_profit_price=(
            Decimal(str(take_profit_price)) if take_profit_price is not None else None
        ),
        asset=SimpleNamespace(symbol="BTCUSDT"),
    )


def test_pending_processor_triggers_buy_when_candle_low_reaches_limit():
    market = FakeMarketRepo(
        [
            {"time": 1, "open": 101, "high": 102, "low": 99, "close": 100},
        ]
    )
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=market,
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._order_was_triggered(_order("buy", 100)) is True
    assert market.calls[0]["symbol"] == "BTCUSDT"
    assert market.calls[0]["interval"] == "1m"


def test_pending_processor_triggers_sell_when_candle_high_reaches_limit():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=FakeMarketRepo(
            [
                {"time": 1, "open": 101, "high": 105, "low": 99, "close": 100},
            ]
        ),
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._order_was_triggered(_order("sell", 104)) is True


def test_pending_processor_skips_when_limit_is_not_reached():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=FakeMarketRepo(
            [
                {"time": 1, "open": 101, "high": 102, "low": 99, "close": 100},
            ]
        ),
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._order_was_triggered(_order("buy", 98)) is False
    assert processor._order_was_triggered(_order("sell", 103)) is False


def test_pending_processor_triggers_stop_loss_from_historical_candle():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=FakeMarketRepo(
            [
                {"time": 1, "open": 100, "high": 101, "low": 95, "close": 98},
            ]
        ),
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._exit_trigger_for_order(
        _entry_order(stop_loss_price=96, take_profit_price=110)
    ) == ("stop_loss", Decimal("96"))


def test_pending_processor_triggers_take_profit_from_historical_candle():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=FakeMarketRepo(
            [
                {"time": 1, "open": 100, "high": 111, "low": 99, "close": 110},
            ]
        ),
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._exit_trigger_for_order(
        _entry_order(stop_loss_price=96, take_profit_price=110)
    ) == ("take_profit", Decimal("110"))


def test_pending_processor_prefers_stop_loss_when_both_hit_same_candle():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo=FakeMarketRepo(
            [
                {"time": 1, "open": 100, "high": 111, "low": 95, "close": 100},
            ]
        ),
        now_provider=lambda: datetime(2026, 7, 28, 10, 2, tzinfo=timezone.utc),
    )

    assert processor._exit_trigger_for_order(
        _entry_order(stop_loss_price=96, take_profit_price=110)
    ) == ("stop_loss", Decimal("96"))


def test_disabled_pending_processor_does_not_open_market_repo():
    processor = PendingOrderProcessor(
        db_session_factory=lambda: None,
        market_repo_factory=lambda: ExplodingMarketRepo(),
        enabled=False,
    )

    assert processor.status()["enabled"] is False
