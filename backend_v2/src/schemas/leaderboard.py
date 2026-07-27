"""
Pydantic schemas cho Leaderboard API.

- LeaderboardRowPublic: thông tin công khai cho user thường
- LeaderboardRowAdmin: thêm user_id, participant_status cho admin
- LeaderboardSnapshotResponse: response wrapper cho REST + WS
- snapshot_to_response: helper chuyển đổi LeaderboardSnapshot → response
"""

from __future__ import annotations

from pydantic import BaseModel

from src.services.leaderboard_calculator import LeaderboardSnapshot


# ---------------------------------------------------------------------------
# Row schemas
# ---------------------------------------------------------------------------


class LeaderboardRowPublic(BaseModel):
    """Một hàng leaderboard dành cho user thường (không có user_id)."""

    rank: int
    user: str
    equity: float
    pnl: float
    roi: float          # percentage, e.g. 12.5 = +12.5%
    volume: float
    trade_count: int
    last_trade: str | None


class LeaderboardRowAdmin(LeaderboardRowPublic):
    """Một hàng leaderboard dành cho admin — thêm user_id và participant_status."""

    user_id: int
    participant_status: str   # active | locked | disqualified


# ---------------------------------------------------------------------------
# Snapshot response schema
# ---------------------------------------------------------------------------


class LeaderboardSnapshotResponse(BaseModel):
    """Response wrapper cho một leaderboard snapshot (REST và WebSocket)."""

    contest_id: str
    sort_by: str
    updated_at: str           # ISO8601 UTC, e.g. "2024-01-01T12:00:00Z"
    rows: list[LeaderboardRowAdmin | LeaderboardRowPublic]  # LeaderboardRowAdmin nếu là admin request


# ---------------------------------------------------------------------------
# Helper: LeaderboardSnapshot → LeaderboardSnapshotResponse
# ---------------------------------------------------------------------------


def snapshot_to_response(
    snapshot: LeaderboardSnapshot,
    is_admin: bool = False,
) -> LeaderboardSnapshotResponse:
    """
    Chuyển đổi LeaderboardSnapshot (internal dataclass) sang LeaderboardSnapshotResponse
    (Pydantic schema để serialize về JSON).

    Parameters
    ----------
    snapshot:
        Snapshot tính từ LeaderboardCalculator.
    is_admin:
        True → serialize mỗi row thành LeaderboardRowAdmin (có user_id, participant_status).
        False → serialize mỗi row thành LeaderboardRowPublic (ẩn user_id).

    Returns
    -------
    LeaderboardSnapshotResponse sẵn sàng để return từ FastAPI endpoint.
    """
    if is_admin:
        rows: list[LeaderboardRowPublic] = [
            LeaderboardRowAdmin(
                rank=row.rank,
                user=row.user,
                equity=row.equity,
                pnl=row.pnl,
                roi=row.roi,
                volume=row.volume,
                trade_count=row.trade_count,
                last_trade=row.last_trade,
                user_id=row.user_id,
                participant_status=row.participant_status,
            )
            for row in snapshot.rows
        ]
    else:
        rows = [
            LeaderboardRowPublic(
                rank=row.rank,
                user=row.user,
                equity=row.equity,
                pnl=row.pnl,
                roi=row.roi,
                volume=row.volume,
                trade_count=row.trade_count,
                last_trade=row.last_trade,
            )
            for row in snapshot.rows
        ]

    return LeaderboardSnapshotResponse(
        contest_id=snapshot.contest_id,
        sort_by=snapshot.sort_by,
        updated_at=snapshot.updated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        rows=rows,
    )
