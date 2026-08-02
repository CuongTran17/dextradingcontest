from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker

from src.database.base import Base
from src.database.crypto_models import (
    AccountBalance,
    Contest,
    ContestAsset,
    ContestParticipant,
    CryptoAsset,
    Position,
    TradingAccount,
    TradingOrder,
)
from src.database.user_models import User
from src.repositories.crypto_trading import CryptoTradingRepository
from src.services.crypto_contests import CryptoContestService


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


def test_service_lists_contests_without_lazy_loading_participants(db_session):
    user = User(
        id=201,
        email="student@example.com",
        password_hash="hash",
        fullname="Student",
        role="user",
    )
    btc = CryptoAsset(
        id=201,
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
    contests = [
        Contest(
            id=201 + index,
            slug=f"contest-{index}",
            title=f"Contest {index}",
            mode="practice",
            status="active",
            initial_balance=Decimal("10000"),
            quote_asset="USDT_TEST",
            starts_at=datetime(2026, 6, 1 + index, tzinfo=timezone.utc),
            ends_at=datetime(2026, 7, 1 + index, tzinfo=timezone.utc),
            fee_rate=Decimal("0.001"),
            rules_json="{}",
        )
        for index in range(2)
    ]
    for index, contest in enumerate(contests):
        contest.assets.append(ContestAsset(id=201 + index, asset=btc, is_enabled=True))
    participants = [
        ContestParticipant(
            id=201 + index,
            contest_id=contest.id,
            user_id=201,
            status="active",
        )
        for index, contest in enumerate(contests)
    ]
    db_session.add_all([user, btc, *contests, *participants])
    db_session.commit()
    statements: list[str] = []
    event.listen(
        db_session.bind,
        "before_cursor_execute",
        lambda _conn, _cursor, statement, _params, _context, _executemany: statements.append(statement),
    )
    Session = sessionmaker(bind=db_session.bind)
    request_session = Session()
    try:
        service = CryptoContestService(CryptoTradingRepository(request_session))
        rows = service.list_contests()
    finally:
        request_session.close()

    assert [row["participant_count"] for row in rows] == [1, 1]
    lazy_participant_selects = [
        statement.lower()
        for statement in statements
        if "from contest_participants" in statement.lower()
        and "where ? = contest_participants.contest_id" in statement.lower()
    ]
    assert lazy_participant_selects == []


def test_leaderboard_ranks_accounts_by_cash_plus_position_value(db_session):
    user_a = User(
        id=1,
        email="a@example.com",
        password_hash="hash",
        fullname="Student A",
        role="user",
    )
    user_b = User(
        id=2,
        email="b@example.com",
        password_hash="hash",
        fullname="Student B",
        role="user",
    )
    btc = CryptoAsset(
        id=10,
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
    contest = Contest(
        id=10,
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
    contest.assets.append(ContestAsset(id=10, asset=btc, is_enabled=True))
    participant_a = ContestParticipant(
        id=10,
        contest_id=10,
        user_id=1,
        status="active",
    )
    participant_b = ContestParticipant(
        id=11,
        contest_id=10,
        user_id=2,
        status="active",
    )
    account_a = TradingAccount(
        id=10,
        contest_participant_id=10,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    account_a.balances.append(
        AccountBalance(
            id=10,
            asset="USDT_TEST",
            available=Decimal("10000"),
            locked=Decimal("0"),
        )
    )
    account_b = TradingAccount(
        id=11,
        contest_participant_id=11,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    account_b.balances.append(
        AccountBalance(
            id=11,
            asset="USDT_TEST",
            available=Decimal("8000"),
            locked=Decimal("0"),
        )
    )
    account_b.positions.append(
        Position(
            id=11,
            asset=btc,
            quantity=Decimal("0.1"),
            average_entry_price=Decimal("25000"),
            cost_basis=Decimal("2500"),
            realized_pnl=Decimal("0"),
        )
    )
    account_b.orders.append(
        TradingOrder(
            id=11,
            client_order_id="web-001",
            asset=btc,
            side="buy",
            order_type="market",
            status="filled",
            requested_quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            average_fill_price=Decimal("25000"),
            estimated_notional=Decimal("2500"),
            executed_notional=Decimal("2500"),
            fee_amount=Decimal("2.5"),
            fee_asset="USDT_TEST",
            market_price_at_submission=Decimal("25000"),
            submitted_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
    )
    db_session.add_all([user_a, user_b, btc, contest, participant_a, participant_b, account_a, account_b])
    db_session.commit()
    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=lambda symbols: {"BTCUSDT": 30000.0},
    )

    rows = service.get_leaderboard("practice-arena")

    assert rows[0]["rank"] == 1
    assert rows[0]["user"] == "Student B"
    assert rows[0]["equity"] == 11000.0
    assert rows[0]["roi"] == 10.0
    assert rows[0]["volume"] == 2500.0
    assert rows[0]["trade_count"] == 1
    assert rows[0]["last_trade"] == "BTCUSDT buy"
    assert rows[1]["rank"] == 2
    assert rows[1]["equity"] == 10000.0


def _seed_participant_metrics(db_session):
    user_a = User(
        id=101,
        email="student-a@example.com",
        password_hash="hash",
        fullname="Student A",
        role="user",
    )
    user_b = User(
        id=102,
        email="student-b@example.com",
        password_hash="hash",
        fullname="Student B",
        role="user",
    )
    btc = CryptoAsset(
        id=101,
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
    contest = Contest(
        id=101,
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
    contest.assets.append(ContestAsset(id=101, asset=btc, is_enabled=True))
    participant_a = ContestParticipant(
        id=101,
        contest_id=101,
        user_id=101,
        status="active",
    )
    participant_b = ContestParticipant(
        id=102,
        contest_id=101,
        user_id=102,
        status="active",
    )
    account_a = TradingAccount(
        id=101,
        contest_participant_id=101,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    account_a.balances.append(
        AccountBalance(
            id=101,
            asset="USDT_TEST",
            available=Decimal("10000"),
            locked=Decimal("0"),
        )
    )
    account_b = TradingAccount(
        id=102,
        contest_participant_id=102,
        status="active",
        initial_equity=Decimal("10000"),
        current_equity=Decimal("10000"),
        realized_pnl=Decimal("0"),
        unrealized_pnl=Decimal("0"),
    )
    account_b.balances.append(
        AccountBalance(
            id=102,
            asset="USDT_TEST",
            available=Decimal("8000"),
            locked=Decimal("0"),
        )
    )
    account_b.positions.append(
        Position(
            id=102,
            asset=btc,
            quantity=Decimal("0.1"),
            average_entry_price=Decimal("25000"),
            cost_basis=Decimal("2500"),
            realized_pnl=Decimal("0"),
        )
    )
    account_b.orders.append(
        TradingOrder(
            id=102,
            client_order_id="web-102",
            asset=btc,
            side="buy",
            order_type="market",
            status="filled",
            requested_quantity=Decimal("0.1"),
            filled_quantity=Decimal("0.1"),
            average_fill_price=Decimal("25000"),
            estimated_notional=Decimal("2500"),
            executed_notional=Decimal("2500"),
            fee_amount=Decimal("2.5"),
            fee_asset="USDT_TEST",
            market_price_at_submission=Decimal("25000"),
            submitted_at=datetime(2026, 6, 2, tzinfo=timezone.utc),
        )
    )
    db_session.add_all(
        [user_a, user_b, btc, contest, participant_a, participant_b, account_a, account_b]
    )
    db_session.commit()


def test_admin_participant_rows_include_live_metrics(db_session):
    _seed_participant_metrics(db_session)
    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=lambda symbols: {"BTCUSDT": 30000.0},
    )

    rows = service.list_participants("practice-arena")

    assert rows[0]["user_id"] == 102
    assert rows[0]["user"] == "Student B"
    assert rows[0]["status"] == "active"
    assert rows[0]["account_status"] == "active"
    assert rows[0]["equity"] == 11000.0
    assert rows[0]["trade_count"] == 1


def test_admin_can_lock_and_restore_participant_without_changing_equity(db_session):
    _seed_participant_metrics(db_session)
    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=lambda symbols: {"BTCUSDT": 30000.0},
    )

    locked = service.set_participant_status("practice-arena", user_id=102, status="locked")
    restored = service.set_participant_status("practice-arena", user_id=102, status="active")

    assert locked["status"] == "locked"
    assert locked["account_status"] == "frozen"
    assert locked["equity"] == 11000.0
    assert restored["status"] == "active"
    assert restored["account_status"] == "active"


def test_leaderboard_caches_and_force_refreshes(db_session):
    from src.services.crypto_contests import clear_leaderboard_cache
    clear_leaderboard_cache()

    _seed_participant_metrics(db_session)
    call_count = 0

    def mock_price_provider(symbols):
        nonlocal call_count
        call_count += 1
        return {"BTCUSDT": 30000.0 if call_count == 1 else 50000.0}

    service = CryptoContestService(
        CryptoTradingRepository(db_session),
        price_provider=mock_price_provider,
    )

    first_rows = service.get_leaderboard("practice-arena")
    assert first_rows[0]["equity"] == 11000.0
    assert call_count == 1

    # Second call without force_refresh should hit cache and not call price_provider again
    second_rows = service.get_leaderboard("practice-arena")
    assert second_rows[0]["equity"] == 11000.0
    assert call_count == 1

    # Third call with force_refresh=True should bypass cache and fetch updated prices
    third_rows = service.get_leaderboard("practice-arena", force_refresh=True)
    assert third_rows[0]["equity"] == 13000.0  # 8000 + 0.1 * 50000 = 13000
    assert call_count == 2
