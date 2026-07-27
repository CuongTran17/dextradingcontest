"""
LeaderboardBroadcastService

Quản lý WebSocket clients, nhận price update từ BinanceRealtimeService,
tính toán và broadcast leaderboard tới tất cả clients đang kết nối.

Responsibilities:
- Client registry theo contest_id
- Throttle broadcast: tối đa 1 lần/giây/contest
- Participant cache TTL 5s để tránh query DB liên tục
- handle_client: accept WS, send snapshot, listen messages, cleanup on disconnect
- Xử lý message set_sort từ client
- Ẩn user_id khi is_admin=False
- Graceful error handling: DB lỗi, WS disconnect, contest not found
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Callable, Literal

from sqlalchemy.orm import Session
from starlette.websockets import WebSocket, WebSocketDisconnect

from src.repositories.crypto_trading import CryptoTradingRepository
from src.schemas.leaderboard import snapshot_to_response
from src.services.leaderboard_calculator import LeaderboardCalculator

logger = logging.getLogger(__name__)

VALID_SORT_BY = {"equity", "pnl", "roi"}


class LeaderboardBroadcastService:
    """
    Broadcast leaderboard realtime qua WebSocket.

    Parameters
    ----------
    realtime_service:
        BinanceRealtimeService instance — dùng để đăng ký price callback
        và đọc giá từ cache.
    db_session_factory:
        Callable trả về một SQLAlchemy Session mới (e.g. SessionLocal).
    calculator:
        LeaderboardCalculator instance (optional — tạo mới nếu None).
    throttle_seconds:
        Khoảng thời gian tối thiểu giữa 2 lần broadcast cho cùng contest.
    participant_cache_ttl:
        TTL (giây) cho participant cache — sau đó refresh từ DB.
    """

    def __init__(
        self,
        realtime_service: object,
        db_session_factory: Callable[[], Session],
        calculator: LeaderboardCalculator | None = None,
        throttle_seconds: float = 1.0,
        participant_cache_ttl: float = 5.0,
    ) -> None:
        self._realtime_service = realtime_service
        self._db_session_factory = db_session_factory
        self._calculator = calculator or LeaderboardCalculator()
        self._throttle_seconds = throttle_seconds
        self._participant_cache_ttl = participant_cache_ttl

        # contest_id → set of connected WebSocket clients
        self._clients: dict[str, set[WebSocket]] = {}

        # contest_id → (participants_list, cached_at timestamp)
        self._participant_cache: dict[str, tuple[list, float]] = {}

        # contest_id → last broadcast timestamp
        self._last_broadcast_at: dict[str, float] = {}

        self._running = False
        self._tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Đăng ký price callback với BinanceRealtimeService."""
        if self._running:
            return
        self._running = True
        # Đăng ký callback nhận price update
        if hasattr(self._realtime_service, "register_price_listener"):
            self._realtime_service.register_price_listener(self.on_price_update)
        logger.info("LeaderboardBroadcastService started")

    async def stop(self) -> None:
        """Dừng service, đóng tất cả WebSocket connections."""
        self._running = False

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks = []

        # Đóng tất cả clients
        all_clients: list[WebSocket] = []
        for clients in self._clients.values():
            all_clients.extend(clients)

        close_results = await asyncio.gather(
            *[self._safe_close(ws) for ws in all_clients],
            return_exceptions=True,
        )
        for result in close_results:
            if isinstance(result, Exception):
                logger.debug("Error closing WS during stop: %s", result)

        self._clients.clear()
        logger.info("LeaderboardBroadcastService stopped")

    # ------------------------------------------------------------------
    # Client handling
    # ------------------------------------------------------------------

    async def handle_client(
        self,
        websocket: WebSocket,
        contest_id: str,
        is_admin: bool = False,
    ) -> None:
        """
        Toàn bộ lifecycle của một WebSocket client:
        1. Query contest — nếu không tìm thấy: accept, send error, close
        2. Accept WS, thêm vào registry
        3. Gửi snapshot ngay lập tức
        4. Loop nhận messages từ client
        5. Cleanup khi disconnect
        """
        # Kiểm tra contest tồn tại trước khi accept
        contest = self._get_contest(contest_id)
        if contest is None:
            # req 6.5: accept, gửi error, đóng connection
            await websocket.accept()
            await websocket.send_json({"type": "error", "message": "Contest not found"})
            await websocket.close()
            return

        # Accept và đăng ký client
        await websocket.accept()
        if contest_id not in self._clients:
            self._clients[contest_id] = set()
        self._clients[contest_id].add(websocket)

        try:
            # Gửi snapshot ngay lập tức (req 3.1)
            await self._send_snapshot(websocket, contest, contest_id, is_admin, msg_type="leaderboard_snapshot")

            # Lắng nghe messages từ client
            while True:
                try:
                    message = await websocket.receive_json()
                except WebSocketDisconnect:
                    break
                except Exception:
                    # Client có thể gửi non-JSON hoặc bị ngắt đột ngột
                    break

                await self._handle_client_message(websocket, message, contest, contest_id, is_admin)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            logger.exception("Unexpected error in handle_client for contest=%s: %s", contest_id, exc)
        finally:
            # req 3.5: cleanup khi disconnect
            if contest_id in self._clients:
                self._clients[contest_id].discard(websocket)

    # ------------------------------------------------------------------
    # Price update callback (được gọi bởi BinanceRealtimeService)
    # ------------------------------------------------------------------

    async def on_price_update(self, prices: dict[str, float]) -> None:
        """
        Callback được BinanceRealtimeService gọi mỗi khi có ticker price update.

        - req 6.2: Nếu prices rỗng → skip broadcast cycle
        - req 3.3: Throttle: không broadcast quá 1 lần/giây/contest
        - req 3.4: Refresh participant cache khi TTL hết
        - req 3.5: Xóa disconnected clients
        """
        if not prices:
            return  # req 6.2: skip khi không có giá

        now = time.monotonic()

        # Loop qua tất cả contest có clients
        for contest_id, clients in list(self._clients.items()):
            if not clients:
                continue

            # Throttle check (req 3.3)
            last_broadcast = self._last_broadcast_at.get(contest_id, 0.0)
            if now - last_broadcast < self._throttle_seconds:
                continue

            # Lấy contest object
            contest = self._get_contest(contest_id)
            if contest is None:
                continue

            # Refresh participant cache nếu TTL hết (req 3.4)
            participants = self._get_cached_participants(contest_id, now)
            if participants is None:
                continue  # DB error đã được log bên trong, skip cycle này

            # Compute snapshot
            try:
                snapshot = self._calculator.compute_snapshot(
                    contest, participants, prices, sort_by="equity"
                )
            except Exception as exc:
                logger.exception("Error computing snapshot for contest=%s: %s", contest_id, exc)
                continue

            # Broadcast tới tất cả clients (req 3.2)
            await self._broadcast_to_contest(contest_id, snapshot, clients, is_admin=False)
            self._last_broadcast_at[contest_id] = now

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_contest(self, contest_id: str):
        """Query contest by slug. Returns None nếu không tìm thấy."""
        try:
            db = self._db_session_factory()
            try:
                repo = CryptoTradingRepository(db)
                return repo.get_contest_by_slug(contest_id)
            finally:
                db.close()
        except Exception as exc:
            logger.exception("DB error querying contest=%s: %s", contest_id, exc)
            return None

    def _get_cached_participants(self, contest_id: str, now: float) -> list | None:
        """
        Trả về danh sách participants từ cache hoặc DB.

        Returns None nếu gặp DB error (req 6.3: giữ stale cache nếu có).
        """
        cached = self._participant_cache.get(contest_id)
        if cached is not None:
            participants, cached_at = cached
            if now - cached_at <= self._participant_cache_ttl:
                return participants  # cache còn hiệu lực

        # Cache hết TTL hoặc chưa có — refresh từ DB
        try:
            db = self._db_session_factory()
            try:
                repo = CryptoTradingRepository(db)
                participants = repo.list_contest_participants(contest_id)
                self._participant_cache[contest_id] = (participants, now)
                return participants
            finally:
                db.close()
        except Exception as exc:
            # req 6.3: log error, giữ stale cache
            logger.exception("DB error refreshing participants for contest=%s: %s", contest_id, exc)
            if cached is not None:
                return cached[0]  # trả về stale cache
            return None  # không có cache nào — skip cycle này

    async def _send_snapshot(
        self,
        websocket: WebSocket,
        contest,
        contest_id: str,
        is_admin: bool,
        msg_type: str = "leaderboard_snapshot",
        sort_by: Literal["equity", "pnl", "roi"] = "equity",
    ) -> None:
        """Compute và gửi snapshot tới một WebSocket client cụ thể."""
        now = time.monotonic()
        participants = self._get_cached_participants(contest_id, now)
        if participants is None:
            participants = []

        prices = self._get_prices()

        try:
            snapshot = self._calculator.compute_snapshot(
                contest, participants, prices, sort_by=sort_by
            )
        except Exception as exc:
            logger.exception("Error computing snapshot for contest=%s: %s", contest_id, exc)
            return

        response = snapshot_to_response(snapshot, is_admin=is_admin)
        message = {"type": msg_type, **response.model_dump()}
        try:
            await websocket.send_json(message)
        except WebSocketDisconnect:
            if contest_id in self._clients:
                self._clients[contest_id].discard(websocket)
        except Exception as exc:
            logger.debug("Error sending snapshot to client: %s", exc)
            if contest_id in self._clients:
                self._clients[contest_id].discard(websocket)

    async def _handle_client_message(
        self,
        websocket: WebSocket,
        message: dict,
        contest,
        contest_id: str,
        is_admin: bool,
    ) -> None:
        """Xử lý message từ client."""
        msg_type = message.get("type")

        if msg_type == "set_sort":
            sort_by = message.get("sort_by", "")
            if sort_by not in VALID_SORT_BY:
                # req 6.4: gửi error, KHÔNG đóng connection
                await self._safe_send(websocket, {
                    "type": "error",
                    "message": "Invalid sort_by. Must be equity|pnl|roi",
                })
                return

            # Re-sort và gửi lại snapshot (req 2.4)
            await self._send_snapshot(
                websocket, contest, contest_id, is_admin,
                msg_type="leaderboard_snapshot",
                sort_by=sort_by,  # type: ignore[arg-type]
            )
        else:
            # Unknown message type — ignore silently
            pass

    async def _broadcast_to_contest(
        self,
        contest_id: str,
        snapshot,
        clients: set[WebSocket],
        is_admin: bool = False,
    ) -> None:
        """Broadcast snapshot tới tất cả clients của một contest."""
        response = snapshot_to_response(snapshot, is_admin=is_admin)
        message = {"type": "leaderboard_update", **response.model_dump()}

        disconnected: list[WebSocket] = []
        results = await asyncio.gather(
            *[self._safe_send(ws, message) for ws in list(clients)],
            return_exceptions=True,
        )
        for ws, result in zip(list(clients), results):
            if isinstance(result, Exception):
                disconnected.append(ws)

        # req 3.5: Xóa disconnected clients
        for ws in disconnected:
            if contest_id in self._clients:
                self._clients[contest_id].discard(ws)

    def _get_prices(self) -> dict[str, float]:
        """Lấy giá từ RealtimeMarketCache."""
        try:
            if hasattr(self._realtime_service, "cache"):
                return self._realtime_service.cache.get_prices()
        except Exception as exc:
            logger.debug("Error getting prices from realtime cache: %s", exc)
        return {}

    async def _safe_send(self, websocket: WebSocket, message: dict) -> None:
        """Gửi JSON message, raise Exception nếu disconnect để caller xử lý."""
        await websocket.send_json(message)

    async def _safe_close(self, websocket: WebSocket) -> None:
        """Đóng WebSocket, bỏ qua lỗi."""
        try:
            await websocket.close()
        except Exception:
            pass
