from datetime import datetime, timedelta, timezone

from src.services.crypto_market_backfill import (
    DEFAULT_SYMBOLS,
    CryptoMarketBackfillService,
)


def _row(open_time: datetime) -> dict:
    return {
        "open_time": open_time,
        "close_time": open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        "open": 100,
        "high": 102,
        "low": 99,
        "close": 101,
        "volume": 10,
        "quote_volume": 1000,
        "trade_count": 5,
        "taker_buy_base_volume": 5,
        "taker_buy_quote_volume": 500,
        "is_closed": True,
    }


class FakeRepo:
    def __init__(self, last_open_time=None, first_open_time=None):
        self.last_open_time = last_open_time
        self.first_open_time = first_open_time or last_open_time
        self.saved = []
        self.states = []
        self.materialized = []

    def get_ingestion_state(self, symbol, interval):
        if self.last_open_time is None:
            return None
        return {"last_closed_open_time": self.last_open_time}

    def get_candle_bounds(self, symbol, interval):
        if self.first_open_time is None:
            return None
        return {
            "first_open_time": self.first_open_time,
            "last_open_time": self.last_open_time,
        }

    def upsert_candles(self, symbol, interval, rows):
        self.saved.extend(rows)
        self.last_open_time = rows[-1]["open_time"]
        return len(rows)

    def update_ingestion_state(self, symbol, interval, last_open_time, **kwargs):
        self.states.append((symbol, interval, last_open_time, kwargs["status"]))

    def materialize_intervals(self, symbol):
        self.materialized.append(symbol)
        return 0


def test_backfill_pages_forward_and_stores_closed_candles_only():
    now = datetime(2026, 6, 25, 0, 5, 30, tzinfo=timezone.utc)
    start = now - timedelta(minutes=4, seconds=30)
    calls = []

    def fetch_page(symbol, interval, limit, start_time, end_time):
        calls.append(start_time)
        if len(calls) == 1:
            return [_row(start), _row(start + timedelta(minutes=1))]
        if len(calls) == 2:
            return [
                _row(start + timedelta(minutes=2)),
                {**_row(start + timedelta(minutes=4)), "is_closed": False},
            ]
        return []

    repo = FakeRepo()
    service = CryptoMarketBackfillService(repo, fetch_page, now_provider=lambda: now)

    result = service.backfill_symbol("BTCUSDT", days=1, start_time=start, page_limit=2)

    assert result["stored"] == 3
    assert calls[1] == start + timedelta(minutes=2)
    assert len(repo.saved) == 3
    assert repo.materialized == ["BTCUSDT"]
    assert repo.states[-1][3] == "success"


def test_backfill_resumes_after_last_closed_candle():
    now = datetime(2026, 6, 25, 0, 10, tzinfo=timezone.utc)
    last = datetime(2026, 6, 25, 0, 7, tzinfo=timezone.utc)
    starts = []

    def fetch_page(symbol, interval, limit, start_time, end_time):
        starts.append(start_time)
        return []

    service = CryptoMarketBackfillService(
        FakeRepo(last, first_open_time=now - timedelta(days=365)),
        fetch_page,
        now_provider=lambda: now,
    )
    service.backfill_symbol("ETHUSDT", days=365)

    assert starts == [last + timedelta(minutes=1)]


def test_default_symbols_match_supported_spot_market():
    assert DEFAULT_SYMBOLS == (
        "BTCUSDT",
        "ETHUSDT",
        "SOLUSDT",
        "XRPUSDT",
        "BNBUSDT",
    )


def test_backfill_expands_an_existing_short_window_backwards():
    now = datetime(2026, 6, 25, 0, 10, tzinfo=timezone.utc)
    existing_first = now - timedelta(days=1)
    requested_starts = []

    def fetch_page(symbol, interval, limit, start_time, end_time):
        requested_starts.append(start_time)
        return []

    repo = FakeRepo(
        last_open_time=now - timedelta(minutes=2),
        first_open_time=existing_first,
    )
    service = CryptoMarketBackfillService(
        repo,
        fetch_page,
        now_provider=lambda: now,
    )

    service.backfill_symbol("BTCUSDT", days=365)

    assert requested_starts[0] == now - timedelta(days=365)
