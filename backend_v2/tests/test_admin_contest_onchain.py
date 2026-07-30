from datetime import datetime, timezone
from decimal import Decimal

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
