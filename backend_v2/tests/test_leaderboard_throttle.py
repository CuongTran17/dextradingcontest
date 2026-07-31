"""
Property-based tests for Leaderboard throttle guarantee.

Validates: Requirement 3.3
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from hypothesis import given, settings
import hypothesis.strategies as st

from src.services.leaderboard_broadcast import LeaderboardBroadcastService


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
        assets=[],
    )


@given(
    throttle_seconds=st.floats(min_value=0.1, max_value=5.0),
    offsets=st.lists(
        st.floats(min_value=0.0, max_value=0.999), min_size=2, max_size=15
    ),
)
@settings(max_examples=100)
def test_throttle_guarantee_property(throttle_seconds: float, offsets: list[float]) -> None:
    """
    **Property 6: Throttle Guarantee**

    Ensure that emitting multiple price events consecutively within the
    `throttle_seconds` window guarantees that the broadcast count is <= 1.
    """
    # Scale offsets to be strictly less than throttle_seconds
    scaled_offsets = sorted(offset * throttle_seconds * 0.99 for offset in offsets)

    asyncio.run(run_throttle_scenario(throttle_seconds, scaled_offsets))


async def run_throttle_scenario(
    throttle_seconds: float,
    scaled_offsets: list[float],
) -> None:
    fake_realtime = Mock()

    service = LeaderboardBroadcastService(
        realtime_service=fake_realtime,
        db_session_factory=lambda: Mock(),
        throttle_seconds=throttle_seconds,
    )

    # Register a mock WebSocket client for a contest so clients set is not empty
    mock_ws = Mock()
    service._clients["test-contest"] = {mock_ws}

    # Mock internal methods to isolate throttle logic from DB and calculations
    service._get_contest = Mock(return_value=make_contest())
    service._get_cached_participants = Mock(return_value=[])
    service._calculator = Mock()
    service._calculator.compute_snapshot = Mock(return_value=Mock())

    # Use AsyncMock to count how many times the broadcast method is called
    broadcast_mock = AsyncMock()
    service._broadcast_to_contest = broadcast_mock

    # Simulate price updates occurring at the generated offset times
    start_time = 1000.0
    mock_times = [start_time + offset for offset in scaled_offsets]

    time_iter = iter(mock_times)

    def mock_monotonic() -> float:
        try:
            return next(time_iter)
        except StopIteration:
            return mock_times[-1]

    with patch("src.services.leaderboard_broadcast.time.monotonic", side_effect=mock_monotonic):
        # Call on_price_update for each simulated event
        for _ in range(len(scaled_offsets)):
            await service.on_price_update({"BTCUSDT": 50000.0})

    # Verify that the broadcast is sent at most once (specifically exactly once)
    assert broadcast_mock.call_count <= 1
