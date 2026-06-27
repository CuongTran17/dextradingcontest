"""Load processed OHLCV outputs into the DuckDB market warehouse."""
from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from backend_v2.src.database.market_duckdb import LazyMarketDuckDB, MarketDuckDB, market_repo
from backend_v2.src.services.technical_indicators import build_technical_payload
from etl.config import EtlConfig
from etl.processed_files import latest_processed_parquet

log = logging.getLogger(__name__)


def _latest_processed_parquet(cfg: EtlConfig | None = None) -> Path | None:
    processed_dir = cfg.processed_dir if cfg else Path("lake/processed")
    return latest_processed_parquet(processed_dir)


def load_daily_price_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            log.error("No parquet files found in processed dir")
            return 0
        dataset = pd.read_parquet(latest_file)

    ohlcv_cols = ["symbol", "data_date", "open_price", "high_price", "low_price", "close_price", "volume"]
    if not all(col in dataset.columns for col in ohlcv_cols):
        log.error("Missing required OHLCV columns in dataset")
        return 0

    frame = dataset[ohlcv_cols].copy()
    frame = frame.rename(
        columns={
            "data_date": "date",
            "open_price": "open",
            "high_price": "high",
            "low_price": "low",
            "close_price": "close",
        }
    )
    for col in ("open", "high", "low", "close"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
    frame["volume"] = pd.to_numeric(frame["volume"], errors="coerce").fillna(0).astype(int)

    total = 0
    normalized_symbols = frame["symbol"].astype(str).str.upper()
    for symbol, rows in frame.groupby(normalized_symbols):
        total += repo.upsert_daily_rows(str(symbol), rows.to_dict(orient="records"))
    log.info("Loaded %d daily OHLCV rows into DuckDB", total)
    return total


def load_eod_rows_to_duckdb(
    rows: list[dict[str, Any]],
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
) -> int:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        if symbol:
            grouped[symbol].append(row)

    total = 0
    for symbol, symbol_rows in grouped.items():
        total += repo.upsert_daily_rows(symbol, symbol_rows)
    log.info("Loaded %d aggregated EOD rows into DuckDB", total)
    return total


def _technical_payload_from_processed(symbol: str, frame: pd.DataFrame) -> dict[str, Any]:
    frame = frame.sort_values("data_date").reset_index(drop=True)
    return build_technical_payload(
        symbol,
        frame,
        time_col="data_date",
        open_col="open_price",
        high_col="high_price",
        low_col="low_price",
        close_col="close_price",
        volume_col="volume",
    )


def load_technical_cache_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
    limit: int = 365,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            return 0
        dataset = pd.read_parquet(latest_file)

    required_cols = ["symbol", "data_date", "open_price", "high_price", "low_price", "close_price", "volume"]
    if not all(col in dataset.columns for col in required_cols):
        log.error("Missing required technical cache columns in dataset")
        return 0

    total = 0
    for symbol, frame in dataset.groupby("symbol"):
        frame = frame.sort_values("data_date").tail(limit)
        if frame.empty:
            continue
        normalized = str(symbol).upper()
        payload = _technical_payload_from_processed(normalized, frame)
        repo.upsert_technical_cache(
            normalized,
            None,
            None,
            limit,
            len(frame),
            str(frame["data_date"].iloc[-1]),
            payload,
            "etl-processed",
        )
        total += 1
    log.info("Loaded %d technical cache rows into DuckDB", total)
    return total


def load_market_features_to_duckdb(
    cfg: EtlConfig | None = None,
    dataset: pd.DataFrame | None = None,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
    run_id: str | None = None,
    source_path: str | None = None,
) -> int:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        if not latest_file:
            log.error("No parquet files found in processed dir")
            return 0
        dataset = pd.read_parquet(latest_file)
        source_path = source_path or str(latest_file)

    resolved_run_id = run_id or (cfg.run_id if cfg else "manual")
    total = repo.upsert_market_features(dataset, run_id=resolved_run_id, source_path=source_path)
    log.info("Loaded %d market feature rows into DuckDB", total)
    return total
