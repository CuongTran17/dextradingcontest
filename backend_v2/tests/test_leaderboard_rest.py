"""
Integration tests cho REST endpoint GET /api/leaderboard/{contest_id}.

Validates: Requirements 4.1, 4.3, 4.4, 4.5
"""
from __future__ import annotations

import re
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.database.db import get_db
from src.routes.leaderboard import router


# ---------------------------------------------------------------------------
# Helpers: build mock objects that match what the real ORM returns
# ---------------------------------------------------------------------------


def make_balance(asset: str, available: float) -> SimpleNamespace:
    return SimpleNamespace(asset=asset, available=Decimal(str(available)))


def make_position(symbol: str, quantity: float) -> SimpleNamespace:
    return SimpleNamespace(
        quantity=Decimal(str(quantity)),
        asset=SimpleNamespace(symbol=symbol),
    )


def make_order(
    symbol: str = "BTCUSDT",
    side: str = "buy",
    status: str = "filled",
    executed_notional: float = 5000.0,
    submitted_at: object = None,
) -> SimpleNamespace:
    from datetime import datetime, timezone

    if submitted_at is None:
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


def make_contest(
    slug: str = "test-contest",
    quote_asset: str = "USDT_TEST",
    initial_balance: float = 10_000.0,
    assets: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        slug=slug,
        quote_asset=quote_asset,
        initial_balance=Decimal(str(initial_balance)),
        assets=assets or [],
    )


# ---------------------------------------------------------------------------
# Fake dependencies
# ---------------------------------------------------------------------------


class FakeRepo:
    """Fake CryptoTradingRepository — controls contest lookup and participant list."""

    def __init__(
        self,
        contest: SimpleNamespace | None,
        participants: list[SimpleNamespace] | None = None,
    ):
        self._contest = contest
        self._participants = participants or []

    def get_contest_by_slug(self, slug: str) -> SimpleNamespace | None:
        if self._contest is not None and self._contest.slug == slug:
            return self._contest
        return None

    def list_contest_participants(self, slug: str) -> list[SimpleNamespace]:
        return self._participants


class FakeRealtimeCache:
    """Returns a fixed prices dict."""

    def __init__(self, prices: dict[str, float] | None = None):
        self._prices = prices or {}

    def get_prices(self) -> dict[str, float]:
        return self._prices


class FakeRealtimeService:
    def __init__(self, prices: dict[str, float] | None = None):
        self.cache = FakeRealtimeCache(prices)


# ---------------------------------------------------------------------------
# App factory — wires fake dependencies without touching the DB or lifespan
# ---------------------------------------------------------------------------


def build_test_app(
    contest: SimpleNamespace | None,
    participants: list[SimpleNamespace] | None = None,
    prices: dict[str, float] | None = None,
) -> FastAPI:
    """
    Build a minimal FastAPI test app with the leaderboard router and
    dependency overrides so no real DB or external service is needed.
    """
    from unittest.mock import patch

    app = FastAPI()
    app.include_router(router)

    # Override get_db — the repo is patched at module level below
    app.dependency_overrides[get_db] = lambda: None  # db session not used directly

    # Inject fake realtime service into app state
    if prices is not None:
        app.state.crypto_realtime = FakeRealtimeService(prices)
    # If prices is None, no crypto_realtime on app.state → triggers Binance REST fallback

    # Patch CryptoTradingRepository wherever the route imports it
    fake_repo = FakeRepo(contest, participants or [])

    # We patch it inside the routes module
    import src.routes.leaderboard as leaderboard_module

    original_repo_cls = leaderboard_module.__dict__.get("CryptoTradingRepository")

    class PatchedRepo:
        def __new__(cls, db):  # noqa: D102
            return fake_repo

    leaderboard_module.CryptoTradingRepository = PatchedRepo

    # Store original so we can restore later (handled by pytest fixture teardown)
    app._original_repo_cls = original_repo_cls
    app._leaderboard_module = leaderboard_module

    return app


# ---------------------------------------------------------------------------
# Pytest fixture for test client — clean monkey-patch each test
# ---------------------------------------------------------------------------


@pytest.fixture()
def rest_client_factory():
    """
    Factory fixture that yields a function: build_client(contest, participants, prices)
    → TestClient.  Restores the patched module after each test.
    """
    apps_created: list[FastAPI] = []

    def _factory(
        contest: SimpleNamespace | None,
        participants: list[SimpleNamespace] | None = None,
        prices: dict[str, float] | None = None,
    ) -> TestClient:
        app = build_test_app(contest, participants, prices)
        apps_created.append(app)
        return TestClient(app, raise_server_exceptions=True)

    yield _factory

    # Teardown: restore patched module
    for app in apps_created:
        module = getattr(app, "_leaderboard_module", None)
        original = getattr(app, "_original_repo_cls", None)
        if module is not None and original is not None:
            module.CryptoTradingRepository = original


# ---------------------------------------------------------------------------
# Tests: Requirement 4.1 — response structure and sort_by
# ---------------------------------------------------------------------------


class TestLeaderboardResponseStructure:
    """GET /api/leaderboard/{contest_id} — structure correctness (Req 4.1, 4.5)."""

    def test_response_has_required_top_level_fields(self, rest_client_factory):
        contest = make_contest(slug="summer-2024")
        participant = make_participant(
            user_id=1,
            fullname="Alice",
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", 11_000.0)],
            ),
        )
        client = rest_client_factory(contest, [participant], prices={})

        response = client.get("/api/leaderboard/summer-2024")

        assert response.status_code == 200
        body = response.json()
        assert "contest_id" in body
        assert "sort_by" in body
        assert "updated_at" in body
        assert "rows" in body

    def test_response_contest_id_matches_slug(self, rest_client_factory):
        contest = make_contest(slug="spring-2025")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/spring-2025")

        assert response.status_code == 200
        assert response.json()["contest_id"] == "spring-2025"

    def test_rows_have_public_fields(self, rest_client_factory):
        contest = make_contest(slug="alpha")
        participant = make_participant(
            user_id=5,
            fullname="Bob",
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", 10_500.0)],
            ),
        )
        client = rest_client_factory(contest, [participant], prices={})

        response = client.get("/api/leaderboard/alpha")

        assert response.status_code == 200
        row = response.json()["rows"][0]
        required_fields = {"rank", "user", "equity", "pnl", "roi", "volume", "trade_count", "last_trade"}
        assert required_fields <= set(row.keys())

    def test_rows_sorted_by_equity_by_default(self, rest_client_factory):
        """Default sort_by = equity — highest equity first (Req 4.1, 2.2)."""
        contest = make_contest(slug="c1")
        participants = [
            make_participant(
                user_id=1,
                fullname="Alice",
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 12_000.0)],  # best equity
                ),
            ),
            make_participant(
                user_id=2,
                fullname="Bob",
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 9_000.0)],
                ),
            ),
            make_participant(
                user_id=3,
                fullname="Carol",
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", 10_500.0)],
                ),
            ),
        ]
        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/c1")

        assert response.status_code == 200
        rows = response.json()["rows"]
        equities = [r["equity"] for r in rows]
        assert equities == sorted(equities, reverse=True)
        assert rows[0]["equity"] == 12_000.0

    def test_sort_by_pnl(self, rest_client_factory):
        """?sort_by=pnl — rows sorted descending by pnl."""
        contest = make_contest(slug="c2")
        participants = [
            make_participant(
                user_id=1,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", v)],
                ),
            )
            for v in [11_500.0, 8_000.0, 10_200.0]
        ]
        # Assign different user_ids properly
        for idx, p in enumerate(participants, start=1):
            p.user_id = idx
            p.user = SimpleNamespace(
                id=idx,
                fullname=f"User{idx}",
                first_name=None,
                last_name=None,
                email=f"u{idx}@t.com",
            )

        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/c2?sort_by=pnl")

        assert response.status_code == 200
        body = response.json()
        assert body["sort_by"] == "pnl"
        pnls = [r["pnl"] for r in body["rows"]]
        assert pnls == sorted(pnls, reverse=True)

    def test_sort_by_roi(self, rest_client_factory):
        """?sort_by=roi — rows sorted descending by roi."""
        contest = make_contest(slug="c3")
        participants = [
            make_participant(
                user_id=i,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", float(9_000 + i * 700))],
                ),
            )
            for i in range(1, 4)
        ]
        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/c3?sort_by=roi")

        assert response.status_code == 200
        body = response.json()
        assert body["sort_by"] == "roi"
        rois = [r["roi"] for r in body["rows"]]
        assert rois == sorted(rois, reverse=True)

    def test_rank_is_contiguous_from_one(self, rest_client_factory):
        """Ranks must be 1..N with no gaps or duplicates."""
        contest = make_contest(slug="rank-test")
        participants = [
            make_participant(
                user_id=i,
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", float(8_000 + i * 500))],
                ),
            )
            for i in range(1, 6)
        ]
        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/rank-test")

        assert response.status_code == 200
        rows = response.json()["rows"]
        ranks = sorted(r["rank"] for r in rows)
        assert ranks == list(range(1, 6))


# ---------------------------------------------------------------------------
# Tests: Requirement 4.3 — HTTP 404 when contest does not exist
# ---------------------------------------------------------------------------


class TestLeaderboard404:
    """GET /api/leaderboard/{contest_id} — 404 for missing contest (Req 4.3)."""

    def test_returns_404_when_contest_not_found(self, rest_client_factory):
        client = rest_client_factory(contest=None)  # repo returns None for any slug

        response = client.get("/api/leaderboard/nonexistent-contest")

        assert response.status_code == 404

    def test_404_body_contains_detail(self, rest_client_factory):
        """Response body must mention the contest id in the detail message."""
        client = rest_client_factory(contest=None)

        response = client.get("/api/leaderboard/missing-slug")

        assert response.status_code == 404
        detail = response.json()["detail"]
        assert "missing-slug" in detail

    def test_returns_404_for_different_slug(self, rest_client_factory):
        """A real contest exists but a different slug is requested."""
        contest = make_contest(slug="existing-contest")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/some-other-slug")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Requirement 4.4 — no authentication required
# ---------------------------------------------------------------------------


class TestLeaderboardNoAuth:
    """REST endpoint is public — no auth required (Req 4.4)."""

    def test_no_auth_header_returns_200(self, rest_client_factory):
        contest = make_contest(slug="public-contest")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/public-contest")

        assert response.status_code == 200

    def test_does_not_return_401_or_403(self, rest_client_factory):
        contest = make_contest(slug="open-contest")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/open-contest")

        assert response.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# Tests: Requirement 4.5 — updated_at in ISO8601 UTC
# ---------------------------------------------------------------------------


class TestLeaderboardUpdatedAt:
    """updated_at field must be present and ISO8601 UTC (Req 4.5)."""

    # ISO8601 UTC: "2024-01-01T12:00:00Z" or "2024-01-01T12:00:00+00:00"
    _ISO8601_UTC_RE = re.compile(
        r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(Z|[+-]00:00)$"
    )

    def test_updated_at_field_is_present(self, rest_client_factory):
        contest = make_contest(slug="ts-test")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/ts-test")

        assert response.status_code == 200
        assert "updated_at" in response.json()

    def test_updated_at_is_iso8601_utc_format(self, rest_client_factory):
        """updated_at must match ISO8601 UTC format."""
        contest = make_contest(slug="ts-format")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/ts-format")

        assert response.status_code == 200
        updated_at = response.json()["updated_at"]
        assert updated_at, "updated_at must not be empty"
        assert self._ISO8601_UTC_RE.match(updated_at), (
            f"updated_at={updated_at!r} does not match ISO8601 UTC pattern"
        )

    def test_updated_at_is_string_not_null(self, rest_client_factory):
        contest = make_contest(slug="ts-notnull")
        client = rest_client_factory(contest, [], prices={})

        response = client.get("/api/leaderboard/ts-notnull")

        assert response.status_code == 200
        updated_at = response.json()["updated_at"]
        assert isinstance(updated_at, str)
        assert updated_at != ""


# ---------------------------------------------------------------------------
# Tests: Requirement 5.3 — user_id absent from public response
# ---------------------------------------------------------------------------


class TestLeaderboardUserIdHidden:
    """user_id must NOT appear in public (non-admin) response rows (Req 5.3)."""

    def test_user_id_not_in_row(self, rest_client_factory):
        contest = make_contest(slug="privacy-test")
        participant = make_participant(
            user_id=42,
            fullname="Secret User",
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", 11_000.0)],
            ),
        )
        client = rest_client_factory(contest, [participant], prices={})

        response = client.get("/api/leaderboard/privacy-test")

        assert response.status_code == 200
        rows = response.json()["rows"]
        assert len(rows) == 1
        assert "user_id" not in rows[0], (
            "user_id must not be exposed in the public REST response"
        )

    def test_user_id_not_in_any_row(self, rest_client_factory):
        """Even with multiple participants, no row should expose user_id."""
        contest = make_contest(slug="privacy-multi")
        participants = [
            make_participant(
                user_id=i,
                fullname=f"User {i}",
                account=make_account(
                    initial_equity=10_000.0,
                    balances=[make_balance("USDT_TEST", float(10_000 + i * 200))],
                ),
            )
            for i in range(1, 4)
        ]
        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/privacy-multi")

        assert response.status_code == 200
        for row in response.json()["rows"]:
            assert "user_id" not in row

    def test_participant_status_not_in_public_row(self, rest_client_factory):
        """participant_status is also admin-only — should not appear in public rows."""
        contest = make_contest(slug="status-test")
        participant = make_participant(
            user_id=7,
            status="disqualified",
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", 9_000.0)],
            ),
        )
        client = rest_client_factory(contest, [participant], prices={})

        response = client.get("/api/leaderboard/status-test")

        assert response.status_code == 200
        row = response.json()["rows"][0]
        assert "participant_status" not in row


# ---------------------------------------------------------------------------
# Tests: prices integration — positions reflected in equity
# ---------------------------------------------------------------------------


class TestLeaderboardPriceIntegration:
    """Verify that realtime prices feed into the equity calculation."""

    def test_position_value_reflected_in_equity(self, rest_client_factory):
        """equity = cash + qty * price — prices from RealtimeMarketCache."""
        contest = make_contest(slug="price-test")
        participant = make_participant(
            user_id=1,
            fullname="Trader",
            account=make_account(
                initial_equity=10_000.0,
                balances=[make_balance("USDT_TEST", 5_000.0)],
                positions=[make_position("BTCUSDT", 0.1)],
            ),
        )
        prices = {"BTCUSDT": 60_000.0}
        client = rest_client_factory(contest, [participant], prices=prices)

        response = client.get("/api/leaderboard/price-test")

        assert response.status_code == 200
        row = response.json()["rows"][0]
        expected_equity = round(5_000.0 + 0.1 * 60_000.0, 2)
        assert row["equity"] == expected_equity

    def test_empty_rows_when_no_participants_with_account(self, rest_client_factory):
        """Participants without TradingAccount are filtered — rows is empty list."""
        contest = make_contest(slug="empty-contest")
        participants = [make_participant(user_id=i, account=None) for i in range(3)]
        client = rest_client_factory(contest, participants, prices={})

        response = client.get("/api/leaderboard/empty-contest")

        assert response.status_code == 200
        assert response.json()["rows"] == []
