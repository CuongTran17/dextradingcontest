from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

FEE_RATE = 0.001
SLIPPAGE_RATE = 0.0005
INITIAL_CAPITAL = 10000.0


def execute_market_order(
    portfolio: dict[str, Any],
    symbol: str,
    side: str,
    quantity: float,
    latest_price: float,
) -> dict[str, Any]:
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")
    if side not in {"buy", "sell"}:
        raise ValueError("Side must be buy or sell")

    next_portfolio = deepcopy(portfolio)
    next_portfolio.setdefault("positions", [])
    next_portfolio.setdefault("orders", [])
    next_portfolio.setdefault("cash", INITIAL_CAPITAL)

    execution_price = float(latest_price)
    notional = execution_price * quantity
    fee = notional * FEE_RATE
    slippage = notional * SLIPPAGE_RATE
    positions = next_portfolio["positions"]

    if side == "buy":
        total_cost = notional + fee
        if next_portfolio["cash"] < total_cost:
            raise ValueError("Insufficient USDT_TEST balance")
        next_portfolio["cash"] -= total_cost
        position = _find_position(positions, symbol)
        if position:
            previous_notional = position["quantity"] * position["average_entry"]
            next_quantity = position["quantity"] + quantity
            position["quantity"] = next_quantity
            position["average_entry"] = (previous_notional + notional) / next_quantity
        else:
            positions.append({"symbol": symbol, "quantity": quantity, "average_entry": execution_price})
    else:
        position = _find_position(positions, symbol)
        if not position or position["quantity"] < quantity:
            raise ValueError(f"Insufficient {symbol} position")
        next_portfolio["cash"] += notional - fee
        position["quantity"] -= quantity

    next_portfolio["positions"] = [position for position in positions if position["quantity"] > 1e-12]
    next_portfolio["orders"].append(
        {
            "id": str(uuid4()),
            "contest_id": next_portfolio.get("contest_id", "practice-arena"),
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "execution_price": execution_price,
            "notional": notional,
            "fee": fee,
            "slippage": slippage,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return next_portfolio


def portfolio_metrics(
    portfolio: dict[str, Any],
    latest_prices: dict[str, float],
) -> dict[str, float | int]:
    positions_value = sum(
        position["quantity"] * latest_prices.get(position["symbol"], position["average_entry"])
        for position in portfolio.get("positions", [])
    )
    equity = portfolio.get("cash", 0.0) + positions_value
    pnl = equity - INITIAL_CAPITAL
    volume = sum(order.get("notional", 0.0) for order in portfolio.get("orders", []))
    return {
        "cash": portfolio.get("cash", 0.0),
        "positions_value": positions_value,
        "equity": equity,
        "pnl": pnl,
        "roi": (pnl / INITIAL_CAPITAL) * 100,
        "volume": volume,
        "trade_count": len(portfolio.get("orders", [])),
    }


def _find_position(positions: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    return next((position for position in positions if position.get("symbol") == symbol), None)
