from decimal import Decimal

from sqlalchemy.orm import Session, selectinload

from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestAsset,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradeFill,
    TradingAccount,
    TradingOrder,
)


class CryptoTradingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_contest(self, slug: str) -> Contest | None:
        return (
            self.db.query(Contest)
            .filter(
                Contest.slug == slug,
                Contest.status.in_(("active", "scheduled")),
            )
            .first()
        )

    def list_contests(self) -> list[Contest]:
        return (
            self.db.query(Contest)
            .options(selectinload(Contest.assets).selectinload(ContestAsset.asset))
            .order_by(Contest.starts_at.desc(), Contest.id.desc())
            .all()
        )

    def get_contest_by_slug(self, slug: str) -> Contest | None:
        return (
            self.db.query(Contest)
            .options(selectinload(Contest.assets).selectinload(ContestAsset.asset))
            .filter(Contest.slug == slug)
            .first()
        )

    def get_assets_by_symbols(self, symbols: list[str]) -> list[CryptoAsset]:
        return (
            self.db.query(CryptoAsset)
            .filter(
                CryptoAsset.symbol.in_(symbols),
                CryptoAsset.is_active.is_(True),
            )
            .order_by(CryptoAsset.symbol.asc())
            .all()
        )

    def get_participant(
        self,
        contest_id: int,
        user_id: int,
    ) -> ContestParticipant | None:
        return (
            self.db.query(ContestParticipant)
            .filter_by(contest_id=contest_id, user_id=user_id)
            .first()
        )

    def list_contest_participants(self, contest_slug: str) -> list[ContestParticipant]:
        return (
            self.db.query(ContestParticipant)
            .join(Contest)
            .options(
                selectinload(ContestParticipant.account).selectinload(
                    TradingAccount.balances
                ),
                selectinload(ContestParticipant.account)
                .selectinload(TradingAccount.positions)
                .selectinload(Position.asset),
                selectinload(ContestParticipant.account)
                .selectinload(TradingAccount.orders)
                .selectinload(TradingOrder.asset),
            )
            .filter(Contest.slug == contest_slug)
            .all()
        )

    def create_participant(
        self,
        contest_id: int,
        user_id: int,
    ) -> ContestParticipant:
        participant = ContestParticipant(
            contest_id=contest_id,
            user_id=user_id,
            status="active",
        )
        self.db.add(participant)
        self.db.flush()
        return participant

    def get_account_for_participant(
        self,
        participant_id: int,
    ) -> TradingAccount | None:
        return (
            self.db.query(TradingAccount)
            .filter_by(contest_participant_id=participant_id)
            .first()
        )

    def create_account(
        self,
        participant_id: int,
        initial_balance: Decimal,
        quote_asset: str,
    ) -> TradingAccount:
        account = TradingAccount(
            contest_participant_id=participant_id,
            status="active",
            initial_equity=initial_balance,
            current_equity=initial_balance,
            realized_pnl=Decimal("0"),
            unrealized_pnl=Decimal("0"),
        )
        account.balances.append(
            AccountBalance(
                asset=quote_asset,
                available=initial_balance,
                locked=Decimal("0"),
            )
        )
        self.db.add(account)
        self.db.flush()
        return account

    def get_account_for_user(
        self,
        contest_slug: str,
        user_id: int,
    ) -> TradingAccount | None:
        return (
            self.db.query(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
            )
            .first()
        )

    def list_contest_assets(self, contest_id: int) -> list[ContestAsset]:
        return (
            self.db.query(ContestAsset)
            .filter_by(contest_id=contest_id, is_enabled=True)
            .all()
        )

    def get_order_by_client_id(
        self,
        user_id: int,
        contest_slug: str,
        client_order_id: str,
    ) -> TradingOrder | None:
        return (
            self.db.query(TradingOrder)
            .join(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
                TradingOrder.client_order_id == client_order_id,
            )
            .first()
        )

    def lock_account_for_user(
        self,
        contest_slug: str,
        user_id: int,
    ) -> TradingAccount | None:
        return (
            self.db.query(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
            )
            .with_for_update()
            .first()
        )

    def get_enabled_asset(
        self,
        contest_slug: str,
        symbol: str,
    ) -> tuple[CryptoAsset, Contest] | None:
        row = (
            self.db.query(CryptoAsset, Contest)
            .join(ContestAsset, ContestAsset.asset_id == CryptoAsset.id)
            .join(Contest, Contest.id == ContestAsset.contest_id)
            .filter(
                Contest.slug == contest_slug,
                ContestAsset.is_enabled.is_(True),
                CryptoAsset.symbol == symbol,
                CryptoAsset.is_active.is_(True),
            )
            .first()
        )
        return tuple(row) if row else None

    def lock_balance(
        self,
        account_id: int,
        asset: str,
    ) -> AccountBalance | None:
        return (
            self.db.query(AccountBalance)
            .filter_by(account_id=account_id, asset=asset)
            .with_for_update()
            .first()
        )

    def lock_position(
        self,
        account_id: int,
        asset_id: int,
    ) -> Position | None:
        return (
            self.db.query(Position)
            .filter_by(account_id=account_id, asset_id=asset_id)
            .with_for_update()
            .first()
        )

    def add_position(self, position: Position) -> Position:
        self.db.add(position)
        return position

    def delete_position(self, position: Position) -> None:
        self.db.delete(position)

    def add_order(self, order: TradingOrder) -> TradingOrder:
        self.db.add(order)
        return order

    def add_fill(self, fill: TradeFill) -> TradeFill:
        self.db.add(fill)
        return fill

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
