from datetime import datetime
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload

from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestAsset,
    ContestParticipant,
    CryptoAccountEvent,
    CryptoAsset,
    CryptoCertificateBatch,
    CryptoCertificateClaim,
    CryptoContestSettlement,
    CryptoFaucetClaim,
    CryptoOrderEvent,
    Position,
    TradeFill,
    TradingAccount,
    TradingOrder,
)
from src.database.user_models import User


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

    def get_contest_for_settlement(self, slug: str) -> Contest | None:
        return (
            self.db.query(Contest)
            .options(selectinload(Contest.assets).selectinload(ContestAsset.asset))
            .filter(Contest.slug == slug)
            .with_for_update()
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

    def list_settlements(self, contest_id: int) -> list[CryptoContestSettlement]:
        return (
            self.db.query(CryptoContestSettlement)
            .filter(CryptoContestSettlement.contest_id == contest_id)
            .order_by(CryptoContestSettlement.version.asc())
            .all()
        )

    def get_latest_settlement(self, contest_slug: str) -> CryptoContestSettlement | None:
        return (
            self.db.query(CryptoContestSettlement)
            .join(Contest, Contest.id == CryptoContestSettlement.contest_id)
            .filter(Contest.slug == contest_slug)
            .order_by(CryptoContestSettlement.version.desc())
            .first()
        )

    def list_admin_accounts(
        self,
        *,
        contest_slug: str | None = None,
        q: str | None = None,
        status: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[TradingAccount], int]:
        query = (
            self.db.query(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .join(User, User.id == ContestParticipant.user_id)
            .options(
                selectinload(TradingAccount.participant).selectinload(
                    ContestParticipant.contest
                ),
                selectinload(TradingAccount.participant).selectinload(
                    ContestParticipant.user
                ),
                selectinload(TradingAccount.balances),
                selectinload(TradingAccount.positions).selectinload(Position.asset),
                selectinload(TradingAccount.orders).selectinload(TradingOrder.asset),
            )
        )
        if contest_slug:
            query = query.filter(Contest.slug == contest_slug)
        if status:
            query = query.filter(TradingAccount.status == status)
        if q:
            like = f"%{q.strip()}%"
            query = query.filter((User.email.ilike(like)) | (User.fullname.ilike(like)))
        total = query.count()
        rows = (
            query.order_by(TradingAccount.updated_at.desc(), TradingAccount.id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return rows, total

    def get_admin_account_detail(self, account_id: int) -> TradingAccount | None:
        return (
            self.db.query(TradingAccount)
            .options(
                selectinload(TradingAccount.participant).selectinload(
                    ContestParticipant.contest
                ),
                selectinload(TradingAccount.participant).selectinload(
                    ContestParticipant.user
                ),
                selectinload(TradingAccount.balances),
                selectinload(TradingAccount.positions).selectinload(Position.asset),
                selectinload(TradingAccount.orders).selectinload(TradingOrder.fills),
                selectinload(TradingAccount.orders).selectinload(TradingOrder.asset),
            )
            .filter(TradingAccount.id == account_id)
            .first()
        )

    def admin_overview_counts(self) -> dict:
        users_total = self.db.query(User).count()
        users_locked = self.db.query(User).filter(User.is_locked.is_(True)).count()
        users_admins = self.db.query(User).filter(User.role == "admin").count()
        contests_total = self.db.query(Contest).count()
        contests_active = self.db.query(Contest).filter(Contest.status == "active").count()
        participants_total = self.db.query(ContestParticipant).count()
        accounts_total = self.db.query(TradingAccount).count()
        accounts_active = (
            self.db.query(TradingAccount)
            .filter(TradingAccount.status == "active")
            .count()
        )
        total_equity = sum(
            float(row[0] or 0)
            for row in self.db.query(TradingAccount.current_equity).all()
        )
        return {
            "users_total": users_total,
            "users_locked": users_locked,
            "users_admins": users_admins,
            "contests_total": contests_total,
            "contests_active": contests_active,
            "participants_total": participants_total,
            "accounts_total": accounts_total,
            "accounts_active": accounts_active,
            "total_equity": round(total_equity, 2),
        }

    def get_contest_participant_by_user(
        self,
        contest_slug: str,
        user_id: int,
    ) -> ContestParticipant | None:
        return (
            self.db.query(ContestParticipant)
            .join(Contest)
            .options(selectinload(ContestParticipant.account))
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
            )
            .first()
        )

    def get_participant_wallet(
        self,
        contest_slug: str,
        user_id: int,
    ) -> ContestParticipant | None:
        return self.get_contest_participant_by_user(contest_slug, user_id)

    def set_participant_wallet(
        self,
        participant: ContestParticipant,
        wallet_address: str,
        wallet_type: str,
        join_tx_signature: str,
        joined_onchain_at: datetime,
    ) -> ContestParticipant:
        participant.wallet_address = wallet_address
        participant.wallet_type = wallet_type
        participant.join_tx_signature = join_tx_signature
        participant.joined_onchain_at = joined_onchain_at
        return participant

    def mark_contest_onchain_initialized(
        self,
        contest: Contest,
        contest_address: str,
        initialize_tx_signature: str,
        admin_wallet: str,
        initialized_at: datetime,
    ) -> Contest:
        contest.onchain_contest_address = contest_address
        contest.onchain_initialize_tx_signature = initialize_tx_signature
        contest.onchain_admin_wallet = admin_wallet
        contest.onchain_initialized_at = initialized_at
        return contest

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

    def list_pending_limit_orders(self) -> list[TradingOrder]:
        return (
            self.db.query(TradingOrder)
            .join(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .options(
                selectinload(TradingOrder.account)
                .selectinload(TradingAccount.participant)
                .selectinload(ContestParticipant.contest),
                selectinload(TradingOrder.asset),
            )
            .filter(
                TradingOrder.order_type == "limit",
                TradingOrder.status == "pending",
                TradingOrder.limit_price.isnot(None),
                TradingAccount.status == "active",
                ContestParticipant.status == "active",
                Contest.status == "active",
            )
            .order_by(TradingOrder.submitted_at.asc(), TradingOrder.id.asc())
            .all()
        )

    def list_open_exit_trigger_orders(self) -> list[TradingOrder]:
        return (
            self.db.query(TradingOrder)
            .join(TradingAccount)
            .join(ContestParticipant)
            .join(Contest)
            .options(
                selectinload(TradingOrder.account)
                .selectinload(TradingAccount.participant)
                .selectinload(ContestParticipant.contest),
                selectinload(TradingOrder.asset),
            )
            .filter(
                TradingOrder.side == "buy",
                TradingOrder.status == "filled",
                TradingOrder.filled_quantity > 0,
                TradingOrder.exit_triggered_at.is_(None),
                or_(
                    TradingOrder.stop_loss_price.isnot(None),
                    TradingOrder.take_profit_price.isnot(None),
                ),
                TradingAccount.status == "active",
                ContestParticipant.status == "active",
                Contest.status == "active",
            )
            .order_by(TradingOrder.completed_at.asc(), TradingOrder.id.asc())
            .all()
        )

    def lock_order(self, order_id: int) -> TradingOrder | None:
        return (
            self.db.query(TradingOrder)
            .options(
                selectinload(TradingOrder.account)
                .selectinload(TradingAccount.participant)
                .selectinload(ContestParticipant.contest),
                selectinload(TradingOrder.asset),
            )
            .filter(TradingOrder.id == order_id)
            .with_for_update()
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

    def add_settlement(
        self,
        settlement: CryptoContestSettlement,
    ) -> CryptoContestSettlement:
        self.db.add(settlement)
        return settlement

    def add_certificate_claim(
        self,
        claim: CryptoCertificateClaim,
    ) -> CryptoCertificateClaim:
        self.db.add(claim)
        return claim

    def add_certificate_batch(
        self,
        batch: CryptoCertificateBatch,
    ) -> CryptoCertificateBatch:
        self.db.add(batch)
        self.db.flush()
        return batch

    def get_certificate_batch(
        self,
        contest_slug: str,
        batch_id: int,
    ) -> CryptoCertificateBatch | None:
        return (
            self.db.query(CryptoCertificateBatch)
            .join(Contest, Contest.id == CryptoCertificateBatch.contest_id)
            .filter(
                Contest.slug == contest_slug,
                CryptoCertificateBatch.id == batch_id,
            )
            .first()
        )

    def get_latest_authorized_certificate_batch(
        self,
        contest_slug: str,
    ) -> CryptoCertificateBatch | None:
        return (
            self.db.query(CryptoCertificateBatch)
            .join(Contest, Contest.id == CryptoCertificateBatch.contest_id)
            .filter(
                Contest.slug == contest_slug,
                CryptoCertificateBatch.status == "authorized",
            )
            .order_by(CryptoCertificateBatch.authorized_at.desc(), CryptoCertificateBatch.id.desc())
            .first()
        )

    def authorize_certificate_batch(
        self,
        batch: CryptoCertificateBatch,
        admin_wallet: str,
        tx_signature: str,
        authorized_at: datetime,
    ) -> CryptoCertificateBatch:
        batch.status = "authorized"
        batch.authorized_by_wallet = admin_wallet
        batch.authorize_tx_signature = tx_signature
        batch.authorized_at = authorized_at
        return batch

    def get_certificate_claim_for_user(
        self,
        contest_slug: str,
        user_id: int,
    ) -> CryptoCertificateClaim | None:
        return (
            self.db.query(CryptoCertificateClaim)
            .join(
                CryptoCertificateBatch,
                CryptoCertificateBatch.id == CryptoCertificateClaim.batch_id,
            )
            .join(
                ContestParticipant,
                ContestParticipant.id == CryptoCertificateClaim.participant_id,
            )
            .join(Contest, Contest.id == CryptoCertificateClaim.contest_id)
            .options(selectinload(CryptoCertificateClaim.batch))
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
                CryptoCertificateBatch.status == "authorized",
            )
            .order_by(
                CryptoCertificateBatch.authorized_at.desc(),
                CryptoCertificateBatch.id.desc(),
            )
            .first()
        )

    def get_certificate_claim_for_user_batch(
        self,
        contest_slug: str,
        user_id: int,
        batch_id: int,
    ) -> CryptoCertificateClaim | None:
        return (
            self.db.query(CryptoCertificateClaim)
            .join(
                CryptoCertificateBatch,
                CryptoCertificateBatch.id == CryptoCertificateClaim.batch_id,
            )
            .join(
                ContestParticipant,
                ContestParticipant.id == CryptoCertificateClaim.participant_id,
            )
            .join(Contest, Contest.id == CryptoCertificateClaim.contest_id)
            .options(selectinload(CryptoCertificateClaim.batch))
            .filter(
                Contest.slug == contest_slug,
                ContestParticipant.user_id == user_id,
                CryptoCertificateClaim.batch_id == batch_id,
                CryptoCertificateBatch.status == "authorized",
            )
            .first()
        )

    def mark_certificate_claimed(
        self,
        claim: CryptoCertificateClaim,
        mint_address: str | None,
        mint_tx_signature: str,
        claimed_at: datetime,
    ) -> CryptoCertificateClaim:
        claim.mint_address = mint_address
        claim.mint_tx_signature = mint_tx_signature
        claim.claimed_at = claimed_at
        return claim

    def get_latest_faucet_claim(
        self,
        user_id: int,
        wallet_address: str,
    ) -> CryptoFaucetClaim | None:
        return (
            self.db.query(CryptoFaucetClaim)
            .filter(
                CryptoFaucetClaim.user_id == user_id,
                CryptoFaucetClaim.wallet_address == wallet_address,
            )
            .order_by(CryptoFaucetClaim.claimed_at.desc(), CryptoFaucetClaim.id.desc())
            .first()
        )

    def add_faucet_claim(self, claim: CryptoFaucetClaim) -> CryptoFaucetClaim:
        self.db.add(claim)
        return claim

    def add_account_event(self, event: CryptoAccountEvent) -> CryptoAccountEvent:
        self.db.add(event)
        return event

    def add_order_event(self, event: CryptoOrderEvent) -> CryptoOrderEvent:
        self.db.add(event)
        return event

    def flush(self) -> None:
        self.db.flush()

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()
