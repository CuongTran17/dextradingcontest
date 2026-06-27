from datetime import datetime, timezone

from src.database.crypto_models import Contest, ContestAsset
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.crypto_trading import ContestCreate, ContestUpdate
from src.services.binance_market_data import get_latest_prices


class ContestNotFoundError(Exception):
    pass


class ContestValidationError(Exception):
    pass


class ParticipantNotFoundError(Exception):
    pass


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _public_status(contest: Contest) -> str:
    if contest.mode == "practice":
        return "practice"
    if contest.status in {"draft", "scheduled"}:
        return "upcoming"
    if contest.status in {"active", "settling"}:
        return "active"
    return "ended"


class CryptoContestService:
    def __init__(self, repository: CryptoTradingRepository, price_provider=None):
        self.repository = repository
        self.price_provider = price_provider or get_latest_prices

    def list_contests(self) -> list[dict]:
        return [self._map_contest(contest) for contest in self.repository.list_contests()]

    def get_contest(self, slug: str) -> dict:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")
        return self._map_contest(contest)

    def create_contest(self, body: ContestCreate, created_by: int | None) -> dict:
        if self.repository.get_contest_by_slug(body.slug):
            raise ContestValidationError(f"Contest slug '{body.slug}' already exists")
        assets = self.repository.get_assets_by_symbols(list(dict.fromkeys(body.symbols)))
        found = {asset.symbol for asset in assets}
        missing = [symbol for symbol in body.symbols if symbol not in found]
        if missing:
            raise ContestValidationError(f"Unsupported symbols: {', '.join(missing)}")

        contest = Contest(
            slug=body.slug,
            title=body.title,
            mode=body.mode,
            status=body.status,
            initial_balance=body.initial_balance,
            quote_asset=body.quote_asset,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            fee_rate=body.fee_rate,
            rules_json="{}",
            created_by=created_by,
        )
        for asset in assets:
            contest.assets.append(ContestAsset(asset=asset, is_enabled=True))

        self.repository.db.add(contest)
        self.repository.commit()
        return self._map_contest(contest)

    def update_contest(self, slug: str, body: ContestUpdate) -> dict:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")

        if body.title is not None:
            contest.title = body.title
        if body.status is not None:
            contest.status = body.status
        if body.starts_at is not None:
            contest.starts_at = body.starts_at
        if body.ends_at is not None:
            contest.ends_at = body.ends_at
        if body.symbols is not None:
            assets = self.repository.get_assets_by_symbols(list(dict.fromkeys(body.symbols)))
            found = {asset.symbol for asset in assets}
            missing = [symbol for symbol in body.symbols if symbol not in found]
            if missing:
                raise ContestValidationError(f"Unsupported symbols: {', '.join(missing)}")
            contest.assets.clear()
            for asset in assets:
                contest.assets.append(ContestAsset(asset=asset, is_enabled=True))

        self.repository.commit()
        return self._map_contest(contest)

    def set_contest_status(self, slug: str, status: str) -> dict:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")
        if status not in {
            "draft",
            "scheduled",
            "active",
            "settling",
            "completed",
            "cancelled",
        }:
            raise ContestValidationError("Invalid contest status")

        contest.status = status
        self.repository.commit()
        return self._map_contest(contest)

    def get_leaderboard(self, slug: str) -> list[dict]:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")

        participants = self.repository.list_contest_participants(slug)
        symbols = [
            item.asset.symbol
            for item in contest.assets
            if item.is_enabled and item.asset.is_active
        ]
        prices = self.price_provider(symbols)
        user_names = self._user_display_names([participant.user_id for participant in participants])
        rows = []

        for participant in participants:
            account = participant.account
            if account is None:
                continue

            cash = sum(
                float(balance.available)
                for balance in account.balances
                if balance.asset == contest.quote_asset
            )
            position_value = sum(
                float(position.quantity) * float(prices.get(position.asset.symbol, 0))
                for position in account.positions
            )
            equity = cash + position_value
            initial = float(account.initial_equity)
            pnl = equity - initial
            filled_orders = [order for order in account.orders if order.status == "filled"]
            volume = sum(float(order.executed_notional) for order in filled_orders)
            last_order = max(account.orders, key=lambda order: order.submitted_at, default=None)

            rows.append(
                {
                    "rank": 0,
                    "user": user_names.get(participant.user_id, f"user-{participant.user_id}"),
                    "equity": round(equity, 2),
                    "pnl": round(pnl, 2),
                    "roi": round((pnl / initial) * 100, 4) if initial else 0,
                    "volume": round(volume, 2),
                    "trade_count": len(filled_orders),
                    "last_trade": (
                        f"{last_order.asset.symbol} {last_order.side}"
                        if last_order is not None
                        else None
                    ),
                }
            )

        rows.sort(key=lambda row: row["equity"], reverse=True)
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        return rows

    def list_participants(self, slug: str) -> list[dict]:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")

        participants = self.repository.list_contest_participants(slug)
        return self._participant_rows(contest, participants)

    def set_participant_status(self, slug: str, user_id: int, status: str) -> dict:
        if status not in {"active", "locked", "disqualified"}:
            raise ContestValidationError("Invalid participant status")

        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")

        participant = self.repository.get_contest_participant_by_user(slug, user_id)
        if participant is None:
            raise ParticipantNotFoundError("Contest participant not found")

        participant.status = status
        if participant.account is not None:
            participant.account.status = "active" if status == "active" else "frozen"
        self.repository.commit()
        return self._participant_rows(contest, [participant])[0]

    def _map_contest(self, contest: Contest) -> dict:
        enabled_assets = [
            item.asset
            for item in contest.assets
            if item.is_enabled and item.asset.is_active
        ]
        return {
            "id": contest.slug,
            "title": contest.title,
            "status": _public_status(contest),
            "raw_status": contest.status,
            "mode": contest.mode,
            "initial_capital": float(contest.initial_balance),
            "quote_asset": contest.quote_asset,
            "symbols": [asset.symbol for asset in enabled_assets],
            "starts_at": _iso(contest.starts_at),
            "ends_at": _iso(contest.ends_at),
            "participant_count": len(contest.participants),
        }

    def _participant_rows(self, contest: Contest, participants: list) -> list[dict]:
        symbols = [
            item.asset.symbol
            for item in contest.assets
            if item.is_enabled and item.asset.is_active
        ]
        prices = self.price_provider(symbols)
        user_names = self._user_display_names([participant.user_id for participant in participants])
        rows = [
            self._map_participant_row(contest, participant, prices, user_names)
            for participant in participants
            if participant.account is not None
        ]
        return sorted(rows, key=lambda row: row["equity"], reverse=True)

    def _map_participant_row(
        self,
        contest: Contest,
        participant,
        prices: dict[str, float],
        user_names: dict[int, str],
    ) -> dict:
        account = participant.account
        cash = sum(
            float(balance.available)
            for balance in account.balances
            if balance.asset == contest.quote_asset
        )
        position_value = sum(
            float(position.quantity) * float(prices.get(position.asset.symbol, 0))
            for position in account.positions
        )
        equity = cash + position_value
        initial = float(account.initial_equity)
        pnl = equity - initial
        filled_orders = [order for order in account.orders if order.status == "filled"]
        volume = sum(float(order.executed_notional) for order in filled_orders)
        last_order = max(account.orders, key=lambda order: order.submitted_at, default=None)
        return {
            "user_id": participant.user_id,
            "user": user_names.get(participant.user_id, f"user-{participant.user_id}"),
            "status": participant.status,
            "account_status": account.status,
            "equity": round(equity, 2),
            "pnl": round(pnl, 2),
            "roi": round((pnl / initial) * 100, 4) if initial else 0,
            "volume": round(volume, 2),
            "trade_count": len(filled_orders),
            "last_trade": (
                f"{last_order.asset.symbol} {last_order.side}"
                if last_order is not None
                else None
            ),
        }

    def _user_display_names(self, user_ids: list[int]) -> dict[int, str]:
        if not user_ids:
            return {}
        users = self.repository.db.query(User).filter(User.id.in_(user_ids)).all()
        return {
            user.id: user.fullname or user.email or f"user-{user.id}"
            for user in users
        }
