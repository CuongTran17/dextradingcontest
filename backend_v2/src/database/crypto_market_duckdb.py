from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb

from src.settings import REPO_ROOT, get_settings

INTERVAL_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
    "4h": 240,
}


def _utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _utc_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_path(path_value: str | Path | None = None) -> Path:
    raw = Path(path_value or get_settings().crypto_duckdb_path)
    return raw if raw.is_absolute() else REPO_ROOT / raw


class CryptoMarketDuckDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _resolve_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> duckdb.DuckDBPyConnection:
        return duckdb.connect(str(self.db_path))

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_candles (
                    exchange VARCHAR NOT NULL,
                    market_type VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    interval VARCHAR NOT NULL,
                    open_time TIMESTAMP NOT NULL,
                    close_time TIMESTAMP NOT NULL,
                    open DOUBLE NOT NULL,
                    high DOUBLE NOT NULL,
                    low DOUBLE NOT NULL,
                    close DOUBLE NOT NULL,
                    volume DOUBLE NOT NULL,
                    quote_volume DOUBLE NOT NULL,
                    trade_count BIGINT NOT NULL,
                    taker_buy_base_volume DOUBLE NOT NULL,
                    taker_buy_quote_volume DOUBLE NOT NULL,
                    is_closed BOOLEAN NOT NULL,
                    source VARCHAR NOT NULL,
                    ingested_at TIMESTAMP NOT NULL,
                    PRIMARY KEY (exchange, market_type, symbol, interval, open_time)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS crypto_ingestion_state (
                    exchange VARCHAR NOT NULL,
                    market_type VARCHAR NOT NULL,
                    symbol VARCHAR NOT NULL,
                    interval VARCHAR NOT NULL,
                    last_closed_open_time TIMESTAMP,
                    last_checked_at TIMESTAMP NOT NULL,
                    status VARCHAR NOT NULL,
                    last_error VARCHAR,
                    PRIMARY KEY (exchange, market_type, symbol, interval)
                )
                """
            )

    def upsert_candles(
        self,
        symbol: str,
        interval: str,
        rows: Iterable[dict[str, Any]],
        *,
        exchange: str = "binance",
        market_type: str = "spot",
        source: str = "binance",
    ) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        payload = [
            (
                exchange,
                market_type,
                symbol.upper(),
                interval,
                _utc_naive(row["open_time"]),
                _utc_naive(row["close_time"]),
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row.get("volume", 0)),
                float(row.get("quote_volume", 0)),
                int(row.get("trade_count", 0)),
                float(row.get("taker_buy_base_volume", 0)),
                float(row.get("taker_buy_quote_volume", 0)),
                bool(row.get("is_closed", True)),
                source,
                now,
            )
            for row in rows
        ]
        if not payload:
            return 0

        with self.connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.executemany(
                    """
                    DELETE FROM crypto_candles
                    WHERE exchange = ? AND market_type = ? AND symbol = ?
                      AND interval = ? AND open_time = ?
                    """,
                    [(row[0], row[1], row[2], row[3], row[4]) for row in payload],
                )
                conn.executemany(
                    """
                    INSERT INTO crypto_candles VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    payload,
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return len(payload)

    def load_candles(
        self,
        symbol: str,
        interval: str,
        *,
        limit: int = 1000,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> list[dict[str, float | int]]:
        query = """
            SELECT open_time, open, high, low, close, volume
            FROM crypto_candles
            WHERE exchange = 'binance' AND market_type = 'spot'
              AND symbol = ? AND interval = ? AND is_closed = TRUE
        """
        params: list[Any] = [symbol.upper(), interval]
        if start_time is not None:
            query += " AND open_time >= ?"
            params.append(_utc_naive(start_time))
        if end_time is not None:
            query += " AND open_time <= ?"
            params.append(_utc_naive(end_time))
        query += " ORDER BY open_time DESC LIMIT ?"
        params.append(max(1, int(limit)))

        with self.connect() as conn:
            records = list(reversed(conn.execute(query, params).fetchall()))

        return [
            {
                "time": int(_utc_aware(row[0]).timestamp()),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            }
            for row in records
        ]

    def materialize_intervals(
        self,
        symbol: str,
        *,
        intervals: tuple[str, ...] = ("5m", "15m", "1h", "4h"),
    ) -> int:
        inserted = 0
        normalized = symbol.upper()
        with self.connect() as conn:
            for interval in intervals:
                minutes = INTERVAL_MINUTES[interval]
                bucket_literal = f"{minutes} minutes"
                rows = conn.execute(
                    f"""
                    SELECT
                        time_bucket(INTERVAL '{bucket_literal}', open_time) AS bucket,
                        arg_min(open, open_time) AS open,
                        max(high) AS high,
                        min(low) AS low,
                        arg_max(close, open_time) AS close,
                        sum(volume) AS volume,
                        sum(quote_volume) AS quote_volume,
                        sum(trade_count) AS trade_count,
                        sum(taker_buy_base_volume) AS taker_buy_base_volume,
                        sum(taker_buy_quote_volume) AS taker_buy_quote_volume
                    FROM crypto_candles
                    WHERE exchange = 'binance' AND market_type = 'spot'
                      AND symbol = ? AND interval = '1m' AND is_closed = TRUE
                    GROUP BY bucket
                    HAVING count(*) = ?
                    ORDER BY bucket
                    """,
                    [normalized, minutes],
                ).fetchall()
                candles = [
                    {
                        "open_time": row[0],
                        "close_time": row[0]
                        + timedelta(minutes=minutes)
                        - timedelta(milliseconds=1),
                        "open": row[1],
                        "high": row[2],
                        "low": row[3],
                        "close": row[4],
                        "volume": row[5],
                        "quote_volume": row[6],
                        "trade_count": row[7],
                        "taker_buy_base_volume": row[8],
                        "taker_buy_quote_volume": row[9],
                        "is_closed": True,
                    }
                    for row in rows
                ]
                inserted += self.upsert_candles(
                    normalized,
                    interval,
                    candles,
                    source="derived-1m",
                )
        return inserted

    def update_ingestion_state(
        self,
        symbol: str,
        interval: str,
        last_closed_open_time: datetime | None,
        *,
        status: str,
        last_error: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        key = ["binance", "spot", symbol.upper(), interval]
        with self.connect() as conn:
            conn.execute(
                """
                DELETE FROM crypto_ingestion_state
                WHERE exchange = ? AND market_type = ? AND symbol = ? AND interval = ?
                """,
                key,
            )
            conn.execute(
                """
                INSERT INTO crypto_ingestion_state VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    *key,
                    _utc_naive(last_closed_open_time) if last_closed_open_time else None,
                    now,
                    status,
                    last_error,
                ],
            )

    def get_ingestion_state(self, symbol: str, interval: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT last_closed_open_time, last_checked_at, status, last_error
                FROM crypto_ingestion_state
                WHERE exchange = 'binance' AND market_type = 'spot'
                  AND symbol = ? AND interval = ?
                """,
                [symbol.upper(), interval],
            ).fetchone()
        if row is None:
            return None
        return {
            "last_closed_open_time": _utc_aware(row[0]) if row[0] else None,
            "last_checked_at": _utc_aware(row[1]),
            "status": row[2],
            "last_error": row[3],
        }

    def delete_older_than(self, cutoff: datetime) -> int:
        with self.connect() as conn:
            before = conn.execute("SELECT count(*) FROM crypto_candles").fetchone()[0]
            conn.execute(
                "DELETE FROM crypto_candles WHERE open_time < ?",
                [_utc_naive(cutoff)],
            )
            after = conn.execute("SELECT count(*) FROM crypto_candles").fetchone()[0]
        return int(before - after)

    def count_candles(
        self,
        *,
        symbol: str | None = None,
        interval: str | None = None,
    ) -> int:
        clauses = ["1 = 1"]
        params: list[Any] = []
        if symbol:
            clauses.append("symbol = ?")
            params.append(symbol.upper())
        if interval:
            clauses.append("interval = ?")
            params.append(interval)
        with self.connect() as conn:
            return int(
                conn.execute(
                    f"SELECT count(*) FROM crypto_candles WHERE {' AND '.join(clauses)}",
                    params,
                ).fetchone()[0]
            )


class LazyCryptoMarketDuckDB:
    def __init__(self):
        self._repo: CryptoMarketDuckDB | None = None

    def _get_repo(self) -> CryptoMarketDuckDB:
        if self._repo is None:
            self._repo = CryptoMarketDuckDB()
        return self._repo

    def __getattr__(self, name: str):
        return getattr(self._get_repo(), name)


crypto_market_repo = LazyCryptoMarketDuckDB()
