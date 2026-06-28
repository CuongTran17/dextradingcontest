from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal

from src.database.crypto_models import Position, TradeFill, TradingOrder
from src.services.crypto_accounts import serialize_order


class InsufficientDepthError(ValueError):
    pass


class AccountUnavailableError(ValueError):
    pass


class AssetUnavailableError(ValueError):
    pass


class InsufficientBalanceError(ValueError):
    pass


class InsufficientPositionError(ValueError):
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


class CryptoOrderService:
    def __init__(self, repo, liquidity_provider, now_provider=None):
        self.repo = repo
        self.liquidity_provider = liquidity_provider
        self.now_provider = now_provider or (lambda: datetime.now(timezone.utc))

    def place_market_order(
        self,
        *,
        user_id: int,
        contest_slug: str,
        client_order_id: str,
        symbol: str,
        side: str,
        quantity: Decimal,
    ) -> dict:
        existing = self.repo.get_order_by_client_id(
            user_id,
            contest_slug,
            client_order_id,
        )
        if existing is not None:
            return serialize_order(existing)

        try:
            account = self.repo.lock_account_for_user(
                contest_slug,
                user_id,
            )
            participant_status = getattr(
                getattr(account, "participant", None),
                "status",
                None,
            )
            if (
                account is None
                or account.status != "active"
                or participant_status != "active"
            ):
                raise AccountUnavailableError("Trading account is not active")
            contest = getattr(getattr(account, "participant", None), "contest", None)
            if contest is not None and not self._contest_is_open_for_trading(contest):
                raise AccountUnavailableError("Contest is not open for trading")

            market = self.repo.get_enabled_asset(contest_slug, symbol)
            if market is None:
                raise AssetUnavailableError(
                    f"{symbol} is not enabled for this contest"
                )
            asset, contest = market
            if not self._contest_is_open_for_trading(contest):
                raise AccountUnavailableError("Contest is not open for trading")
            if quantity < Decimal(asset.min_quantity):
                raise ValueError(
                    f"Minimum quantity for {symbol} is {asset.min_quantity}"
                )

            book = self.liquidity_provider.get_order_book(symbol, 100)
            fee_rate = Decimal(contest.fee_rate)
            fill = calculate_market_fill(
                side,
                Decimal(quantity),
                book,
                fee_rate,
            )
            if fill.notional < Decimal(asset.min_notional):
                raise ValueError(
                    f"Minimum notional for {symbol} is {asset.min_notional}"
                )

            cash = self.repo.lock_balance(
                account.id,
                contest.quote_asset,
            )
            if cash is None:
                raise InsufficientBalanceError(
                    f"{contest.quote_asset} balance not found"
                )
            position = self.repo.lock_position(account.id, asset.id)

            if side == "buy":
                position = self._apply_buy(
                    account,
                    cash,
                    position,
                    asset,
                    fill,
                )
            else:
                self._apply_sell(
                    account,
                    cash,
                    position,
                    symbol,
                    fill,
                )

            order = self._persist_order_and_fills(
                account=account,
                asset=asset,
                contest=contest,
                client_order_id=client_order_id,
                side=side,
                fill=fill,
                market_price=Decimal(
                    str(book.get("mid_price", fill.average_price))
                ),
            )
            account.current_equity = (
                Decimal(account.current_equity) - fill.fee
            )
            account.version = int(account.version) + 1
            self.repo.commit()
            return serialize_order(order)
        except Exception:
            self.repo.rollback()
            raise

    def _contest_is_open_for_trading(self, contest) -> bool:
        if getattr(contest, "mode", None) == "practice":
            return getattr(contest, "status", None) == "active"
        if getattr(contest, "status", None) != "active":
            return False

        now = self._as_aware_utc(self.now_provider())
        starts_at = self._as_aware_utc(getattr(contest, "starts_at", None))
        ends_at = self._as_aware_utc(getattr(contest, "ends_at", None))

        if starts_at is not None and now < starts_at:
            return False
        if ends_at is not None and now >= ends_at:
            return False
        return True

    @staticmethod
    def _as_aware_utc(value):
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _apply_buy(
        self,
        account,
        cash,
        position,
        asset,
        fill: MarketFill,
    ):
        total_cost = fill.notional + fill.fee
        if Decimal(cash.available) < total_cost:
            raise InsufficientBalanceError(
                "Insufficient USDT_TEST balance"
            )

        cash.available = Decimal(cash.available) - total_cost
        if position is None:
            position = Position(
                account_id=account.id,
                asset_id=asset.id,
                asset=asset,
                quantity=Decimal("0"),
                average_entry_price=Decimal("0"),
                cost_basis=Decimal("0"),
                realized_pnl=Decimal("0"),
            )
            self.repo.add_position(position)

        previous_cost = Decimal(position.cost_basis)
        next_quantity = Decimal(position.quantity) + fill.quantity
        next_cost = previous_cost + total_cost
        position.quantity = next_quantity
        position.cost_basis = next_cost
        position.average_entry_price = next_cost / next_quantity
        return position

    def _apply_sell(
        self,
        account,
        cash,
        position,
        symbol: str,
        fill: MarketFill,
    ) -> None:
        if position is None or Decimal(position.quantity) < fill.quantity:
            raise InsufficientPositionError(
                f"Insufficient {symbol} position"
            )

        net_proceeds = fill.notional - fill.fee
        average_entry = Decimal(position.average_entry_price)
        removed_cost = average_entry * fill.quantity
        realized_pnl = net_proceeds - removed_cost

        cash.available = Decimal(cash.available) + net_proceeds
        position.quantity = Decimal(position.quantity) - fill.quantity
        position.realized_pnl = (
            Decimal(position.realized_pnl) + realized_pnl
        )
        position.cost_basis = average_entry * Decimal(position.quantity)
        account.realized_pnl = (
            Decimal(account.realized_pnl) + realized_pnl
        )

        if Decimal(position.quantity) == 0:
            self.repo.delete_position(position)

    def _persist_order_and_fills(
        self,
        *,
        account,
        asset,
        contest,
        client_order_id: str,
        side: str,
        fill: MarketFill,
        market_price: Decimal,
    ) -> TradingOrder:
        completed_at = datetime.now(timezone.utc)
        order = TradingOrder(
            client_order_id=client_order_id,
            account_id=account.id,
            asset_id=asset.id,
            asset=asset,
            side=side,
            order_type="market",
            status="filled",
            requested_quantity=fill.quantity,
            filled_quantity=fill.quantity,
            average_fill_price=fill.average_price,
            estimated_notional=market_price * fill.quantity,
            executed_notional=fill.notional,
            fee_amount=fill.fee,
            fee_asset=contest.quote_asset,
            market_price_at_submission=market_price,
            completed_at=completed_at,
        )
        self.repo.add_order(order)
        self.repo.flush()

        fee_rate = Decimal(contest.fee_rate)
        for sequence, level in enumerate(fill.levels, start=1):
            self.repo.add_fill(
                TradeFill(
                    order_id=order.id,
                    fill_sequence=sequence,
                    price=level.price,
                    quantity=level.quantity,
                    notional=level.notional,
                    fee_amount=level.notional * fee_rate,
                    fee_asset=contest.quote_asset,
                    liquidity_source="simulated_orderbook",
                    executed_at=completed_at,
                )
            )

        return order
