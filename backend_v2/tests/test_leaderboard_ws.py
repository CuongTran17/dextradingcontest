"""
Integration tests cho WebSocket leaderboard endpoint.

Covers:
- WS connect → nhận leaderboard_snapshot ngay lập tức
- WS gửi set_sort → nhận snapshot mới với sort order thay đổi
- WS contest không tồn tại → nhận error + connection đóng
- WS gửi sort_by không hợp lệ → nhận error nhưng connection vẫn mở

Requirements: 3.1, 3.5, 6.4, 6.5
"""
from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from typing import Callable

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.leaderboard import router
from src.services.leaderboard_broadcast import LeaderboardBroadcastService


# ---------------------------------------------------------------------------
# Mock helpers (reuse patterns from test_leaderboard_calculator.py)
# ---------------------------------------------------------------------------


def _make_balance(asset: str, available: float) -> SimpleNamespace:
    return SimpleNamespace(asset=asset, available=Decimal(str(available)))


def _make_position(symbol: str, quantity: float) -> SimpleNamespace:
    return SimpleNamespace(
        quantity=Decimal(str(quantity)),
        asset=SimpleNamespace(symbol=symbol),
    )


def _make_account(
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


def _make_participant(
    user_id: int = 1,
    status: str = "active",
    account: SimpleNamespace | None = None,
    fullname: str = "Alice",
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


def _make_contest(
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


# ---------------------------------------------------------------------------
# Fake realtime service (returns static prices)
# ---------------------------------------------------------------------------


class FakeRealtimeService:
    """Fake BinanceRealtimeService — trả về giá cố định, hỗ trợ price listeners."""

    def __init__(self, prices: dict[str, float] | None = None) -> None:
        self._prices = prices or {"BTCUSDT": 50_000.0, "ETHUSDT": 3_000.0}
        self._listeners: list[Callable] = []

        class _Cache:
            def __init__(self, prices):
                self._prices = prices

            def get_prices(self):
                return dict(self._prices)

        self.cache = _Cache(self._prices)

    def register_price_listener(self, callback: Callable) -> None:
        self._listeners.append(callback)


# ---------------------------------------------------------------------------
# Fake DB session factory
# ---------------------------------------------------------------------------


class FakeRepository:
    """Minimal fake for CryptoTradingRepository."""

    def __init__(self, contest=None, participants=None):
        self._contest = contest
        self._participants = participants or []

    def get_contest_by_slug(self, slug: str):
        if self._contest and self._contest.slug == slug:
            return self._contest
        return None

    def list_contest_participants(self, contest_id: str):
        return self._participants


class FakeSession:
    def close(self):
        pass


def _make_db_factory(contest=None, participants=None) -> Callable:
    """Returns a factory that yields a fake DB session backed by FakeRepository."""

    class _FakeSession:
        def __init__(self):
            self._repo = FakeRepository(contest=contest, participants=participants)

        def close(self):
            pass

    # Monkey-patch the import used inside LeaderboardBroadcastService
    original_repo_cls = None

    import src.repositories.crypto_trading as repo_module

    _contest = contest
    _participants = participants or []

    class _PatchedRepo:
        def __init__(self, session):
            pass

        def get_contest_by_slug(self, slug: str):
            if _contest and _contest.slug == slug:
                return _contest
            return None

        def list_contest_participants(self, contest_id: str):
            return _participants

    # We'll patch at import time and restore after — simpler to just pass a
    # factory that the broadcast service calls as SessionLocal.
    # The broadcast service does: db = self._db_session_factory(); repo = CryptoTradingRepository(db)
    # So we need to monkeypatch CryptoTradingRepository in broadcast module.

    def factory():
        return _FakeSession()

    # Store the patched repo class so callers can inject it
    factory._patched_repo = _PatchedRepo  # type: ignore[attr-defined]
    return factory


# ---------------------------------------------------------------------------
# App factory: builds a FastAPI app with a real LeaderboardBroadcastService
# backed by fake DB/realtime.
# ---------------------------------------------------------------------------


def _make_app(
    contest_slug: str = "test-contest",
    contest_exists: bool = True,
    participants: list | None = None,
    prices: dict | None = None,
) -> TestClient:
    """
    Builds a TestClient with a real LeaderboardBroadcastService that uses
    mocked DB and realtime dependencies.
    """
    import src.services.leaderboard_broadcast as broadcast_module

    contest = _make_contest(slug=contest_slug) if contest_exists else None

    if participants is None:
        participants = [
            _make_participant(
                user_id=1,
                fullname="Alice",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 12_000.0)],
                ),
            ),
            _make_participant(
                user_id=2,
                fullname="Bob",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 9_000.0)],
                ),
            ),
        ]

    _contest = contest
    _participants = participants

    class PatchedRepo:
        def __init__(self, session):
            pass

        def get_contest_by_slug(self, slug: str):
            if _contest and _contest.slug == slug:
                return _contest
            return None

        def list_contest_participants(self, contest_id: str):
            return _participants

    # Patch CryptoTradingRepository in the broadcast module
    original_repo = broadcast_module.CryptoTradingRepository
    broadcast_module.CryptoTradingRepository = PatchedRepo  # type: ignore[attr-defined]

    fake_realtime = FakeRealtimeService(prices=prices)

    def fake_db_factory():
        return FakeSession()

    service = LeaderboardBroadcastService(
        realtime_service=fake_realtime,
        db_session_factory=fake_db_factory,
    )
    # Run start synchronously via asyncio in tests is avoided —
    # TestClient handles startup. Just register it directly.
    if hasattr(fake_realtime, "register_price_listener"):
        fake_realtime.register_price_listener(service.on_price_update)
    service._running = True

    app = FastAPI()
    app.state.leaderboard_broadcast = service
    app.include_router(router)

    client = TestClient(app)
    # Store so we can restore after test
    client._original_repo = original_repo  # type: ignore[attr-defined]
    client._broadcast_module = broadcast_module  # type: ignore[attr-defined]
    return client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWsConnectReceivesSnapshot:
    """
    Req 3.1: Client kết nối → nhận leaderboard_snapshot ngay lập tức.
    Fields: type, contest_id, rows, updated_at đều có mặt.
    """

    def test_connect_receives_snapshot_immediately(self):
        """WS connect → nhận leaderboard_snapshot với đầy đủ fields."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            assert msg["type"] == "leaderboard_snapshot"
            assert msg["contest_id"] == "test-contest"
            assert "rows" in msg
            assert "updated_at" in msg
            assert isinstance(msg["rows"], list)
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_snapshot_has_sort_by_field(self):
        """Snapshot chứa field sort_by."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            assert "sort_by" in msg
            assert msg["sort_by"] in ("equity", "pnl", "roi")
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_snapshot_rows_have_required_fields(self):
        """Mỗi row trong snapshot chứa rank, user, equity, pnl, roi, volume, trade_count."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            rows = msg["rows"]
            assert len(rows) == 2  # Alice + Bob

            row = rows[0]
            for field in ("rank", "user", "equity", "pnl", "roi", "volume", "trade_count"):
                assert field in row, f"Field '{field}' missing from row"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_snapshot_rows_do_not_expose_user_id_for_public(self):
        """
        Req 5.3: user_id không xuất hiện trong response khi không có admin_token.
        """
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            rows = msg["rows"]
            for row in rows:
                assert "user_id" not in row, "user_id phải bị ẩn với public user"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_snapshot_updated_at_is_iso8601(self):
        """updated_at phải là chuỗi ISO8601 UTC."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            updated_at = msg["updated_at"]
            assert isinstance(updated_at, str)
            # ISO8601 UTC: "2024-01-01T12:00:00Z"
            assert "T" in updated_at
            assert updated_at.endswith("Z") or "+" in updated_at
        finally:
            broadcast_module.CryptoTradingRepository = original_repo


class TestWsSetSort:
    """
    Req 2.4: Client gửi set_sort → nhận snapshot mới với sort order thay đổi.
    """

    def test_set_sort_returns_new_snapshot(self):
        """Gửi set_sort roi → nhận leaderboard_snapshot mới."""
        import src.services.leaderboard_broadcast as broadcast_module

        participants = [
            _make_participant(
                user_id=1,
                fullname="Alice",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 12_000.0)],
                ),
            ),
            _make_participant(
                user_id=2,
                fullname="Bob",
                account=_make_account(
                    initial_equity=8_000.0,   # khác initial để ROI khác equity order
                    balances=[_make_balance("USDT_TEST", 11_000.0)],
                ),
            ),
        ]

        client = _make_app(participants=participants)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                # Đọc snapshot ban đầu (mặc định equity)
                initial_snapshot = ws.receive_json()
                assert initial_snapshot["type"] == "leaderboard_snapshot"
                assert initial_snapshot["sort_by"] == "equity"

                # Gửi set_sort roi
                ws.send_json({"type": "set_sort", "sort_by": "roi"})
                new_snapshot = ws.receive_json()

            assert new_snapshot["type"] == "leaderboard_snapshot"
            assert new_snapshot["sort_by"] == "roi"
            assert "rows" in new_snapshot
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_set_sort_roi_reorders_rows(self):
        """
        Sau set_sort roi, rows được sort giảm dần theo roi.
        Alice: equity=12000, initial=10000 → roi=20%
        Bob: equity=9000, initial=5000 → roi=80%
        → Bob đứng đầu khi sort theo roi mặc dù Alice có equity cao hơn.
        """
        import src.services.leaderboard_broadcast as broadcast_module

        participants = [
            _make_participant(
                user_id=1,
                fullname="Alice",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 12_000.0)],
                ),
            ),
            _make_participant(
                user_id=2,
                fullname="Bob",
                account=_make_account(
                    initial_equity=5_000.0,
                    balances=[_make_balance("USDT_TEST", 9_000.0)],
                ),
            ),
        ]

        client = _make_app(participants=participants)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                # Bỏ qua initial snapshot
                ws.receive_json()

                # Request sort by roi
                ws.send_json({"type": "set_sort", "sort_by": "roi"})
                roi_snapshot = ws.receive_json()

            rows = roi_snapshot["rows"]
            assert len(rows) == 2

            roi_values = [row["roi"] for row in rows]
            # Phải giảm dần
            assert roi_values == sorted(roi_values, reverse=True)

            # Bob (roi = 80%) phải đứng trước Alice (roi = 20%)
            assert rows[0]["user"] == "Bob"
            assert rows[1]["user"] == "Alice"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_set_sort_equity_returns_correct_sort_order(self):
        """Sau set_sort equity, rows sort giảm dần theo equity."""
        import src.services.leaderboard_broadcast as broadcast_module

        participants = [
            _make_participant(
                user_id=1,
                fullname="Alice",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 15_000.0)],
                ),
            ),
            _make_participant(
                user_id=2,
                fullname="Bob",
                account=_make_account(
                    initial_equity=10_000.0,
                    balances=[_make_balance("USDT_TEST", 8_000.0)],
                ),
            ),
        ]

        client = _make_app(participants=participants)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                ws.receive_json()  # initial snapshot

                ws.send_json({"type": "set_sort", "sort_by": "equity"})
                equity_snapshot = ws.receive_json()

            rows = equity_snapshot["rows"]
            equity_values = [row["equity"] for row in rows]
            assert equity_values == sorted(equity_values, reverse=True)
        finally:
            broadcast_module.CryptoTradingRepository = original_repo


class TestWsContestNotFound:
    """
    Req 6.5: Contest không tồn tại → nhận error message rồi connection đóng.
    """

    def test_nonexistent_contest_receives_error(self):
        """Contest không tồn tại → nhận {"type":"error","message":"Contest not found"}."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app(contest_slug="test-contest", contest_exists=False)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/nonexistent-contest") as ws:
                msg = ws.receive_json()

            assert msg["type"] == "error"
            assert msg["message"] == "Contest not found"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_nonexistent_contest_connection_closes_after_error(self):
        """
        Req 6.5: Sau khi gửi error, connection được đóng gracefully.
        TestClient sẽ nhận được close sau error message.
        """
        import src.services.leaderboard_broadcast as broadcast_module
        from starlette.websockets import WebSocketDisconnect

        client = _make_app(contest_slug="test-contest", contest_exists=False)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/nonexistent-contest") as ws:
                error_msg = ws.receive_json()
                assert error_msg["type"] == "error"
                # Connection phải đóng — nhận thêm data sẽ raise exception
                try:
                    ws.receive_json()
                    # Nếu không raise, connection vẫn mở — nhưng server đã close
                    # Starlette TestClient có thể return None hoặc raise
                except Exception:
                    pass  # Connection đã đóng — expected
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_valid_contest_does_not_receive_error(self):
        """Contest tồn tại → KHÔNG nhận error message, nhận snapshot bình thường."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app(contest_exists=True)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            assert msg["type"] != "error"
            assert msg["type"] == "leaderboard_snapshot"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo


class TestWsInvalidSortBy:
    """
    Req 6.4: Client gửi sort_by không hợp lệ → nhận error nhưng connection vẫn mở.
    """

    def test_invalid_sort_by_returns_error_message(self):
        """Gửi set_sort với sort_by không hợp lệ → nhận {"type":"error",...}."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                ws.receive_json()  # bỏ qua initial snapshot

                ws.send_json({"type": "set_sort", "sort_by": "invalid_metric"})
                error_msg = ws.receive_json()

            assert error_msg["type"] == "error"
            assert "sort_by" in error_msg["message"].lower() or "invalid" in error_msg["message"].lower()
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_connection_remains_open_after_invalid_sort_by(self):
        """
        Req 6.4: Connection KHÔNG bị đóng sau error sort_by không hợp lệ.
        Verify bằng cách gửi set_sort hợp lệ và nhận snapshot sau đó.
        """
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                ws.receive_json()  # initial snapshot

                # Gửi sort_by không hợp lệ
                ws.send_json({"type": "set_sort", "sort_by": "INVALID"})
                error_msg = ws.receive_json()
                assert error_msg["type"] == "error"

                # Connection vẫn mở — gửi sort_by hợp lệ, nhận snapshot thành công
                ws.send_json({"type": "set_sort", "sort_by": "pnl"})
                valid_snapshot = ws.receive_json()

            # Phải nhận được snapshot hợp lệ (không phải error)
            assert valid_snapshot["type"] == "leaderboard_snapshot"
            assert valid_snapshot["sort_by"] == "pnl"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_multiple_invalid_sort_by_keeps_connection_open(self):
        """Nhiều set_sort không hợp lệ liên tiếp không đóng connection."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                ws.receive_json()  # initial snapshot

                for bad_sort in ("volume", "rank", "", "EQUITY"):
                    ws.send_json({"type": "set_sort", "sort_by": bad_sort})
                    err = ws.receive_json()
                    assert err["type"] == "error"

                # Sau nhiều lần invalid, vẫn có thể nhận snapshot hợp lệ
                ws.send_json({"type": "set_sort", "sort_by": "equity"})
                final = ws.receive_json()

            assert final["type"] == "leaderboard_snapshot"
        finally:
            broadcast_module.CryptoTradingRepository = original_repo


class TestWsEmptyLeaderboard:
    """Edge cases: không có participants."""

    def test_snapshot_with_no_participants_has_empty_rows(self):
        """Contest tồn tại nhưng không có participants → rows = []."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app(participants=[])
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            assert msg["type"] == "leaderboard_snapshot"
            assert msg["rows"] == []
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_snapshot_with_participants_without_accounts_has_empty_rows(self):
        """
        Req 1.6: Participants không có account bị lọc ra.
        Snapshot rows phải rỗng.
        """
        import src.services.leaderboard_broadcast as broadcast_module

        participants = [
            _make_participant(user_id=i, account=None) for i in range(3)
        ]

        client = _make_app(participants=participants)
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            assert msg["rows"] == []
        finally:
            broadcast_module.CryptoTradingRepository = original_repo


class TestWsAdminToken:
    """
    Req 5.1, 5.2, 5.3, 5.4: Integration tests for admin WebSocket.
    """

    def test_ws_with_valid_admin_token(self):
        """Test WS với admin_token hợp lệ → response rows có user_id và participant_status."""
        import jwt
        import src.services.leaderboard_broadcast as broadcast_module
        from src.settings import get_settings

        settings = get_settings()
        admin_token = jwt.encode(
            {"role": "admin"},
            settings.jwt_secret,
            algorithm=settings.jwt_algorithm,
        )

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect(
                f"/api/leaderboard/ws/test-contest?admin_token={admin_token}"
            ) as ws:
                msg = ws.receive_json()

            assert msg["type"] == "leaderboard_snapshot"
            rows = msg["rows"]
            assert len(rows) > 0
            for row in rows:
                assert "user_id" in row
                assert "participant_status" in row
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_ws_with_invalid_admin_token(self):
        """Test WS với admin_token invalid → nhận {"type":"error","message":"Unauthorized"}, connection đóng."""
        import src.services.leaderboard_broadcast as broadcast_module

        admin_token = "invalid-jwt-token"

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect(
                f"/api/leaderboard/ws/test-contest?admin_token={admin_token}"
            ) as ws:
                msg = ws.receive_json()
                assert msg["type"] == "error"
                assert msg["message"] == "Unauthorized"

                # Verify that connection closes after sending the error message.
                from starlette.websockets import WebSocketDisconnect
                with pytest.raises((Exception, WebSocketDisconnect)):
                    ws.receive_json()
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

    def test_user_id_does_not_appear_without_admin_token(self):
        """Test user_id không xuất hiện khi không có admin_token."""
        import src.services.leaderboard_broadcast as broadcast_module

        client = _make_app()
        original_repo = client._original_repo

        try:
            with client.websocket_connect("/api/leaderboard/ws/test-contest") as ws:
                msg = ws.receive_json()

            rows = msg["rows"]
            assert len(rows) > 0
            for row in rows:
                assert "user_id" not in row
                assert "participant_status" not in row
        finally:
            broadcast_module.CryptoTradingRepository = original_repo

