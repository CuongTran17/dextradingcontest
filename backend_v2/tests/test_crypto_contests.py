from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.crypto_models import Contest, ContestAsset, CryptoAsset
from src.database.user_models import User  # noqa: F401
from src.repositories.crypto_trading import CryptoTradingRepository


@compiles(LONGTEXT, "sqlite")
def _compile_longtext_for_sqlite(_type, _compiler, **_kw):
    return "TEXT"


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


def test_repository_lists_contests_with_enabled_symbols(db_session):
    btc = CryptoAsset(
        id=1,
        exchange="binance",
        market_type="spot",
        symbol="BTCUSDT",
        base_asset="BTC",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=6,
        min_quantity=Decimal("0.000001"),
        min_notional=Decimal("5"),
        is_active=True,
    )
    eth = CryptoAsset(
        id=2,
        exchange="binance",
        market_type="spot",
        symbol="ETHUSDT",
        base_asset="ETH",
        quote_asset="USDT",
        price_precision=2,
        quantity_precision=5,
        min_quantity=Decimal("0.00001"),
        min_notional=Decimal("5"),
        is_active=True,
    )
    contest = Contest(
        id=1,
        slug="practice-arena",
        title="Practice Arena",
        mode="practice",
        status="active",
        initial_balance=Decimal("10000"),
        quote_asset="USDT_TEST",
        starts_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ends_at=datetime(2026, 7, 1, tzinfo=timezone.utc),
        fee_rate=Decimal("0.001"),
        rules_json="{}",
    )
    contest.assets.append(ContestAsset(id=1, asset=btc, is_enabled=True))
    contest.assets.append(ContestAsset(id=2, asset=eth, is_enabled=True))
    db_session.add(contest)
    db_session.commit()

    rows = CryptoTradingRepository(db_session).list_contests()

    assert len(rows) == 1
    assert rows[0].slug == "practice-arena"
    assert [asset.asset.symbol for asset in rows[0].assets] == ["BTCUSDT", "ETHUSDT"]
