"""Load processed/raw ETL outputs into MySQL cache tables."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from etl.config import FUNDAMENTAL_REPORT_TYPES, EtlConfig
from etl.load_to_duckdb import load_daily_price_to_duckdb, load_eod_rows_to_duckdb, load_technical_cache_to_duckdb
from etl.processed_files import latest_processed_parquet

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
log = logging.getLogger(__name__)


def get_engine():
    env_path = Path("backend_v2/.env")
    if env_path.exists():
        load_dotenv(env_path)

    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        mysql_url = "mysql+mysqlconnector://root:123456789@localhost/vnstock_data"
        log.warning("MYSQL_URL not found in %s, using default: %s", env_path, mysql_url)
    return create_engine(mysql_url)


def _clean_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _clean_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_clean_json(item) for item in value]
    if isinstance(value, tuple):
        return [_clean_json(item) for item in value]
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


def _json_dumps(payload: Any) -> str:
    return json.dumps(_clean_json(payload), ensure_ascii=False, default=str)


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        log.warning("Invalid JSON skipped: %s", path)
        return None


def _raw_json_path(cfg: EtlConfig, category: str, symbol: str) -> Path:
    return cfg.raw_dir / category / symbol.upper() / f"{cfg.run_id}.json"


def _latest_processed_parquet(cfg: EtlConfig | None = None) -> Path | None:
    processed_dir = cfg.processed_dir if cfg else Path("lake/processed")
    return latest_processed_parquet(processed_dir)


def load_daily_price(cfg: EtlConfig | None = None, dataset: pd.DataFrame | None = None) -> int:
    log.warning("load_daily_price() now writes daily OHLCV to DuckDB, not MySQL.")
    return load_daily_price_to_duckdb(cfg=cfg, dataset=dataset)


def load_eod_rows(rows: list[dict[str, Any]]) -> int:
    log.warning("load_eod_rows() now writes aggregated EOD rows to DuckDB, not MySQL.")
    return load_eod_rows_to_duckdb(rows)


def load_overview_cache(cfg: EtlConfig) -> int:
    engine = get_engine()
    records = []
    for symbol in cfg.symbols:
        payload = _read_json(_raw_json_path(cfg, "overview", symbol))
        if isinstance(payload, list) and payload:
            payload = payload[0]
        if isinstance(payload, dict):
            records.append({"symbol": symbol.upper(), "payload_json": _json_dumps(payload), "source": "etl-vnstock"})
    if not records:
        return 0
    sql = text(
        """
        INSERT INTO company_overview_cache (symbol, payload_json, source, updated_at)
        VALUES (:symbol, :payload_json, :source, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE payload_json=VALUES(payload_json), source=VALUES(source), updated_at=CURRENT_TIMESTAMP
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, records)
    log.info("Loaded %d overview cache rows", len(records))
    return len(records)


def load_financial_cache(cfg: EtlConfig) -> int:
    engine = get_engine()
    records = []
    for symbol in cfg.symbols:
        for report_type in FUNDAMENTAL_REPORT_TYPES:
            if report_type == "ratios":
                payload = _read_json(_raw_json_path(cfg, "ratio_summary", symbol))
                source = "etl-vnstock-ratio-summary"
            else:
                payload = _read_json(_raw_json_path(cfg, f"fundamental/{report_type}", symbol))
                source = f"etl-vnstock-{report_type}"
            if isinstance(payload, list) and payload:
                records.append(
                    {
                        "symbol": symbol.upper(),
                        "report_type": report_type,
                        "row_count": len(payload),
                        "payload_json": _json_dumps(payload),
                        "source": source,
                    }
                )
    if not records:
        return 0
    sql = text(
        """
        INSERT INTO financial_report_cache (symbol, report_type, row_count, payload_json, source, updated_at)
        VALUES (:symbol, :report_type, :row_count, :payload_json, :source, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            row_count=VALUES(row_count),
            payload_json=VALUES(payload_json),
            source=VALUES(source),
            updated_at=CURRENT_TIMESTAMP
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, records)
    log.info("Loaded %d financial cache rows", len(records))
    return len(records)


def _load_symbol_list_cache(cfg: EtlConfig, category: str, table_name: str, source: str) -> int:
    engine = get_engine()
    records = []
    for symbol in cfg.symbols:
        payload = _read_json(_raw_json_path(cfg, category, symbol))
        if isinstance(payload, list):
            records.append(
                {
                    "symbol": symbol.upper(),
                    "item_count": len(payload),
                    "payload_json": _json_dumps(payload),
                    "source": source,
                }
            )
    if not records:
        return 0
    sql = text(
        f"""
        INSERT INTO {table_name} (symbol, item_count, payload_json, source, updated_at)
        VALUES (:symbol, :item_count, :payload_json, :source, CURRENT_TIMESTAMP)
        ON DUPLICATE KEY UPDATE
            item_count=VALUES(item_count),
            payload_json=VALUES(payload_json),
            source=VALUES(source),
            updated_at=CURRENT_TIMESTAMP
        """
    )
    with engine.begin() as conn:
        conn.execute(sql, records)
    log.info("Loaded %d %s rows", len(records), table_name)
    return len(records)


def load_news_cache(cfg: EtlConfig) -> int:
    return _load_symbol_list_cache(cfg, "news", "news_cache", "etl-vnstock-news")


def load_events_cache(cfg: EtlConfig) -> int:
    return _load_symbol_list_cache(cfg, "events", "events_cache", "etl-vnstock-events")


def load_technical_cache(cfg: EtlConfig, dataset: pd.DataFrame | None = None, limit: int = 365) -> int:
    log.warning("load_technical_cache() now writes technical cache to DuckDB, not MySQL.")
    return load_technical_cache_to_duckdb(cfg=cfg, dataset=dataset, limit=limit)


def load_all(cfg: EtlConfig, dataset: pd.DataFrame | None = None) -> dict[str, int]:
    if dataset is None:
        latest_file = _latest_processed_parquet(cfg)
        dataset = pd.read_parquet(latest_file) if latest_file else None
    results = {
        "overview": load_overview_cache(cfg),
        "financial": load_financial_cache(cfg),
        "news": load_news_cache(cfg),
        "events": load_events_cache(cfg),
    }
    log.info("MySQL cache load_all results: %s", results)
    return results


if __name__ == "__main__":
    load_daily_price()
