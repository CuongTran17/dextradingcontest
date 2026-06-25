from sqlalchemy import Numeric, UniqueConstraint

from src.database.base import Base
from src.database.crypto_models import (
    AccountBalance,
    ContestAsset,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradeFill,
    TradingAccount,
    TradingOrder,
)
from src.database.user_models import User


def _unique_constraint_names(model) -> set[str]:
    return {
        item.name
        for item in model.__table__.constraints
        if isinstance(item, UniqueConstraint) and item.name
    }


def test_crypto_models_define_account_isolation_constraints():
    assert "uq_crypto_asset_market_symbol" in _unique_constraint_names(CryptoAsset)
    assert "uq_contest_asset" in _unique_constraint_names(ContestAsset)
    assert "uq_contest_participant" in _unique_constraint_names(ContestParticipant)
    assert "uq_account_balance_asset" in _unique_constraint_names(AccountBalance)
    assert "uq_position_account_asset" in _unique_constraint_names(Position)
    assert "uq_order_client_id" in _unique_constraint_names(TradingOrder)
    assert "uq_fill_sequence" in _unique_constraint_names(TradeFill)
    assert TradingAccount.__table__.c.contest_participant_id.unique is True


def test_money_columns_use_fixed_precision():
    columns = [
        AccountBalance.__table__.c.available,
        Position.__table__.c.quantity,
        Position.__table__.c.average_entry_price,
        TradingOrder.__table__.c.executed_notional,
        TradeFill.__table__.c.price,
    ]

    assert all(isinstance(column.type, Numeric) for column in columns)


def test_production_metadata_contains_only_user_and_crypto_tables():
    assert User.__tablename__ == "users"
    assert {
        "users",
        "crypto_assets",
        "contests",
        "contest_assets",
        "contest_participants",
        "trading_accounts",
        "account_balances",
        "crypto_positions",
        "crypto_orders",
        "crypto_trade_fills",
    } == set(Base.metadata.tables)
