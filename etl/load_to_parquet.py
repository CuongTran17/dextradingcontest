"""Processed parquet writer with symbol partitions and metadata."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pandas as pd

from etl.config import EtlConfig
from etl.logging_setup import get_logger
from etl.transform.transform_validate import build_quality_contract_report

log = get_logger(__name__)


def _file_checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _save_gold_market_features(dataset: pd.DataFrame, cfg: EtlConfig) -> dict[str, str]:
    """Write canonical gold-layer market features without removing legacy outputs."""
    gold_table_dir = cfg.gold_dir / "market_features"
    run_dir = gold_table_dir / f"run_id={cfg.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    run_data_path = run_dir / "data.parquet"
    dataset.to_parquet(run_data_path, index=False)

    latest_path = gold_table_dir / "latest.parquet"
    dataset.to_parquet(latest_path, index=False)

    partition_root = gold_table_dir / "by_symbol"
    if "symbol" in dataset.columns:
        for symbol, frame in dataset.groupby("symbol"):
            symbol_dir = partition_root / f"symbol={str(symbol).upper()}"
            symbol_dir.mkdir(parents=True, exist_ok=True)
            frame.sort_values("data_date").to_parquet(symbol_dir / "latest.parquet", index=False)

    return {
        "gold_market_features_run": str(run_data_path),
        "gold_market_features_latest": str(latest_path),
        "gold_market_features_by_symbol": str(partition_root),
    }


def _save_silver_market_data(dataset: pd.DataFrame, cfg: EtlConfig) -> dict[str, str]:
    """Write normalized market data to the additive silver layer."""
    silver_table_dir = cfg.silver_dir / "market_data"
    run_dir = silver_table_dir / f"run_id={cfg.run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)

    run_data_path = run_dir / "data.parquet"
    dataset.to_parquet(run_data_path, index=False)

    latest_path = silver_table_dir / "latest.parquet"
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_parquet(latest_path, index=False)

    partition_root = silver_table_dir / "by_symbol"
    if "symbol" in dataset.columns:
        for symbol, frame in dataset.groupby("symbol"):
            symbol_dir = partition_root / f"symbol={str(symbol).upper()}"
            symbol_dir.mkdir(parents=True, exist_ok=True)
            frame.sort_values("data_date").to_parquet(symbol_dir / "latest.parquet", index=False)

    return {
        "silver_market_data_run": str(run_data_path),
        "silver_market_data_latest": str(latest_path),
        "silver_market_data_by_symbol": str(partition_root),
    }


def save_processed_parquet(dataset: pd.DataFrame, cfg: EtlConfig) -> Path:
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.processed_dir / f"market_data_{cfg.run_id}.parquet"
    dataset.to_parquet(out, index=False)

    by_symbol_dir = cfg.processed_dir / "by_symbol"
    if "symbol" in dataset.columns:
        for symbol, frame in dataset.groupby("symbol"):
            symbol_dir = by_symbol_dir / str(symbol).upper()
            symbol_dir.mkdir(parents=True, exist_ok=True)
            frame.to_parquet(symbol_dir / "latest.parquet", index=False)

    silver_artifacts = _save_silver_market_data(dataset, cfg)
    gold_artifacts = _save_gold_market_features(dataset, cfg)
    quality_summary = build_quality_contract_report(dataset, expected_symbols=list(cfg.symbols))

    metadata = {
        "run_id": cfg.run_id,
        "row_count": int(len(dataset)),
        "columns": list(dataset.columns),
        "date_range": {
            "min": str(dataset["data_date"].min()) if "data_date" in dataset.columns and not dataset.empty else None,
            "max": str(dataset["data_date"].max()) if "data_date" in dataset.columns and not dataset.empty else None,
        },
        "symbols": sorted(dataset["symbol"].dropna().unique().tolist()) if "symbol" in dataset.columns else [],
        "schema_version": 2,
        "quality_summary": quality_summary,
        "checksum_sha256": _file_checksum(out),
        "lake_layout_version": 1,
        "layers": {
            "legacy_processed": str(out),
            **silver_artifacts,
            **gold_artifacts,
        },
    }
    meta_path = cfg.processed_dir / f"market_data_{cfg.run_id}.meta.json"
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    log.info("Saved processed parquet %s rows=%d metadata=%s", out, len(dataset), meta_path)
    return out


def cleanup_old_snapshots(cfg: EtlConfig, keep: int = 5) -> int:
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(cfg.processed_dir.glob("market_data_*.parquet"), key=lambda p: p.stat().st_mtime, reverse=True)
    stale = files[max(keep, 0):]
    deleted = 0
    for parquet_path in stale:
        stem = parquet_path.with_suffix("")
        meta_path = stem.with_suffix(".meta.json")
        csv_path = stem.with_suffix(".csv")
        run_id = parquet_path.stem.replace("market_data_", "", 1)
        gold_run_dir = cfg.gold_dir / "market_features" / f"run_id={run_id}"
        for path in (parquet_path, meta_path, csv_path):
            if path.exists():
                path.unlink()
                deleted += 1
        if gold_run_dir.exists():
            shutil.rmtree(gold_run_dir)
            deleted += 1
    if deleted:
        log.info("Cleaned up %d old processed snapshot files", deleted)
    return deleted
