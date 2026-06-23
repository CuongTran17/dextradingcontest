import pytest

from src.services.crypto_simulator import execute_market_order, portfolio_metrics


def empty_portfolio():
    return {"contest_id": "practice-arena", "cash": 10000.0, "positions": [], "orders": []}


def test_buy_decreases_cash_and_creates_position():
    portfolio = execute_market_order(empty_portfolio(), "BTCUSDT", "buy", 0.1, 50000.0)

    assert portfolio["cash"] == pytest.approx(4995.0)
    assert portfolio["positions"][0]["symbol"] == "BTCUSDT"
    assert portfolio["positions"][0]["quantity"] == pytest.approx(0.1)


def test_oversized_sell_raises_value_error():
    with pytest.raises(ValueError, match="Insufficient BTCUSDT position"):
        execute_market_order(empty_portfolio(), "BTCUSDT", "sell", 0.1, 50000.0)


def test_metrics_calculate_equity_and_roi():
    portfolio = execute_market_order(empty_portfolio(), "ETHUSDT", "buy", 1.0, 3000.0)

    metrics = portfolio_metrics(portfolio, {"ETHUSDT": 3300.0})

    assert metrics["equity"] > 10000
    assert metrics["roi"] > 0

