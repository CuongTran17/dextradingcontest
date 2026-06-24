from decimal import Decimal

from sqlalchemy.orm import Session

from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestAsset,
    ContestParticipant,
    TradingAccount,
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

    def commit(self) -> None:
        self.db.commit()

