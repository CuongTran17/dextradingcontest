"""
Unit tests và property-based tests cho LeaderboardCalculator.

Validates: Requirements 1.1, 1.2, 1.3, 1.5, 1.6, 2.2, 2.3
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

from src.services.leaderboard_calculator import LeaderboardCalculator, LeaderboardRow


# ---------------------------------------------------------------------------
# Helpers để xây dựng mock objects
# ---------------------------------------------------------------------------

def make_contest(
    slug: str = "test-contest",
    quote_asset: str = "USDT_TEST",
    initial_balance: float = 10_000.0,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        slug=slug,
        quote_asset=quote_asset,
        initial_balance=Decimal(str(initial_balance)),
    )


def make_balance(asset: str, available: float) -> SimpleNamespace:
    return SimpleNamespace(asset=asset, available=Decimal(str(available)))


def make_position(symbol: str, quantity: float) -> SimpleNamespace:
    return SimpleNamespace(
        quantity=Decimal(str(quantity)),
        asset=SimpleNamespace(symbol=symbol),
    )


def make_order(
    symbol: str,
    side: str = "buy",
    status: str = "filled",
    executed_notional: float = 0.0,
    submitted_at: object = None,
) -> SimpleNamespace:
    if submitted_at is None:
        from datetime import datetime, timezone
        submitted_at = datetime.now(timezone.utc)
    return SimpleNamespace(
        status=status,
        executed_notional=Decimal(str(executed_notional)),
        asset=SimpleNamespace(symbol=symbol),
        side=side,
        submitted_at=submitted_at,
    )


def make_account(
    initial_equity: float = 10_000.0,
    balances: list | None = None,
    positions: list | None = None,
    orders: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        initial_equity=Decimal(str(initial_equity)),
        balances=balances or [],
        positions=positions or [],
        orders=orders or [],
    )


def make_participant(
    user_id: int = 1,
    status: str = "active",
    account: SimpleNamespace | None = None,
    fullname: str = "Test User",
) -> SimpleNamespace:
    user = SimpleNamespace(
        id=user_id,
        fullname=fullname,
        first_name=None,
        last_name=None,
        email=f"user{user_id}@test.com",
    )
    return SimpleNamespace(
        id=user_id,
        user_id=user_id,
        status=status,
        account=account,
        user=user,
    )


# ---------------------------------------------------------------------------
# Unit Tests — Deterministic
# ---------------------------------------------------------------------------

class TestEquityCalculation:
    """Validates: Requirements 1.1"""

    def test_equity_cash_only_no_positions(self):
        """equity = cash khi không có positions."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 8_000.0)],
            positions=[],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert len(snapshot.rows) == 1
        assert snapshot.rows[0].equity == round(8_000.0, 2)

    def test_equity_positions_only_no_cash(self):
        """equity = position_value khi cash = 0."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[],          # không có cash
            positions=[make_position("BTCUSDT", 0.5)],
        )
        participant = make_participant(account=account)
        prices = {"BTCUSDT": 60_000.0}
        snapshot = calc.compute_snapshot(contest, [participant], prices=prices)
        assert snapshot.rows[0].equity == round(0.5 * 60_000.0, 2)

    def test_equity_cash_plus_positions(self):
        """equity = cash + sum(qty * price)."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 5_000.0)],
            positions=[
                make_position("BTCUSDT", 0.1),
                make_position("ETHUSDT", 2.0),
            ],
        )
        participant = make_participant(account=account)
        prices = {"BTCUSDT": 60_000.0, "ETHUSDT": 3_000.0}
        expected = 5_000.0 + 0.1 * 60_000.0 + 2.0 * 3_000.0
        snapshot = calc.compute_snapshot(contest, [participant], prices=prices)
        assert snapshot.rows[0].equity == round(expected, 2)

    def test_equity_multiple_balances_same_asset(self):
        """Chỉ tính balance có asset == quote_asset."""
        calc = LeaderboardCalculator()
        contest = make_contest(quote_asset="USDT_TEST")
        account = make_account(
            initial_equity=10_000.0,
            balances=[
                make_balance("USDT_TEST", 3_000.0),
                make_balance("BNB", 100.0),  # asset khác, không tính
            ],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].equity == round(3_000.0, 2)


class TestPnlCalculation:
    """Validates: Requirement 1.2"""

    def test_pnl_positive(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 11_500.0)],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].pnl == round(11_500.0 - 10_000.0, 2)

    def test_pnl_negative(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 8_000.0)],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].pnl == round(8_000.0 - 10_000.0, 2)

    def test_pnl_zero_when_no_change(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 10_000.0)],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].pnl == 0.0


class TestRoiCalculation:
    """Validates: Requirement 1.3"""

    def test_roi_normal_case(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 11_000.0)],
        )
        participant = make_participant(account=account)
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        expected_roi = round(1_000.0 / 10_000.0 * 100.0, 4)
        assert snapshot.rows[0].roi == expected_roi

    def test_roi_zero_when_initial_equity_is_zero(self):
        """Không crash khi initial_equity = 0 — ROI = 0. Validates: Req 1.3"""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=0.0,
            balances=[make_balance("USDT_TEST", 500.0)],
        )
        participant = make_participant(account=account)
        # không được raise exception
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].roi == 0.0

    def test_compute_single_row_roi_zero_division_safe(self):
        """compute_single_row cũng không crash khi initial_equity = 0."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=0.0,
            balances=[make_balance("USDT_TEST", 200.0)],
        )
        participant = make_participant(account=account)
        row = calc.compute_single_row(contest, participant, prices={})
        assert row.roi == 0.0


class TestMissingPriceFallback:
    """Validates: Requirement 1.5"""

    def test_missing_symbol_in_prices_gives_zero_position_value(self):
        """Symbol thiếu giá → position_value = 0, không raise KeyError."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 5_000.0)],
            positions=[make_position("XYZUSDT", 100.0)],  # không có trong prices
        )
        participant = make_participant(account=account)
        prices = {}  # không có XYZUSDT
        snapshot = calc.compute_snapshot(contest, [participant], prices=prices)
        # equity = cash + 0 (position value của symbol thiếu giá = 0)
        assert snapshot.rows[0].equity == round(5_000.0, 2)

    def test_partial_prices_only_known_symbols_counted(self):
        """Chỉ symbol có giá mới được tính vào equity."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        account = make_account(
            initial_equity=10_000.0,
            balances=[make_balance("USDT_TEST", 1_000.0)],
            positions=[
                make_position("BTCUSDT", 1.0),
                make_position("UNKNOWN", 999.0),  # không có giá
            ],
        )
        participant = make_participant(account=account)
        prices = {"BTCUSDT": 50_000.0}
        snapshot = calc.compute_snapshot(contest, [participant], prices=prices)
        expected = 1_000.0 + 1.0 * 50_000.0 + 999.0 * 0.0
        assert snapshot.rows[0].equity == round(expected, 2)


class TestParticipantWithoutAccount:
    """Validates: Requirement 1.6"""

    def test_participant_without_account_is_filtered_out(self):
        """Participant không có account không xuất hiện trong leaderboard."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        p_with_account = make_participant(
            user_id=1,
            account=make_account(balances=[make_balance("USDT_TEST", 10_000.0)]),
        )
        p_without_account = make_participant(user_id=2, account=None)
        snapshot = calc.compute_snapshot(
            contest, [p_with_account, p_without_account], prices={}
        )
        assert len(snapshot.rows) == 1
        assert snapshot.rows[0].user_id == 1

    def test_all_participants_without_account(self):
        """Nếu không có ai có account, leaderboard trống."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        participants = [
            make_participant(user_id=i, account=None) for i in range(5)
        ]
        snapshot = calc.compute_snapshot(contest, participants, prices={})
        assert snapshot.rows == []

    def test_compute_single_row_raises_for_missing_account(self):
        """compute_single_row phải raise ValueError khi không có account."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        participant = make_participant(account=None)
        with pytest.raises(ValueError, match="does not have a TradingAccount"):
            calc.compute_single_row(contest, participant, prices={})


class TestSortOrder:
    """Validates: Requirements 2.1, 2.2"""

    def _make_snapshot(self, sort_by: str):
        calc = LeaderboardCalculator()
        contest = make_contest()
        participants = [
            make_participant(
                user_id=1,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 12_000.0)],
                ),
            ),
            make_participant(
                user_id=2,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 8_000.0)],
                ),
            ),
            make_participant(
                user_id=3,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 10_500.0)],
                ),
            ),
        ]
        return calc.compute_snapshot(contest, participants, prices={}, sort_by=sort_by)

    def test_sort_by_equity_descending(self):
        snapshot = self._make_snapshot("equity")
        values = [row.equity for row in snapshot.rows]
        assert values == sorted(values, reverse=True)
        assert snapshot.rows[0].equity == round(12_000.0, 2)

    def test_sort_by_pnl_descending(self):
        snapshot = self._make_snapshot("pnl")
        values = [row.pnl for row in snapshot.rows]
        assert values == sorted(values, reverse=True)

    def test_sort_by_roi_descending(self):
        snapshot = self._make_snapshot("roi")
        values = [row.roi for row in snapshot.rows]
        assert values == sorted(values, reverse=True)


class TestRankAssignment:
    """Validates: Requirement 2.3"""

    def test_rank_is_contiguous_from_one(self):
        """Rank là dãy 1..N không có gap, không duplicate."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        participants = [
            make_participant(
                user_id=i,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", float(9_000 + i * 500))],
                ),
            )
            for i in range(1, 6)
        ]
        snapshot = calc.compute_snapshot(contest, participants, prices={})
        ranks = [row.rank for row in snapshot.rows]
        assert sorted(ranks) == list(range(1, len(participants) + 1))

    def test_rank_no_duplicates(self):
        """Không có 2 participants nào cùng rank."""
        calc = LeaderboardCalculator()
        contest = make_contest()
        participants = [
            make_participant(
                user_id=i,
                account=make_account(
                    balances=[make_balance("USDT_TEST", float(1_000 * i))],
                ),
            )
            for i in range(1, 4)
        ]
        snapshot = calc.compute_snapshot(contest, participants, prices={})
        ranks = [row.rank for row in snapshot.rows]
        assert len(ranks) == len(set(ranks))

    def test_single_participant_has_rank_one(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        participant = make_participant(
            account=make_account(balances=[make_balance("USDT_TEST", 10_000.0)])
        )
        snapshot = calc.compute_snapshot(contest, [participant], prices={})
        assert snapshot.rows[0].rank == 1


class TestSnapshotMetadata:
    """Test các thuộc tính metadata của snapshot."""

    def test_snapshot_has_correct_contest_id(self):
        calc = LeaderboardCalculator()
        contest = make_contest(slug="my-contest")
        snapshot = calc.compute_snapshot(contest, [], prices={})
        assert snapshot.contest_id == "my-contest"

    def test_snapshot_sort_by_preserved(self):
        calc = LeaderboardCalculator()
        contest = make_contest()
        participant = make_participant(
            account=make_account(balances=[make_balance("USDT_TEST", 10_000.0)])
        )
        for sort_by in ("equity", "pnl", "roi"):
            snapshot = calc.compute_snapshot(contest, [participant], prices={}, sort_by=sort_by)
            assert snapshot.sort_by == sort_by

    def test_snapshot_updated_at_is_utc(self):
        from datetime import timezone
        calc = LeaderboardCalculator()
        contest = make_contest()
        snapshot = calc.compute_snapshot(contest, [], prices={})
        assert snapshot.updated_at.tzinfo == timezone.utc


# ---------------------------------------------------------------------------
# Property-Based Tests
# ---------------------------------------------------------------------------

# Shared constants for PBT
SYMBOLS = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]


def _build_participant_from_pbt(
    user_id: int,
    cash: float,
    quantities: list[float],
    price_vals: list[float],
    initial_equity: float = 10_000.0,
) -> SimpleNamespace:
    """
    Tạo participant mock từ dữ liệu do hypothesis sinh ra.
    Đảm bảo quantities và prices ánh xạ sang SYMBOLS đầu tiên.
    """
    n = min(len(quantities), len(price_vals), len(SYMBOLS))
    positions = [
        make_position(SYMBOLS[i], quantities[i]) for i in range(n)
    ]
    prices_dict = {SYMBOLS[i]: price_vals[i] for i in range(n)}
    account = make_account(
        initial_equity=initial_equity,
        balances=[make_balance("USDT_TEST", cash)],
        positions=positions,
    )
    participant = make_participant(user_id=user_id, account=account)
    return participant, prices_dict


@given(
    cash=st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
    quantities=st.lists(
        st.floats(min_value=0, max_value=1000, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=5,
    ),
    prices_vals=st.lists(
        st.floats(min_value=0, max_value=1e6, allow_nan=False, allow_infinity=False),
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=200)
def test_equity_non_negative(cash, quantities, prices_vals):
    """
    **Validates: Requirements 1.1**

    PBT 1: equity luôn >= 0 với mọi combination prices/quantities hợp lệ (non-negative).
    Vì cash >= 0, quantity >= 0, price >= 0 → equity = cash + sum(qty*price) >= 0.
    """
    calc = LeaderboardCalculator()
    contest = make_contest()
    participant, prices = _build_participant_from_pbt(
        user_id=1, cash=cash, quantities=quantities, price_vals=prices_vals
    )
    snapshot = calc.compute_snapshot(contest, [participant], prices=prices)
    assert len(snapshot.rows) == 1
    assert snapshot.rows[0].equity >= 0.0, (
        f"equity={snapshot.rows[0].equity} phải >= 0 với cash={cash}, "
        f"quantities={quantities}, prices={prices_vals}"
    )


@given(n_participants=st.integers(min_value=1, max_value=20))
@settings(max_examples=100)
def test_rank_is_dense_sequence(n_participants: int):
    """
    **Validates: Requirements 2.3**

    PBT 2: rank là dãy range(1, N+1) với mọi số lượng participants.
    """
    calc = LeaderboardCalculator()
    contest = make_contest()
    participants = [
        make_participant(
            user_id=i,
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", float(10_000 + i * 100))],
            ),
        )
        for i in range(1, n_participants + 1)
    ]
    snapshot = calc.compute_snapshot(contest, participants, prices={})
    ranks = sorted(row.rank for row in snapshot.rows)
    expected = list(range(1, n_participants + 1))
    assert ranks == expected, (
        f"ranks={ranks} phải là {expected} với n_participants={n_participants}"
    )


@given(sort_by=st.sampled_from(["equity", "pnl", "roi"]))
@settings(max_examples=50)
def test_sort_order_descending(sort_by: str):
    """
    **Validates: Requirements 2.1, 2.2**

    PBT 3: rows sort giảm dần theo sort_by với mọi sort_by trong {equity, pnl, roi}.
    """
    calc = LeaderboardCalculator()
    contest = make_contest()
    # Tạo 5 participants với equity khác nhau để có thứ tự rõ ràng
    participants = [
        make_participant(
            user_id=i,
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", float(9_000 + i * 333))],
            ),
        )
        for i in range(1, 6)
    ]
    snapshot = calc.compute_snapshot(contest, participants, prices={}, sort_by=sort_by)
    values = [getattr(row, sort_by) for row in snapshot.rows]
    assert values == sorted(values, reverse=True), (
        f"sort_by={sort_by!r}: values={values} không được sort giảm dần"
    )
