from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pandas as pd

try:
    from src.settings import REPO_ROOT, get_settings
except ModuleNotFoundError:
    from backend_v2.src.settings import REPO_ROOT, get_settings


def _resolve_duckdb_path(path_value: str | Path | None = None) -> Path:
    raw = Path(path_value or get_settings().duckdb_path)
    return raw if raw.is_absolute() else REPO_ROOT / raw


def _to_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def _optional_date(value: Any) -> date | None:
    if value is None:
        return None
    return _to_date(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)


def _actual_direction(future_return_pct: float | None) -> str | None:
    if future_return_pct is None:
        return None
    if future_return_pct > 0:
        return "UP"
    if future_return_pct < 0:
        return "DOWN"
    return "FLAT"


def _prediction_is_correct(decision: str | None, future_return_pct: float | None) -> bool | None:
    if decision is None or future_return_pct is None:
        return None

    normalized = decision.upper()
    if normalized == "BUY":
        return future_return_pct > 0
    if normalized == "SELL":
        return future_return_pct < 0
    if normalized == "HOLD":
        return abs(future_return_pct) <= 2
    return None


@dataclass(frozen=True)
class TechnicalCacheRow:
    symbol: str
    start_date: date | None
    end_date: date | None
    limit_value: int
    history_count: int
    history_last_time: str | None
    payload_json: str
    source: str
    updated_at: datetime


class MarketDuckDB:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _resolve_duckdb_path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.ensure_schema()

    def connect(self) -> duckdb.DuckDBPyConnection:
        last_exc: Exception | None = None
        for attempt in range(5):
            try:
                return duckdb.connect(str(self.db_path))
            except duckdb.IOException as exc:
                message = str(exc).lower()
                is_lock_error = (
                    "being used by another process" in message
                    or "access is denied" in message
                    or "cannot open file" in message
                )
                if not is_lock_error or attempt == 4:
                    raise
                last_exc = exc
                time.sleep(0.25 * (attempt + 1))
        raise last_exc or RuntimeError("Could not connect to DuckDB")

    def ensure_schema(self) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_ohlcv (
                    symbol VARCHAR NOT NULL,
                    date DATE NOT NULL,
                    open DOUBLE NOT NULL DEFAULT 0,
                    high DOUBLE NOT NULL DEFAULT 0,
                    low DOUBLE NOT NULL DEFAULT 0,
                    close DOUBLE NOT NULL DEFAULT 0,
                    volume BIGINT NOT NULL DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (symbol, date)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS technical_cache (
                    symbol VARCHAR NOT NULL,
                    start_date DATE,
                    end_date DATE,
                    limit_value INTEGER NOT NULL DEFAULT 365,
                    history_count INTEGER NOT NULL DEFAULT 0,
                    history_last_time VARCHAR,
                    payload_json VARCHAR NOT NULL,
                    source VARCHAR NOT NULL DEFAULT 'duckdb',
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_features_daily (
                    symbol VARCHAR NOT NULL,
                    data_date DATE NOT NULL,
                    run_id VARCHAR NOT NULL,
                    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS market_feature_runs (
                    run_id VARCHAR PRIMARY KEY,
                    row_count BIGINT NOT NULL,
                    symbol_count BIGINT NOT NULL,
                    min_date DATE,
                    max_date DATE,
                    source_path VARCHAR,
                    loaded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_analysis_runs (
                    analysis_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    analysis_date DATE NOT NULL,
                    horizon_days INTEGER NOT NULL DEFAULT 5,
                    model_version VARCHAR NOT NULL,
                    prompt_version VARCHAR NOT NULL,
                    context_hash VARCHAR NOT NULL,
                    request_hash VARCHAR NOT NULL,
                    response_hash VARCHAR,
                    market_feature_run_id VARCHAR,
                    current_price DOUBLE,
                    decision VARCHAR,
                    confidence DOUBLE,
                    reasoning VARCHAR,
                    key_factors_json VARCHAR NOT NULL DEFAULT '[]',
                    status VARCHAR NOT NULL,
                    error_message VARCHAR,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_analysis_payloads (
                    analysis_id VARCHAR PRIMARY KEY,
                    request_context_json VARCHAR NOT NULL,
                    prompt_text VARCHAR NOT NULL,
                    kaggle_response_json VARCHAR,
                    raw_output VARCHAR,
                    normalized_output_json VARCHAR,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_prediction_outcomes (
                    analysis_id VARCHAR NOT NULL,
                    horizon_days INTEGER NOT NULL,
                    entry_price DOUBLE,
                    exit_date DATE,
                    exit_price DOUBLE,
                    future_return_pct DOUBLE,
                    actual_direction VARCHAR,
                    is_correct BOOLEAN,
                    evaluated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (analysis_id, horizon_days)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ai_generation_jobs (
                    job_id VARCHAR PRIMARY KEY,
                    symbol VARCHAR NOT NULL,
                    user_id BIGINT,
                    force BOOLEAN NOT NULL DEFAULT FALSE,
                    status VARCHAR NOT NULL,
                    analysis_id VARCHAR,
                    result_json VARCHAR,
                    error_message VARCHAR,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP
                )
                """
            )

    def upsert_daily_rows(self, symbol: str, rows: Iterable[dict[str, Any]]) -> int:
        normalized = symbol.strip().upper()
        payload = [
            (
                normalized,
                _to_date(row["date"]),
                float(row.get("open") or 0),
                float(row.get("high") or 0),
                float(row.get("low") or 0),
                float(row.get("close") or 0),
                int(float(row.get("volume") or 0)),
                datetime.now(timezone.utc).replace(tzinfo=None),
            )
            for row in rows
        ]
        if not payload:
            return 0

        with self.connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.executemany(
                    "DELETE FROM daily_ohlcv WHERE symbol = ? AND date = ?",
                    [(item[0], item[1]) for item in payload],
                )
                conn.executemany(
                    """
                    INSERT INTO daily_ohlcv
                        (symbol, date, open, high, low, close, volume, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (item[0], item[1], item[2], item[3], item[4], item[5], item[6], item[7], item[7])
                        for item in payload
                    ],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return len(payload)

    def load_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 365,
    ) -> list[dict[str, Any]]:
        query = """
            SELECT date, open, high, low, close, volume
            FROM daily_ohlcv
            WHERE symbol = ?
        """
        params: list[Any] = [symbol.strip().upper()]
        if start_date is not None:
            query += " AND date >= ?"
            params.append(start_date)
        if end_date is not None:
            query += " AND date <= ?"
            params.append(end_date)
        query += " ORDER BY date DESC LIMIT ?"
        params.append(max(limit, 1))

        with self.connect() as conn:
            records = conn.execute(query, params).fetchall()

        rows = list(reversed(records))
        return [
            {
                "time": item[0].isoformat(),
                "open": float(item[1]),
                "high": float(item[2]),
                "low": float(item[3]),
                "close": float(item[4]),
                "volume": int(item[5]),
            }
            for item in rows
        ]

    @staticmethod
    def _technical_where_clause(
        *,
        symbol: str,
        limit: int,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[str, list[Any]]:
        clauses = ["symbol = ?", "limit_value = ?"]
        params: list[Any] = [symbol.strip().upper(), int(limit)]
        if start_date is None:
            clauses.append("start_date IS NULL")
        else:
            clauses.append("start_date = ?")
            params.append(start_date)
        if end_date is None:
            clauses.append("end_date IS NULL")
        else:
            clauses.append("end_date = ?")
            params.append(end_date)
        return " AND ".join(clauses), params

    def upsert_technical_cache(
        self,
        symbol: str,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        history_count: int,
        history_last_time: str | None,
        payload: dict[str, Any],
        source: str = "duckdb",
    ) -> str:
        normalized = symbol.strip().upper()
        safe_start = _optional_date(start_date)
        safe_end = _optional_date(end_date)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        payload_json = json.dumps(payload, ensure_ascii=False, default=str)
        where_sql, where_params = self._technical_where_clause(
            symbol=normalized,
            limit=limit,
            start_date=safe_start,
            end_date=safe_end,
        )

        with self.connect() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(
                    f"DELETE FROM technical_cache WHERE {where_sql}",
                    where_params,
                )
                conn.execute(
                    """
                    INSERT INTO technical_cache
                        (symbol, start_date, end_date, limit_value, history_count, history_last_time, payload_json, source, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        normalized,
                        safe_start,
                        safe_end,
                        int(limit),
                        int(history_count),
                        history_last_time,
                        payload_json,
                        source,
                        now,
                    ],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return now.replace(tzinfo=timezone.utc).isoformat()

    def load_technical_cache(
        self,
        symbol: str,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> tuple[TechnicalCacheRow | None, dict[str, Any] | None]:
        normalized = symbol.strip().upper()
        safe_start = _optional_date(start_date)
        safe_end = _optional_date(end_date)
        where_sql, where_params = self._technical_where_clause(
            symbol=normalized,
            limit=limit,
            start_date=safe_start,
            end_date=safe_end,
        )

        with self.connect() as conn:
            record = conn.execute(
                f"""
                SELECT symbol, start_date, end_date, limit_value, history_count, history_last_time, payload_json, source, updated_at
                FROM technical_cache
                WHERE {where_sql}
                LIMIT 1
                """,
                where_params,
            ).fetchone()

        if record is None:
            return None, None

        updated_at = record[8]
        if updated_at.tzinfo is None:
            updated_at = updated_at.replace(tzinfo=timezone.utc)
        row = TechnicalCacheRow(
            symbol=record[0],
            start_date=record[1],
            end_date=record[2],
            limit_value=int(record[3]),
            history_count=int(record[4]),
            history_last_time=record[5],
            payload_json=record[6],
            source=record[7],
            updated_at=updated_at,
        )
        payload = json.loads(row.payload_json)
        return row, payload if isinstance(payload, dict) else {}

    @staticmethod
    def _table_columns(conn: duckdb.DuckDBPyConnection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
        return {str(row[1]) for row in rows}

    @staticmethod
    def _duckdb_type_for_series(series: pd.Series) -> str:
        if pd.api.types.is_bool_dtype(series):
            return "BOOLEAN"
        if pd.api.types.is_integer_dtype(series):
            return "BIGINT"
        if pd.api.types.is_float_dtype(series):
            return "DOUBLE"
        if pd.api.types.is_datetime64_any_dtype(series):
            return "TIMESTAMP"
        return "VARCHAR"

    @staticmethod
    def _prepare_market_features(dataset: pd.DataFrame, run_id: str) -> pd.DataFrame:
        if dataset.empty:
            return pd.DataFrame()
        if "symbol" not in dataset.columns or "data_date" not in dataset.columns:
            raise ValueError("market feature dataset requires symbol and data_date columns")

        frame = dataset.copy()
        frame["symbol"] = frame["symbol"].astype(str).str.upper()
        frame["data_date"] = pd.to_datetime(frame["data_date"], errors="coerce").dt.date
        frame = frame.dropna(subset=["symbol", "data_date"])
        frame = frame.drop_duplicates(["symbol", "data_date"], keep="last")
        frame["run_id"] = run_id
        frame["loaded_at"] = datetime.now(timezone.utc).replace(tzinfo=None)
        return frame

    def _ensure_market_feature_columns(self, conn: duckdb.DuckDBPyConnection, frame: pd.DataFrame) -> None:
        existing = self._table_columns(conn, "market_features_daily")
        for column in frame.columns:
            if column in existing:
                continue
            col_type = self._duckdb_type_for_series(frame[column])
            escaped = column.replace('"', '""')
            conn.execute(f'ALTER TABLE market_features_daily ADD COLUMN "{escaped}" {col_type}')
            existing.add(column)

    def upsert_market_features(self, dataset: pd.DataFrame, run_id: str, source_path: str | None = None) -> int:
        frame = self._prepare_market_features(dataset, run_id)
        if frame.empty:
            return 0

        with self.connect() as conn:
            self._ensure_market_feature_columns(conn, frame)
            conn.register("incoming_market_features", frame)
            conn.execute("BEGIN TRANSACTION")
            try:
                conn.execute(
                    """
                    DELETE FROM market_features_daily AS target
                    USING incoming_market_features AS incoming
                    WHERE target.symbol = incoming.symbol
                      AND target.data_date = incoming.data_date
                    """
                )
                columns = list(frame.columns)
                quoted = ", ".join(f'"{column.replace(chr(34), chr(34) + chr(34))}"' for column in columns)
                conn.execute(
                    f"""
                    INSERT INTO market_features_daily ({quoted})
                    SELECT {quoted}
                    FROM incoming_market_features
                    """
                )
                conn.execute("DELETE FROM market_feature_runs WHERE run_id = ?", [run_id])
                conn.execute(
                    """
                    INSERT INTO market_feature_runs
                        (run_id, row_count, symbol_count, min_date, max_date, source_path, loaded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        run_id,
                        int(len(frame)),
                        int(frame["symbol"].nunique()),
                        frame["data_date"].min(),
                        frame["data_date"].max(),
                        source_path,
                        frame["loaded_at"].iloc[0],
                    ],
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
            finally:
                conn.unregister("incoming_market_features")
        return int(len(frame))

    def load_market_features(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        columns: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.connect() as conn:
            requested = columns or ["*"]
            if requested == ["*"]:
                select_sql = "*"
            else:
                available = self._table_columns(conn, "market_features_daily")
                missing = [column for column in requested if column not in available]
                if missing:
                    raise ValueError(f"Unknown market feature columns: {missing}")
                select_sql = ", ".join(f'"{column.replace(chr(34), chr(34) + chr(34))}"' for column in requested)

            where = []
            params: list[Any] = []
            if symbols:
                normalized = [symbol.strip().upper() for symbol in symbols]
                placeholders = ", ".join("?" for _ in normalized)
                where.append(f"symbol IN ({placeholders})")
                params.extend(normalized)
            if start_date:
                where.append("data_date >= ?")
                params.append(start_date)
            if end_date:
                where.append("data_date <= ?")
                params.append(end_date)

            query = f"SELECT {select_sql} FROM market_features_daily"
            if where:
                query += " WHERE " + " AND ".join(where)
            query += " ORDER BY symbol, data_date"
            if limit is not None:
                query += " LIMIT ?"
                params.append(max(limit, 1))

            result = conn.execute(query, params)
            names = [item[0] for item in result.description]
            rows = result.fetchall()

        output = []
        for row in rows:
            item = {}
            for key, value in zip(names, row):
                item[key] = value.isoformat() if isinstance(value, date) else value
            output.append(item)
        return output

    def create_ai_analysis_run(
        self,
        symbol: str,
        analysis_date: date,
        horizon_days: int,
        model_version: str,
        prompt_version: str,
        context_hash: str,
        request_hash: str,
        market_feature_run_id: str | None,
        current_price: float | None,
        status: str,
    ) -> str:
        analysis_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_analysis_runs
                    (analysis_id, symbol, analysis_date, horizon_days, model_version, prompt_version,
                     context_hash, request_hash, market_feature_run_id, current_price, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    analysis_id,
                    symbol.strip().upper(),
                    analysis_date,
                    int(horizon_days),
                    model_version,
                    prompt_version,
                    context_hash,
                    request_hash,
                    market_feature_run_id,
                    current_price,
                    status,
                    now,
                ],
            )
        return analysis_id

    def save_ai_analysis_payload(
        self,
        analysis_id: str,
        request_context: dict[str, Any],
        prompt_text: str,
        kaggle_response: dict[str, Any] | None,
        raw_output: str | None,
        normalized_output: dict[str, Any] | None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute("DELETE FROM ai_analysis_payloads WHERE analysis_id = ?", [analysis_id])
            conn.execute(
                """
                INSERT INTO ai_analysis_payloads
                    (analysis_id, request_context_json, prompt_text, kaggle_response_json,
                     raw_output, normalized_output_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    analysis_id,
                    _json_dumps(request_context),
                    prompt_text,
                    _json_dumps(kaggle_response or {}),
                    raw_output,
                    _json_dumps(normalized_output or {}),
                    now,
                ],
            )

    def complete_ai_analysis_run(
        self,
        analysis_id: str,
        status: str,
        decision: str | None = None,
        confidence: float | None = None,
        reasoning: str | None = None,
        key_factors: list[str] | None = None,
        response_hash: str | None = None,
        error_message: str | None = None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ai_analysis_runs
                SET status = ?,
                    decision = ?,
                    confidence = ?,
                    reasoning = ?,
                    key_factors_json = ?,
                    response_hash = ?,
                    error_message = ?,
                    completed_at = ?
                WHERE analysis_id = ?
                """,
                [
                    status,
                    decision,
                    confidence,
                    reasoning,
                    _json_dumps(key_factors or []),
                    response_hash,
                    error_message,
                    now,
                    analysis_id,
                ],
            )

    def upsert_ai_prediction_outcome(
        self,
        analysis_id: str,
        horizon_days: int,
        entry_price: float | None,
        exit_date: date | None,
        exit_price: float | None,
        future_return_pct: float | None,
        actual_direction: str | None,
        is_correct: bool | None,
    ) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute(
                "DELETE FROM ai_prediction_outcomes WHERE analysis_id = ? AND horizon_days = ?",
                [analysis_id, int(horizon_days)],
            )
            conn.execute(
                """
                INSERT INTO ai_prediction_outcomes
                    (analysis_id, horizon_days, entry_price, exit_date, exit_price,
                     future_return_pct, actual_direction, is_correct, evaluated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    analysis_id,
                    int(horizon_days),
                    entry_price,
                    exit_date,
                    exit_price,
                    future_return_pct,
                    actual_direction,
                    is_correct,
                    now,
                ],
            )

    def load_ai_analysis_payload(self, analysis_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT request_context_json, prompt_text, kaggle_response_json, raw_output, normalized_output_json
                FROM ai_analysis_payloads
                WHERE analysis_id = ?
                """,
                [analysis_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "request_context": json.loads(row[0]),
            "prompt_text": row[1],
            "kaggle_response": json.loads(row[2] or "{}"),
            "raw_output": row[3] or "",
            "normalized_output": json.loads(row[4] or "{}"),
        }

    def load_ai_analysis_run(self, analysis_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT analysis_id, symbol, analysis_date, horizon_days, model_version, prompt_version,
                       context_hash, request_hash, response_hash, market_feature_run_id, current_price,
                       decision, confidence, reasoning, key_factors_json, status, error_message,
                       created_at, completed_at
                FROM ai_analysis_runs
                WHERE analysis_id = ?
                """,
                [analysis_id],
            ).fetchone()
            outcome_rows = conn.execute(
                """
                SELECT horizon_days, entry_price, exit_date, exit_price, future_return_pct, actual_direction, is_correct
                FROM ai_prediction_outcomes
                WHERE analysis_id = ?
                ORDER BY horizon_days
                """,
                [analysis_id],
            ).fetchall()
        if row is None:
            return None
        return {
            "analysis_id": row[0],
            "symbol": row[1],
            "analysis_date": row[2].isoformat(),
            "horizon_days": int(row[3]),
            "model_version": row[4],
            "prompt_version": row[5],
            "context_hash": row[6],
            "request_hash": row[7],
            "response_hash": row[8],
            "market_feature_run_id": row[9],
            "current_price": row[10],
            "decision": row[11],
            "confidence": row[12],
            "reasoning": row[13],
            "key_factors": json.loads(row[14] or "[]"),
            "status": row[15],
            "error_message": row[16],
            "created_at": row[17].isoformat() if row[17] else None,
            "completed_at": row[18].isoformat() if row[18] else None,
            "outcomes": [
                {
                    "horizon_days": int(item[0]),
                    "entry_price": item[1],
                    "exit_date": item[2].isoformat() if item[2] else None,
                    "exit_price": item[3],
                    "future_return_pct": item[4],
                    "actual_direction": item[5],
                    "is_correct": item[6],
                }
                for item in outcome_rows
            ],
        }

    def _calculate_prediction_outcome(
        self,
        conn: duckdb.DuckDBPyConnection,
        *,
        analysis_id: str,
        symbol: str,
        analysis_date: date,
        horizon_days: int,
        current_price: float | None,
        decision: str | None,
    ) -> dict[str, Any] | None:
        entry_price = current_price
        if entry_price is None or entry_price <= 0:
            entry_row = conn.execute(
                """
                SELECT close
                FROM daily_ohlcv
                WHERE symbol = ? AND date <= ?
                ORDER BY date DESC
                LIMIT 1
                """,
                [symbol, analysis_date],
            ).fetchone()
            entry_price = float(entry_row[0]) if entry_row else None

        if entry_price is None or entry_price <= 0:
            return None

        exit_row = conn.execute(
            """
            SELECT date, close
            FROM daily_ohlcv
            WHERE symbol = ? AND date > ?
            ORDER BY date ASC
            LIMIT 1 OFFSET ?
            """,
            [symbol, analysis_date, int(horizon_days) - 1],
        ).fetchone()
        if exit_row is None:
            return None

        exit_date = exit_row[0]
        exit_price = float(exit_row[1])
        future_return_pct = round(((exit_price - float(entry_price)) / float(entry_price)) * 100, 6)
        is_correct = _prediction_is_correct(decision, future_return_pct)
        actual_direction = _actual_direction(future_return_pct)
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        conn.execute(
            "DELETE FROM ai_prediction_outcomes WHERE analysis_id = ? AND horizon_days = ?",
            [analysis_id, int(horizon_days)],
        )
        conn.execute(
            """
            INSERT INTO ai_prediction_outcomes
                (analysis_id, horizon_days, entry_price, exit_date, exit_price,
                 future_return_pct, actual_direction, is_correct, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                analysis_id,
                int(horizon_days),
                float(entry_price),
                exit_date,
                exit_price,
                future_return_pct,
                actual_direction,
                is_correct,
                now,
            ],
        )

        return {
            "horizon_days": int(horizon_days),
            "entry_price": float(entry_price),
            "exit_date": exit_date.isoformat() if exit_date else None,
            "exit_price": exit_price,
            "future_return_pct": future_return_pct,
            "actual_direction": actual_direction,
            "is_correct": is_correct,
        }

    def load_ai_analysis_history(self, symbol: str, limit: int = 24) -> list[dict[str, Any]]:
        normalized = symbol.strip().upper()
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT analysis_id, symbol, analysis_date, horizon_days, model_version, prompt_version,
                       context_hash, request_hash, response_hash, market_feature_run_id, current_price,
                       decision, confidence, reasoning, key_factors_json, status, error_message,
                       created_at, completed_at
                FROM ai_analysis_runs
                WHERE symbol = ? AND status = 'success'
                ORDER BY completed_at DESC NULLS LAST, created_at DESC
                LIMIT ?
                """,
                [normalized, max(int(limit), 1)],
            ).fetchall()

            output: list[dict[str, Any]] = []
            for row in rows:
                outcome_rows = conn.execute(
                    """
                    SELECT horizon_days, entry_price, exit_date, exit_price, future_return_pct, actual_direction, is_correct
                    FROM ai_prediction_outcomes
                    WHERE analysis_id = ?
                    ORDER BY horizon_days
                    """,
                    [row[0]],
                ).fetchall()
                payload_row = conn.execute(
                    """
                    SELECT raw_output, normalized_output_json
                    FROM ai_analysis_payloads
                    WHERE analysis_id = ?
                    """,
                    [row[0]],
                ).fetchone()
                outcomes = [
                    {
                        "horizon_days": int(item[0]),
                        "entry_price": item[1],
                        "exit_date": item[2].isoformat() if item[2] else None,
                        "exit_price": item[3],
                        "future_return_pct": item[4],
                        "actual_direction": item[5],
                        "is_correct": item[6],
                    }
                    for item in outcome_rows
                ]
                existing_horizons = {item["horizon_days"] for item in outcomes}
                for horizon_days in (5, 7, 10):
                    if horizon_days in existing_horizons:
                        continue
                    outcome = self._calculate_prediction_outcome(
                        conn,
                        analysis_id=row[0],
                        symbol=row[1],
                        analysis_date=row[2],
                        horizon_days=horizon_days,
                        current_price=row[10],
                        decision=row[11],
                    )
                    if outcome is not None:
                        outcomes.append(outcome)

                outcomes.sort(key=lambda item: item["horizon_days"])
                output.append(
                    {
                        "analysis_id": row[0],
                        "symbol": row[1],
                        "analysis_date": row[2].isoformat() if row[2] else None,
                        "horizon_days": int(row[3]),
                        "model_version": row[4],
                        "prompt_version": row[5],
                        "context_hash": row[6],
                        "request_hash": row[7],
                        "response_hash": row[8],
                        "market_feature_run_id": row[9],
                        "current_price": row[10],
                        "decision": row[11],
                        "confidence": row[12],
                        "reasoning": row[13],
                        "key_factors": json.loads(row[14] or "[]"),
                        "status": row[15],
                        "error_message": row[16],
                        "created_at": row[17].isoformat() if row[17] else None,
                        "completed_at": row[18].isoformat() if row[18] else None,
                        "raw_output": payload_row[0] if payload_row else "",
                        "normalized_output": json.loads(payload_row[1] or "{}") if payload_row else {},
                        "outcomes": outcomes,
                    }
                )
        return output

    def create_ai_generation_job(
        self,
        *,
        symbol: str,
        user_id: int | None,
        force: bool,
        status: str = "queued",
    ) -> str:
        job_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_generation_jobs
                    (job_id, symbol, user_id, force, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [job_id, symbol.strip().upper(), user_id, bool(force), status, now],
            )
        return job_id

    def update_ai_generation_job(
        self,
        job_id: str,
        *,
        status: str,
        analysis_id: str | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE ai_generation_jobs
                SET status = ?,
                    analysis_id = COALESCE(?, analysis_id),
                    result_json = COALESCE(?, result_json),
                    error_message = ?,
                    started_at = COALESCE(?, started_at),
                    completed_at = COALESCE(?, completed_at)
                WHERE job_id = ?
                """,
                [
                    status,
                    analysis_id,
                    _json_dumps(result_json) if result_json is not None else None,
                    error_message,
                    started_at,
                    completed_at,
                    job_id,
                ],
            )

    def load_ai_generation_job(self, job_id: str) -> dict[str, Any] | None:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT job_id, symbol, user_id, force, status, analysis_id, result_json,
                       error_message, created_at, started_at, completed_at
                FROM ai_generation_jobs
                WHERE job_id = ?
                """,
                [job_id],
            ).fetchone()
        if row is None:
            return None
        return {
            "job_id": row[0],
            "symbol": row[1],
            "user_id": row[2],
            "force": bool(row[3]),
            "status": row[4],
            "analysis_id": row[5],
            "result": json.loads(row[6] or "{}"),
            "error_message": row[7],
            "created_at": row[8].isoformat() if row[8] else None,
            "started_at": row[9].isoformat() if row[9] else None,
            "completed_at": row[10].isoformat() if row[10] else None,
        }

    def load_ai_jobs_by_status(self, status: str) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT job_id
                FROM ai_generation_jobs
                WHERE status = ?
                ORDER BY created_at
                """,
                [status],
            ).fetchall()

        jobs: list[dict[str, Any]] = []
        for (job_id,) in rows:
            job = self.load_ai_generation_job(str(job_id))
            if job is not None:
                jobs.append(job)
        return jobs


class LazyMarketDuckDB:
    def __init__(self):
        self._repo: MarketDuckDB | None = None

    def _get_repo(self) -> MarketDuckDB:
        if self._repo is None:
            self._repo = MarketDuckDB()
        return self._repo

    def upsert_daily_rows(self, symbol: str, rows: Iterable[dict[str, Any]]) -> int:
        return self._get_repo().upsert_daily_rows(symbol, rows)

    def load_history(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        limit: int = 365,
    ) -> list[dict[str, Any]]:
        return self._get_repo().load_history(symbol, start_date=start_date, end_date=end_date, limit=limit)

    def upsert_technical_cache(
        self,
        symbol: str,
        start_date: date | None,
        end_date: date | None,
        limit: int,
        history_count: int,
        history_last_time: str | None,
        payload: dict[str, Any],
        source: str = "duckdb",
    ) -> str:
        return self._get_repo().upsert_technical_cache(
            symbol,
            start_date,
            end_date,
            limit,
            history_count,
            history_last_time,
            payload,
            source,
        )

    def load_technical_cache(
        self,
        symbol: str,
        start_date: date | None,
        end_date: date | None,
        limit: int,
    ) -> tuple[TechnicalCacheRow | None, dict[str, Any] | None]:
        return self._get_repo().load_technical_cache(symbol, start_date, end_date, limit)

    def upsert_market_features(self, dataset: pd.DataFrame, run_id: str, source_path: str | None = None) -> int:
        return self._get_repo().upsert_market_features(dataset, run_id, source_path=source_path)

    def load_market_features(
        self,
        symbols: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        columns: list[str] | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        return self._get_repo().load_market_features(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            columns=columns,
            limit=limit,
        )

    def create_ai_analysis_run(
        self,
        symbol: str,
        analysis_date: date,
        horizon_days: int,
        model_version: str,
        prompt_version: str,
        context_hash: str,
        request_hash: str,
        market_feature_run_id: str | None,
        current_price: float | None,
        status: str,
    ) -> str:
        return self._get_repo().create_ai_analysis_run(
            symbol=symbol,
            analysis_date=analysis_date,
            horizon_days=horizon_days,
            model_version=model_version,
            prompt_version=prompt_version,
            context_hash=context_hash,
            request_hash=request_hash,
            market_feature_run_id=market_feature_run_id,
            current_price=current_price,
            status=status,
        )

    def save_ai_analysis_payload(
        self,
        analysis_id: str,
        request_context: dict[str, Any],
        prompt_text: str,
        kaggle_response: dict[str, Any] | None,
        raw_output: str | None,
        normalized_output: dict[str, Any] | None,
    ) -> None:
        self._get_repo().save_ai_analysis_payload(
            analysis_id=analysis_id,
            request_context=request_context,
            prompt_text=prompt_text,
            kaggle_response=kaggle_response,
            raw_output=raw_output,
            normalized_output=normalized_output,
        )

    def complete_ai_analysis_run(
        self,
        analysis_id: str,
        status: str,
        decision: str | None = None,
        confidence: float | None = None,
        reasoning: str | None = None,
        key_factors: list[str] | None = None,
        response_hash: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self._get_repo().complete_ai_analysis_run(
            analysis_id=analysis_id,
            status=status,
            decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            key_factors=key_factors,
            response_hash=response_hash,
            error_message=error_message,
        )

    def upsert_ai_prediction_outcome(
        self,
        analysis_id: str,
        horizon_days: int,
        entry_price: float | None,
        exit_date: date | None,
        exit_price: float | None,
        future_return_pct: float | None,
        actual_direction: str | None,
        is_correct: bool | None,
    ) -> None:
        self._get_repo().upsert_ai_prediction_outcome(
            analysis_id=analysis_id,
            horizon_days=horizon_days,
            entry_price=entry_price,
            exit_date=exit_date,
            exit_price=exit_price,
            future_return_pct=future_return_pct,
            actual_direction=actual_direction,
            is_correct=is_correct,
        )

    def load_ai_analysis_payload(self, analysis_id: str) -> dict[str, Any] | None:
        return self._get_repo().load_ai_analysis_payload(analysis_id)

    def load_ai_analysis_run(self, analysis_id: str) -> dict[str, Any] | None:
        return self._get_repo().load_ai_analysis_run(analysis_id)

    def load_ai_analysis_history(self, symbol: str, limit: int = 24) -> list[dict[str, Any]]:
        return self._get_repo().load_ai_analysis_history(symbol, limit=limit)

    def create_ai_generation_job(
        self,
        *,
        symbol: str,
        user_id: int | None,
        force: bool,
        status: str = "queued",
    ) -> str:
        return self._get_repo().create_ai_generation_job(
            symbol=symbol,
            user_id=user_id,
            force=force,
            status=status,
        )

    def update_ai_generation_job(
        self,
        job_id: str,
        *,
        status: str,
        analysis_id: str | None = None,
        result_json: dict[str, Any] | None = None,
        error_message: str | None = None,
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
    ) -> None:
        self._get_repo().update_ai_generation_job(
            job_id,
            status=status,
            analysis_id=analysis_id,
            result_json=result_json,
            error_message=error_message,
            started_at=started_at,
            completed_at=completed_at,
        )

    def load_ai_generation_job(self, job_id: str) -> dict[str, Any] | None:
        return self._get_repo().load_ai_generation_job(job_id)

    def load_ai_jobs_by_status(self, status: str) -> list[dict[str, Any]]:
        return self._get_repo().load_ai_jobs_by_status(status)


market_repo = LazyMarketDuckDB()
