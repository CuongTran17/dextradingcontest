from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.admin import _require_admin, get_crypto_contest_service, router
from src.database.crypto_models import Contest
from src.services.crypto_contests import CryptoContestService


class FakeRepo:
    db = None

    def list_contests(self):
        return []

    def get_contest_by_slug(self, slug):
        assert slug == "summer-cup"
        contest = Contest(
            id=1,
            slug="summer-cup",
            title="Summer Cup",
            mode="contest",
            status="scheduled",
            initial_balance=Decimal("10000"),
            quote_asset="USDT_TEST",
            rules_json="{}",
        )
        contest.assets = []
        contest.participants = []
        contest.onchain_contest_address = "ContestPda1111111111111111111111111111111"
        contest.onchain_initialize_tx_signature = "5" * 88
        contest.onchain_admin_wallet = "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"
        contest.onchain_initialized_at = datetime(2026, 7, 30, 10, 0, tzinfo=timezone.utc)
        return contest


def test_contest_response_includes_onchain_state():
    service = CryptoContestService(FakeRepo())

    response = service.get_contest("summer-cup")

    assert response["onchain_contest_address"] == "ContestPda1111111111111111111111111111111"
    assert response["onchain_initialize_tx_signature"] == "5" * 88
    assert response["onchain_admin_wallet"] == "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB"
    assert response["onchain_initialized_at"] == "2026-07-30T10:00:00+00:00"


class FakeContestServiceForConfirm:
    def __init__(self):
        self.confirmed = None

    def confirm_onchain_initialize(
        self,
        contest_slug,
        contest_address,
        initialize_tx_signature,
        admin_wallet,
    ):
        self.confirmed = {
            "contest_slug": contest_slug,
            "contest_address": contest_address,
            "initialize_tx_signature": initialize_tx_signature,
            "admin_wallet": admin_wallet,
        }
        return {
            "id": contest_slug,
            "title": "Summer Cup",
            "status": "upcoming",
            "raw_status": "scheduled",
            "mode": "contest",
            "initial_capital": 10000,
            "quote_asset": "USDT_TEST",
            "symbols": ["BTCUSDT"],
            "starts_at": None,
            "ends_at": None,
            "participant_count": 0,
            "onchain_contest_address": contest_address,
            "onchain_initialize_tx_signature": initialize_tx_signature,
            "onchain_admin_wallet": admin_wallet,
            "onchain_initialized_at": "2026-07-30T10:00:00+00:00",
        }


def test_admin_confirms_onchain_initialize_transaction():
    app = FastAPI()
    app.include_router(router)
    service = FakeContestServiceForConfirm()
    app.dependency_overrides[get_crypto_contest_service] = lambda: service
    app.dependency_overrides[_require_admin] = lambda: SimpleNamespace(id=9)
    client = TestClient(app)

    response = client.post(
        "/api/admin/crypto/contests/summer-cup/onchain/confirm",
        json={
            "contest_address": "ContestPda1111111111111111111111111111111",
            "initialize_tx_signature": "5" * 88,
            "admin_wallet": "ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB",
        },
    )

    assert response.status_code == 200
    assert response.json()["onchain_contest_address"] == "ContestPda1111111111111111111111111111111"
    assert service.confirmed["contest_slug"] == "summer-cup"
