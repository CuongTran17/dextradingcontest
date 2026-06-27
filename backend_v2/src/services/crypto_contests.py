from datetime import datetime, timezone

from src.database.crypto_models import Contest
from src.repositories.crypto_trading import CryptoTradingRepository


class ContestNotFoundError(Exception):
    pass


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _public_status(contest: Contest) -> str:
    if contest.mode == "practice":
        return "practice"
    if contest.status in {"draft", "scheduled"}:
        return "upcoming"
    if contest.status in {"active", "settling"}:
        return "active"
    return "ended"


class CryptoContestService:
    def __init__(self, repository: CryptoTradingRepository):
        self.repository = repository

    def list_contests(self) -> list[dict]:
        return [self._map_contest(contest) for contest in self.repository.list_contests()]

    def get_contest(self, slug: str) -> dict:
        contest = self.repository.get_contest_by_slug(slug)
        if contest is None:
            raise ContestNotFoundError(f"Contest '{slug}' not found")
        return self._map_contest(contest)

    def _map_contest(self, contest: Contest) -> dict:
        enabled_assets = [
            item.asset
            for item in contest.assets
            if item.is_enabled and item.asset.is_active
        ]
        return {
            "id": contest.slug,
            "title": contest.title,
            "status": _public_status(contest),
            "raw_status": contest.status,
            "mode": contest.mode,
            "initial_capital": float(contest.initial_balance),
            "quote_asset": contest.quote_asset,
            "symbols": [asset.symbol for asset in enabled_assets],
            "starts_at": _iso(contest.starts_at),
            "ends_at": _iso(contest.ends_at),
            "participant_count": len(contest.participants),
        }
