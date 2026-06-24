from dataclasses import dataclass
from decimal import Decimal


class InsufficientDepthError(ValueError):
    pass


@dataclass(frozen=True)
class FillLevel:
    price: Decimal
    quantity: Decimal
    notional: Decimal


@dataclass(frozen=True)
class MarketFill:
    quantity: Decimal
    notional: Decimal
    average_price: Decimal
    fee: Decimal
    levels: tuple[FillLevel, ...]


def calculate_market_fill(
    side: str,
    quantity: Decimal,
    book: dict,
    fee_rate: Decimal,
) -> MarketFill:
    if side not in {"buy", "sell"}:
        raise ValueError("Side must be buy or sell")
    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero")

    rows = book["asks"] if side == "buy" else book["bids"]
    remaining = quantity
    levels: list[FillLevel] = []

    for row in rows:
        if remaining <= 0:
            break

        price = Decimal(str(row["price"]))
        available = Decimal(str(row["quantity"]))
        taken = min(remaining, available)
        levels.append(
            FillLevel(
                price=price,
                quantity=taken,
                notional=price * taken,
            )
        )
        remaining -= taken

    if remaining > 0:
        raise InsufficientDepthError("Insufficient order book depth")

    notional = sum(
        (level.notional for level in levels),
        Decimal("0"),
    )
    return MarketFill(
        quantity=quantity,
        notional=notional,
        average_price=notional / quantity,
        fee=notional * fee_rate,
        levels=tuple(levels),
    )
