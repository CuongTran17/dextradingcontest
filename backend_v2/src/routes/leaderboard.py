"""
LeaderboardRouter

Expose REST snapshot và WebSocket realtime feed cho leaderboard.

Endpoints:
  GET /api/leaderboard/{contest_id}?sort_by=equity
  WS  /api/leaderboard/ws/{contest_id}?sort_by=equity&admin_token=xxx

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.4, 6.1, 6.5
"""

from __future__ import annotations

import logging
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from starlette.websockets import WebSocket

from src.database.db import get_db
from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.leaderboard import LeaderboardSnapshotResponse, snapshot_to_response
from src.services.binance_market_data import get_latest_prices
from src.services.leaderboard_calculator import LeaderboardCalculator
from src.settings import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/leaderboard", tags=["leaderboard"])

_settings = get_settings()
JWT_SECRET = _settings.jwt_secret
JWT_ALGORITHM = _settings.jwt_algorithm


# ---------------------------------------------------------------------------
# Helper: validate admin token → bool (never raises)
# ---------------------------------------------------------------------------


def _resolve_is_admin(admin_token: str | None) -> bool:
    """
    Decode admin_token JWT và kiểm tra role == "admin".

    - Token None / invalid / expired / role != admin → False
    - Không raise exception (WS endpoint gửi error message thay vì reject)
    """
    if not admin_token:
        return False
    try:
        payload = jwt.decode(admin_token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload.get("role") == "admin"
    except jwt.PyJWTError:
        return False


# ---------------------------------------------------------------------------
# REST endpoint  GET /api/leaderboard/{contest_id}
# ---------------------------------------------------------------------------


@router.get(
    "/{contest_id}",
    response_model=LeaderboardSnapshotResponse,
    summary="Leaderboard snapshot (public REST)",
)
def get_leaderboard_snapshot(
    contest_id: str,
    request: Request,
    db: Session = Depends(get_db),
    sort_by: Literal["equity", "pnl", "roi"] = Query(default="equity"),
) -> LeaderboardSnapshotResponse:
    """
    Trả về snapshot leaderboard tại thời điểm hiện tại.

    - Dùng giá từ RealtimeMarketCache nếu available (req 4.2).
    - Fallback sang Binance REST nếu cache rỗng.
    - HTTP 503 nếu cả hai đều fail (req 6.1).
    - HTTP 404 nếu contest không tồn tại (req 4.3).
    - Không yêu cầu auth (req 4.4).
    - Response chứa field updated_at (req 4.5).
    """
    repo = CryptoTradingRepository(db)

    # 1. Validate contest exists
    contest = repo.get_contest_by_slug(contest_id)
    if contest is None:
        raise HTTPException(
            status_code=404,
            detail=f"Contest '{contest_id}' not found",
        )

    # 2. Lấy giá realtime từ cache
    prices: dict[str, float] = {}
    try:
        realtime_service = getattr(request.app.state, "crypto_realtime", None)
        if realtime_service is not None:
            prices = realtime_service.cache.get_prices()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to get prices from RealtimeMarketCache: %s", exc)

    # 3. Fallback sang Binance REST nếu cache rỗng (req 4.2, 6.1)
    if not prices:
        try:
            # Lấy symbols từ contest assets
            contest_symbols = [ca.asset.symbol for ca in contest.assets if ca.asset]
            if not contest_symbols:
                # Dùng symbols mặc định nếu contest chưa có assets
                from src.services.binance_realtime import DEFAULT_SYMBOLS
                contest_symbols = DEFAULT_SYMBOLS
            prices = get_latest_prices(contest_symbols)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Binance REST fallback failed: %s", exc)
            raise HTTPException(
                status_code=503,
                detail="Price data temporarily unavailable. Please try again later.",
            ) from exc

    # 4. Query participants và tính snapshot
    participants = repo.list_contest_participants(contest_id)
    calculator = LeaderboardCalculator()
    snapshot = calculator.compute_snapshot(contest, participants, prices, sort_by=sort_by)

    return snapshot_to_response(snapshot, is_admin=False)


# ---------------------------------------------------------------------------
# WebSocket endpoint  WS /api/leaderboard/ws/{contest_id}
# ---------------------------------------------------------------------------


@router.websocket("/ws/{contest_id}")
async def leaderboard_websocket(
    websocket: WebSocket,
    contest_id: str,
    admin_token: str | None = Query(default=None),
    sort_by: str = Query(default="equity"),
) -> None:
    """
    WebSocket realtime leaderboard feed.

    - Validate admin_token JWT (req 5.1, 5.4).
    - Delegate toàn bộ lifecycle tới LeaderboardBroadcastService.handle_client().
    - Contest không tồn tại → gửi error + close (req 6.5).
    - Token invalid / role != admin → is_admin=False, không reject kết nối
      (WS endpoint gửi error message khi contest not found thay vì khi auth fail).

    NOTE: Theo req 5.4, nếu admin_token được cung cấp nhưng invalid/unauthorized,
    server gửi {"type":"error","message":"Unauthorized"} rồi đóng connection.
    """
    # Resolve admin flag (không raise exception)
    is_admin = _resolve_is_admin(admin_token)

    # Kiểm tra: nếu admin_token được cung cấp nhưng không hợp lệ → reject (req 5.4)
    if admin_token is not None and not is_admin:
        await websocket.accept()
        await websocket.send_json({"type": "error", "message": "Unauthorized"})
        await websocket.close()
        return

    # Lấy LeaderboardBroadcastService từ app state
    service = getattr(websocket.app.state, "leaderboard_broadcast", None)

    if service is None:
        # Service chưa khởi động — accept và báo lỗi
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "Leaderboard service is not available",
        })
        await websocket.close()
        return

    # Delegate toàn bộ lifecycle tới service
    await service.handle_client(websocket, contest_id, is_admin=is_admin)
