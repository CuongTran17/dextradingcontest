from decimal import Decimal

import pytest

from src.services.crypto_execution import (
    InsufficientDepthError,
    calculate_market_fill,
)


BOOK = {
    "bids": [
        {"price": 99.0, "quantity": 2.0},
        {"price": 98.0, "quantity": 3.0},
    ],
    "asks": [
        {"price": 101.0, "quantity": 1.0},
        {"price": 102.0, "quantity": 2.0},
    ],
}


def test_buy_walks_asks_and_returns_weighted_average():
    fill = calculate_market_fill(
        "buy",
        Decimal("2"),
        BOOK,
        Decimal("0.001"),
    )

    assert fill.quantity == Decimal("2")
    assert fill.notional == Decimal("203")
    assert fill.average_price == Decimal("101.5")
    assert fill.fee == Decimal("0.203")
    assert [item.price for item in fill.levels] == [
        Decimal("101.0"),
        Decimal("102.0"),
    ]


def test_sell_walks_bids():
    fill = calculate_market_fill(
        "sell",
        Decimal("3"),
        BOOK,
        Decimal("0.001"),
    )

    assert fill.notional == Decimal("296.0")
    assert fill.average_price == Decimal("98.66666666666666666666666667")


def test_insufficient_depth_rejects_whole_order():
    with pytest.raises(
        InsufficientDepthError,
        match="Insufficient order book depth",
    ):
        calculate_market_fill(
            "buy",
            Decimal("4"),
            BOOK,
            Decimal("0.001"),
        )


@pytest.mark.parametrize("quantity", [Decimal("0"), Decimal("-1")])
def test_non_positive_quantity_is_rejected(quantity):
    with pytest.raises(ValueError, match="Quantity must be greater than zero"):
        calculate_market_fill(
            "buy",
            quantity,
            BOOK,
            Decimal("0.001"),
        )


@pytest.mark.parametrize("side", ["hold", "", "BUY"])
def test_invalid_side_is_rejected(side):
    with pytest.raises(ValueError, match="Side must be buy or sell"):
        calculate_market_fill(
            side,
            Decimal("1"),
            BOOK,
            Decimal("0.001"),
        )


def test_limit_order_requires_limit_price():
    from unittest.mock import MagicMock
    from src.services.crypto_execution import CryptoOrderService

    mock_repo = MagicMock()
    mock_repo.get_order_by_client_id.return_value = None
    service = CryptoOrderService(mock_repo, MagicMock())
    with pytest.raises(ValueError, match="limit_price is required for limit orders"):
        service.place_order(
            user_id=1,
            contest_slug="practice-arena",
            client_order_id="limit-001",
            symbol="BTCUSDT",
            side="buy",
            quantity=Decimal("0.1"),
            order_type="limit",
            limit_price=None,
        )
