from datetime import datetime, timedelta, timezone
import subprocess
import sys
from pathlib import Path

from src.database.crypto_market_duckdb import CryptoMarketDuckDB


def _candle(open_time: datetime, price: float, volume: float = 10) -> dict:
    return {
        "open_time": open_time,
        "close_time": open_time + timedelta(minutes=1) - timedelta(milliseconds=1),
        "open": price,
        "high": price + 2,
        "low": price - 1,
        "close": price + 1,
        "volume": volume,
        "quote_volume": volume * price,
        "trade_count": 5,
        "taker_buy_base_volume": volume / 2,
        "taker_buy_quote_volume": volume * price / 2,
        "is_closed": True,
    }


def test_upsert_is_idempotent_and_loads_chronologically(tmp_path):
    repo = CryptoMarketDuckDB(tmp_path / "crypto_market.duckdb")
    start = datetime(2026, 6, 25, tzinfo=timezone.utc)

    repo.upsert_candles("BTCUSDT", "1m", [_candle(start, 100), _candle(start + timedelta(minutes=1), 101)])
    repo.upsert_candles("BTCUSDT", "1m", [_candle(start + timedelta(minutes=1), 105)])

    rows = repo.load_candles("BTCUSDT", "1m", limit=10)

    assert len(rows) == 2
    assert rows[0]["time"] == int(start.timestamp())
    assert rows[1]["open"] == 105.0
    assert rows[1]["close"] == 106.0


def test_materialize_intervals_aggregates_ohlcv(tmp_path):
    repo = CryptoMarketDuckDB(tmp_path / "crypto_market.duckdb")
    start = datetime(2026, 6, 25, tzinfo=timezone.utc)
    rows = [_candle(start + timedelta(minutes=index), 100 + index, volume=10 + index) for index in range(5)]
    repo.upsert_candles("BTCUSDT", "1m", rows)

    count = repo.materialize_intervals("BTCUSDT", intervals=("5m",))
    candles = repo.load_candles("BTCUSDT", "5m", limit=10)

    assert count == 1
    assert candles == [
        {
            "time": int(start.timestamp()),
            "open": 100.0,
            "high": 106.0,
            "low": 99.0,
            "close": 105.0,
            "volume": 60.0,
        }
    ]


def test_ingestion_state_and_retention(tmp_path):
    repo = CryptoMarketDuckDB(tmp_path / "crypto_market.duckdb")
    now = datetime(2026, 6, 25, tzinfo=timezone.utc)
    old = now - timedelta(days=366)
    repo.upsert_candles("ETHUSDT", "1m", [_candle(old, 100), _candle(now, 200)])
    repo.update_ingestion_state("ETHUSDT", "1m", now, status="success")

    state = repo.get_ingestion_state("ETHUSDT", "1m")
    deleted = repo.delete_older_than(now - timedelta(days=365))

    assert state["last_closed_open_time"] == now
    assert state["status"] == "success"
    assert deleted == 1
    assert repo.count_candles(symbol="ETHUSDT", interval="1m") == 1


def test_module_imports_from_repository_root():
    repo_root = Path(__file__).parents[2]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from backend_v2.src.database.crypto_market_duckdb import CryptoMarketDuckDB; print(CryptoMarketDuckDB.__name__)",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "CryptoMarketDuckDB"


def test_find_missing_ranges_groups_contiguous_minutes(tmp_path):
    repo = CryptoMarketDuckDB(tmp_path / "crypto_market.duckdb")
    start = datetime(2026, 6, 25, tzinfo=timezone.utc)
    repo.upsert_candles(
        "BTCUSDT",
        "1m",
        [
            _candle(start, 100),
            _candle(start + timedelta(minutes=3), 103),
            _candle(start + timedelta(minutes=5), 105),
        ],
    )

    gaps = repo.find_missing_ranges(
        "BTCUSDT",
        "1m",
        start,
        start + timedelta(minutes=5),
    )

    assert gaps == [
        (start + timedelta(minutes=1), start + timedelta(minutes=2)),
        (start + timedelta(minutes=4), start + timedelta(minutes=4)),
    ]
