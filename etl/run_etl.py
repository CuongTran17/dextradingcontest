"""Orchestrator — chạy Extract song song rồi Transform tuần tự.

Pipeline:
    1. setup_logging() + tạo lake/raw, lake/processed.
    2. Extract song song qua ThreadPoolExecutor:
         - listing (1 lần)
         - macro_index x 4 chỉ số
         - macro_interbank (1 lần)
         - per symbol: prices, overview, ratio_summary, news, events
       Mỗi job có tenacity retry riêng. Job thất bại -> log + đếm vào failed.
    3. Gate: nếu tỉ lệ mã lỗi > cfg.max_fail_ratio -> raise.
    4. Transform: đọc raw, tính indicator, ghép dataset sạch.
    5. Ghi ra cfg.output_file + copy snapshot vào lake/processed/.

CLI::

    python -m etl.run_etl --start-date 2025-04-01 --end-date 2026-04-01 \
        --symbols MBB,FPT,HPG --output market_data.csv
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pandas as pd
from dotenv import load_dotenv
from vnstock import change_api_key

from etl.config import DEFAULT_SYMBOLS, FUNDAMENTAL_REPORT_TYPES, MACRO_SYMBOLS, EtlConfig
from etl.extract.extract_company import (
    extract_events,
    extract_listing,
    extract_news,
    extract_overview,
    extract_ratio_summary,
)
from etl.extract.extract_fundamental import extract_fundamental
from etl.extract.extract_googlenews import extract_google_news
from etl.extract.extract_interbank import extract_interbank_rate
from etl.extract.extract_prices import extract_index_prices, extract_symbol_prices
from etl.load_to_duckdb import (
    load_daily_price_to_duckdb,
    load_eod_rows_to_duckdb,
    load_market_features_to_duckdb,
    load_technical_cache_to_duckdb,
)
from etl.manifest import EtlManifest, publish_latest_manifest
from etl.load_to_mysql import load_all as load_mysql_caches
from etl.load_to_parquet import cleanup_old_snapshots, save_processed_parquet
from etl.logging_setup import get_logger, setup_logging
from etl.processed_files import latest_processed_parquet
from etl.run_metadata import RunMetadata, complete_metadata, running_metadata, save_run_metadata
from etl.transform.transform_aggregate import aggregate_all_ticks_to_eod
from etl.backfill_dnse_ticks import backfill_dnse_ticks_for_session, backfill_latest_session_ticks
from etl.transform.build_dataset import build_full_dataset, validate_dataset
from etl.transform.transform_validate import enforce_publish_quality_gate
from backend_v2.src.services.etl_marker import write_last_etl_marker

log = get_logger(__name__)


def _latest_processed_parquet(cfg: EtlConfig) -> Path | None:
    return latest_processed_parquet(cfg.processed_dir, exclude_run_id=cfg.run_id)


def _resolve_incremental_cfg(cfg: EtlConfig) -> EtlConfig:
    if cfg.run_mode != "incremental":
        return cfg

    latest = _latest_processed_parquet(cfg)
    if latest is None:
        log.warning("Incremental mode requested but no previous snapshot was found; falling back to configured start date.")
        return cfg

    try:
        previous = pd.read_parquet(latest, columns=["data_date"])
        latest_date = pd.to_datetime(previous["data_date"], errors="coerce").dropna().max()
    except Exception as exc:
        log.warning("Could not inspect previous snapshot %s for incremental start: %s", latest, exc)
        return cfg

    if pd.isna(latest_date):
        return cfg

    resolved_start = latest_date.date() - timedelta(days=max(cfg.incremental_overlap_days, 0))
    if resolved_start > cfg.user_end:
        resolved_start = cfg.user_end
    if resolved_start != cfg.user_start:
        log.info(
            "Incremental start resolved from previous snapshot %s: %s -> %s",
            latest,
            cfg.user_start,
            resolved_start,
        )
    return replace(cfg, user_start=resolved_start)


def _merge_with_previous_snapshot(dataset: pd.DataFrame, cfg: EtlConfig) -> tuple[pd.DataFrame, Path | None]:
    if cfg.run_mode not in {"incremental", "backfill"} or not cfg.merge_with_latest:
        return dataset, None

    latest = _latest_processed_parquet(cfg)
    if latest is None:
        log.info("%s mode has no previous snapshot to merge.", cfg.run_mode)
        return dataset, None

    previous = pd.read_parquet(latest)
    combined = pd.concat([previous, dataset], ignore_index=True, sort=False)
    if {"symbol", "data_date"}.issubset(combined.columns):
        combined["symbol"] = combined["symbol"].astype(str).str.upper()
        combined["data_date"] = pd.to_datetime(combined["data_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        combined = combined.dropna(subset=["symbol", "data_date"])
        combined = combined.drop_duplicates(["symbol", "data_date"], keep="last")
        combined = combined.sort_values(["symbol", "data_date"]).reset_index(drop=True)
    log.info(
        "Merged %s rows from %s with %s new rows -> %s rows",
        len(previous),
        latest,
        len(dataset),
        len(combined),
    )
    return combined, latest


# ---------------------------------------------------------------------------
# Job scheduling helpers
# ---------------------------------------------------------------------------
def _submit(
    pool: ThreadPoolExecutor,
    label: str,
    func: Callable,
    *args,
) -> tuple[str, Future]:
    return label, pool.submit(func, *args)


def _extract_all(cfg: EtlConfig) -> dict[str, Exception]:
    """Chạy toàn bộ Extract song song. Trả về dict job_label -> exception."""
    errors: dict[str, Exception] = {}

    with ThreadPoolExecutor(max_workers=cfg.max_workers) as pool:
        jobs: list[tuple[str, Future]] = []

        # Global jobs
        jobs.append(_submit(pool, "listing", extract_listing, cfg))
        jobs.append(_submit(pool, "macro_interbank", extract_interbank_rate, cfg))
        for idx in MACRO_SYMBOLS:
            jobs.append(_submit(pool, f"macro_index:{idx}", extract_index_prices, idx, cfg))

        # Per-symbol jobs
        for symbol in cfg.symbols:
            jobs.append(_submit(pool, f"prices:{symbol}", extract_symbol_prices, symbol, cfg))
            jobs.append(_submit(pool, f"overview:{symbol}", extract_overview, symbol, cfg))
            jobs.append(_submit(pool, f"ratio:{symbol}", extract_ratio_summary, symbol, cfg))
            jobs.append(_submit(pool, f"news:{symbol}", extract_news, symbol, cfg))
            jobs.append(_submit(pool, f"events:{symbol}", extract_events, symbol, cfg))

            # BCTC / Fundamental — chạy song song nếu enable
            if cfg.enable_fundamental:
                for report_type in FUNDAMENTAL_REPORT_TYPES:
                    jobs.append(_submit(
                        pool,
                        f"fundamental/{report_type}:{symbol}",
                        extract_fundamental,
                        symbol, report_type, cfg,
                    ))

        label_by_future = {fut: label for label, fut in jobs}
        for fut in as_completed(label_by_future):
            label = label_by_future[fut]
            try:
                fut.result()
            except Exception as exc:  # đã retry 5 lần ở tenacity
                log.exception("Extract job failed: %s", label)
                errors[label] = exc

    # GoogleNews — chạy tuần tự (có sleep giữa các symbol để tránh Google block)
    if cfg.enable_google_news:
        log.info("GoogleNews extract starting (%d symbols, sequential)", len(cfg.symbols))
        for symbol in cfg.symbols:
            try:
                extract_google_news(symbol, cfg)
            except Exception as exc:
                log.warning("GoogleNews extract failed for %s: %s", symbol, exc)
                errors[f"google_news:{symbol}"] = exc

    return errors


def _check_failure_gate(errors: dict[str, Exception], cfg: EtlConfig) -> None:
    """Fail toàn bộ run nếu tỷ lệ mã bị lỗi PRICE > ngưỡng cho phép.

    Lỗi ở news/events/overview/ratio coi là "soft": không chặn run
    vì các cột đó có cơ chế fallback (NA hoặc NO_*_FALLBACK).
    """
    failed_symbols = {
        lbl.split(":", 1)[1]
        for lbl in errors
        if lbl.startswith("prices:")
    }
    ratio = len(failed_symbols) / max(len(cfg.symbols), 1)
    if ratio > cfg.max_fail_ratio:
        raise RuntimeError(
            f"Extract fail ratio {ratio:.1%} > {cfg.max_fail_ratio:.0%} "
            f"(failed: {sorted(failed_symbols)})"
        )
    if errors:
        log.warning("Extract finished with %d soft failures: %s", len(errors), sorted(errors.keys()))


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def _record_phase(metadata: RunMetadata, phase: str, started_at: float) -> None:
    metadata.phase_durations[phase] = round(time.perf_counter() - started_at, 3)


def _symbol_status_from_extract_errors(cfg: EtlConfig, errors: dict[str, Exception]) -> dict[str, str]:
    status = {symbol.upper(): "success" for symbol in cfg.symbols}
    for label in errors:
        if ":" not in label:
            continue
        kind, symbol = label.split(":", 1)
        symbol = symbol.upper()
        if symbol not in status:
            continue
        status[symbol] = "failed_price" if kind == "prices" else "partial_failure"
    return status


def _run_impl(cfg: EtlConfig, metadata: RunMetadata) -> Path:
    setup_logging(cfg.log_dir)
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)

    # Load vnstock API key
    env_path = Path("backend_v2/.env")
    if env_path.exists():
        load_dotenv(env_path)
    api_key = os.getenv("VNSTOCK_API_KEY")
    if api_key:
        try:
            changed = change_api_key(api_key)
            log.info("VNStock API key loaded (%s).", "updated" if changed else "active")
        except Exception as e:
            log.warning("Could not set VNStock API key: %s", e)

    log.info(
        "=== ETL RUN %s ===  symbols=%d  user_range=%s..%s  fetch_start=%s  text_mode=%s",
        cfg.run_id,
        len(cfg.symbols),
        cfg.user_start,
        cfg.user_end,
        cfg.fetch_start,
        cfg.text_mode,
    )

    # ---- EXTRACT ----------------------------------------------------------
    phase_started = time.perf_counter()
    errors = _extract_all(cfg)
    _record_phase(metadata, "extract", phase_started)
    metadata.extract_errors = {label: str(exc) for label, exc in errors.items()}
    metadata.symbol_status = _symbol_status_from_extract_errors(cfg, errors)
    save_run_metadata(metadata, cfg)
    _check_failure_gate(errors, cfg)

    # ---- TRANSFORM --------------------------------------------------------
    phase_started = time.perf_counter()
    log.info("Transform phase starting (%d symbols)", len(cfg.symbols))
    dataset = build_full_dataset(cfg.symbols, cfg)
    if dataset.empty:
        raise RuntimeError("No rows were generated after transform. Check raw layer.")
    quality_report = validate_dataset(dataset, expected_symbols=cfg.symbols)
    _record_phase(metadata, "transform", phase_started)
    metadata.quality_report = quality_report
    metadata.row_counts.update(
        {
            "delta_rows": int(len(dataset)),
            "delta_symbols": int(dataset["symbol"].nunique()) if "symbol" in dataset.columns else 0,
            "processed_rows": int(len(dataset)),
            "processed_symbols": int(dataset["symbol"].nunique()) if "symbol" in dataset.columns else 0,
        }
    )
    save_run_metadata(metadata, cfg)

    dataset, merged_from = _merge_with_previous_snapshot(dataset, cfg)
    if merged_from is not None:
        metadata.artifacts["merged_from_snapshot"] = str(merged_from)
        quality_report = validate_dataset(dataset, expected_symbols=cfg.symbols)
        metadata.quality_report = quality_report
        metadata.row_counts.update(
            {
                "processed_rows": int(len(dataset)),
                "processed_symbols": int(dataset["symbol"].nunique()) if "symbol" in dataset.columns else 0,
            }
        )
        save_run_metadata(metadata, cfg)

    quality_report = enforce_publish_quality_gate(dataset, expected_symbols=cfg.symbols)
    metadata.quality_report = quality_report
    save_run_metadata(metadata, cfg)

    # ---- LOAD -------------------------------------------------------------
    phase_started = time.perf_counter()
    cfg.output_file.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(
        cfg.output_file,
        index=False,
        encoding="utf-8-sig",
        float_format="%.6f",
    )

    # Keep root parquet for backward compatibility with older scripts.
    parquet_out = cfg.output_file.with_suffix(".parquet")
    dataset.to_parquet(parquet_out, index=False)
    metadata.artifacts["output_csv"] = str(cfg.output_file)
    metadata.artifacts["output_parquet"] = str(parquet_out)

    processed_parquet = save_processed_parquet(dataset, cfg)
    metadata.artifacts["processed_parquet"] = str(processed_parquet)
    metadata.artifacts["processed_metadata"] = str(cfg.processed_dir / f"market_data_{cfg.run_id}.meta.json")
    metadata.artifacts["gold_market_features"] = str(cfg.gold_dir / "market_features" / f"run_id={cfg.run_id}" / "data.parquet")
    metadata.artifacts["gold_market_features_latest"] = str(cfg.gold_dir / "market_features" / "latest.parquet")

    if cfg.enable_market_duckdb_load:
        load_daily_price_to_duckdb(cfg, dataset)
        load_technical_cache_to_duckdb(cfg, dataset)
        load_market_features_to_duckdb(cfg, dataset, run_id=cfg.run_id, source_path=str(processed_parquet))
        metadata.artifacts["duckdb_market_load"] = "enabled"
        metadata.artifacts["duckdb_technical_cache_load"] = "enabled"
        metadata.artifacts["duckdb_market_features_load"] = "enabled"
    else:
        metadata.artifacts["duckdb_market_load"] = "disabled"
        metadata.artifacts["duckdb_technical_cache_load"] = "disabled"
        metadata.artifacts["duckdb_market_features_load"] = "disabled"

    if cfg.enable_mysql_cache_load:
        load_mysql_caches(cfg, dataset)
        metadata.artifacts["mysql_cache_load"] = "enabled"
    else:
        metadata.artifacts["mysql_cache_load"] = "disabled"

    if cfg.enable_dnse_tick_backfill and cfg.tick_source in {"lake", "auto"}:
        phase_started = time.perf_counter()
        if cfg.dnse_tick_session_date is not None:
            backfill_result = backfill_dnse_ticks_for_session(
                cfg.symbols,
                cfg.dnse_tick_session_date,
                force=cfg.force_dnse_tick_backfill,
            )
        else:
            backfill_result = backfill_latest_session_ticks(
                cfg.symbols,
                force=cfg.force_dnse_tick_backfill,
            )
        _record_phase(metadata, "dnse_tick_backfill", phase_started)
        metadata.row_counts["dnse_tick_backfilled_symbols"] = len(backfill_result.backfilled)
        metadata.row_counts["dnse_tick_existing_symbols"] = len(backfill_result.skipped_existing)
        metadata.row_counts["dnse_tick_empty_symbols"] = len(backfill_result.empty_from_dnse)
        metadata.artifacts["dnse_tick_backfill_session_date"] = backfill_result.session_date.isoformat()
        if backfill_result.failed:
            metadata.extract_errors.update(
                {f"dnse_tick_backfill:{symbol}": error for symbol, error in backfill_result.failed.items()}
            )
        save_run_metadata(metadata, cfg)

    if cfg.enable_tick_eod:
        eod_rows = aggregate_all_ticks_to_eod(cfg.symbols, cfg, source=cfg.tick_source)
        load_eod_rows_to_duckdb(eod_rows)
        metadata.row_counts["tick_eod_rows"] = int(len(eod_rows))

    processed_metadata_path = cfg.processed_dir / f"market_data_{cfg.run_id}.meta.json"
    checksum_sha256 = ""
    try:
        processed_metadata = json.loads(processed_metadata_path.read_text(encoding="utf-8"))
        checksum_sha256 = str(processed_metadata.get("checksum_sha256") or "")
    except Exception as exc:
        log.warning("Could not read processed metadata checksum from %s: %s", processed_metadata_path, exc)

    manifest = EtlManifest(
        run_id=cfg.run_id,
        status="success",
        processed_path=str(processed_parquet),
        processed_metadata_path=str(processed_metadata_path),
        gold_market_features_path=str(cfg.gold_dir / "market_features" / f"run_id={cfg.run_id}" / "data.parquet"),
        gold_market_features_latest_path=str(cfg.gold_dir / "market_features" / "latest.parquet"),
        duckdb_path=str(cfg.lake_dir / "warehouse" / "market.duckdb"),
        row_count=int(len(dataset)),
        symbol_count=int(dataset["symbol"].nunique()) if "symbol" in dataset.columns else 0,
        symbols=sorted(dataset["symbol"].dropna().astype(str).str.upper().unique().tolist()) if "symbol" in dataset.columns else [],
        checksum_sha256=checksum_sha256,
        quality_status=str(quality_report.get("status") or "unknown"),
    )
    manifest_out = publish_latest_manifest(cfg.lake_dir, manifest)
    metadata.artifacts["latest_success_manifest"] = str(manifest_out)

    cleanup_old_snapshots(cfg, keep=5)
    _record_phase(metadata, "load", phase_started)
    save_run_metadata(metadata, cfg)

    log.info(
        "Done: %s & .parquet rows=%d range=%s..%s symbols=%s snapshot=%s",
        cfg.output_file,
        len(dataset),
        dataset["data_date"].min(),
        dataset["data_date"].max(),
        ",".join(sorted(dataset["symbol"].unique().tolist())),
        processed_parquet,
    )
    if quality_report.get("warnings"):
        log.warning("Quality contract warnings: %s", quality_report["warnings"])
    return cfg.output_file


def run(cfg: EtlConfig) -> Path:
    cfg = _resolve_incremental_cfg(cfg)
    metadata = running_metadata(cfg)
    save_run_metadata(metadata, cfg)
    try:
        output = _run_impl(cfg, metadata)
        row_count = 0
        parquet_path = cfg.processed_dir / f"market_data_{cfg.run_id}.parquet"
        if parquet_path.exists():
            try:
                import pandas as pd

                completed = pd.read_parquet(parquet_path, columns=["symbol", "data_date"])
                row_count = int(len(completed))
                latest_data_date = pd.to_datetime(completed["data_date"], errors="coerce").dropna().max()
                data_date = str(latest_data_date.date()) if not pd.isna(latest_data_date) else str(cfg.user_end)
                symbols = sorted(completed["symbol"].dropna().astype(str).str.upper().unique().tolist())
            except Exception:
                row_count = 0
                data_date = str(cfg.user_end)
                symbols = sorted(symbol.upper() for symbol in cfg.symbols)
        else:
            data_date = str(cfg.user_end)
            symbols = sorted(symbol.upper() for symbol in cfg.symbols)
        metadata.row_counts["final_rows"] = row_count
        complete_metadata(metadata, status="success", row_count=row_count, output_file=str(output))
        save_run_metadata(metadata, cfg)
        write_last_etl_marker(
            run_id=cfg.run_id,
            data_date=data_date,
            status="success",
            symbols=symbols,
        )
        return output
    except Exception as exc:
        complete_metadata(metadata, status="failed", errors={"run": str(exc)})
        save_run_metadata(metadata, cfg)
        write_last_etl_marker(
            run_id=cfg.run_id,
            data_date="",
            status="failed",
            symbols=sorted(symbol.upper() for symbol in cfg.symbols),
        )
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_symbols(raw: str) -> list[str]:
    out: list[str] = []
    for token in raw.replace(";", ",").split(","):
        symbol = token.strip().upper()
        if symbol and symbol not in out:
            out.append(symbol)
    return out


def _build_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ETL pipeline: Extract -> Transform -> Load market_data.csv",
    )
    parser.add_argument("--start-date", default="2025-04-01")
    parser.add_argument("--end-date", default=date.today().isoformat())
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--text-mode", default="dense", choices=["dense", "raw"])
    parser.add_argument("--output", default="market_data.csv")
    parser.add_argument("--max-workers", type=int, default=6)
    parser.add_argument("--warmup-days", type=int, default=45)
    parser.add_argument("--lake-dir", default="lake")
    parser.add_argument("--log-dir", default="logs")
    parser.add_argument(
        "--extract-sources", default="KBS,VCI",
        help="Comma-separated list of vnstock sources (fallback order)",
    )
    parser.add_argument(
        "--enable-fundamental", action="store_true", default=True,
        help="Enable BCTC extraction (income, balance, cashflow, ratios)",
    )
    parser.add_argument(
        "--disable-fundamental", action="store_true", default=False,
        help="Disable BCTC extraction",
    )
    parser.add_argument(
        "--enable-google-news", action="store_true", default=True,
        help="Enable GoogleNews extraction",
    )
    parser.add_argument(
        "--disable-google-news", action="store_true", default=False,
        help="Disable GoogleNews extraction",
    )
    parser.add_argument(
        "--google-news-period", default="7d",
        help="GoogleNews time period (e.g. 7d, 30d)",
    )
    parser.add_argument(
        "--disable-mysql-load", action="store_true", default=False,
        help="Skip loading processed/raw outputs into MySQL cache tables",
    )
    parser.add_argument(
        "--disable-duckdb-market-load", action="store_true", default=False,
        help="Skip loading daily OHLCV into DuckDB market warehouse",
    )
    parser.add_argument(
        "--disable-tick-eod", action="store_true", default=False,
        help="Skip intraday tick -> daily OHLCV aggregation",
    )
    parser.add_argument(
        "--tick-source", default="lake", choices=["lake", "redis", "auto"],
        help="Source for tick -> EOD aggregation",
    )
    parser.add_argument(
        "--disable-dnse-tick-backfill", action="store_true", default=False,
        help="Skip DNSE historical tick backfill before tick -> EOD aggregation",
    )
    parser.add_argument(
        "--dnse-tick-session-date", default=None,
        help="Backfill this explicit DNSE tick session date instead of the latest completed session",
    )
    parser.add_argument(
        "--force-dnse-tick-backfill", action="store_true", default=False,
        help="Refetch and overwrite existing DNSE tick Parquet files",
    )
    parser.add_argument(
        "--run-mode", default="full", choices=["full", "incremental", "backfill"],
        help="Run strategy. incremental resolves start date from the latest processed snapshot; backfill merges a specified range into the latest snapshot.",
    )
    parser.add_argument(
        "--incremental-overlap-days", type=int, default=7,
        help="Calendar days to overlap when resolving incremental start date.",
    )
    parser.add_argument(
        "--no-merge-with-latest", action="store_true", default=False,
        help="Do not merge incremental/backfill output with the latest processed snapshot.",
    )
    return parser


def main() -> None:
    args = _build_argparser().parse_args()
    symbols = _parse_symbols(args.symbols)
    if not symbols:
        raise ValueError("No valid symbols. Use --symbols MBB,FPT,HPG")

    # Parse extract sources
    sources = [s.strip().upper() for s in args.extract_sources.split(",") if s.strip()]

    cfg = EtlConfig.from_args(
        start_date=args.start_date,
        end_date=args.end_date,
        symbols=symbols,
        text_mode=args.text_mode,
        output_file=args.output,
        max_workers=args.max_workers,
        warmup_days=args.warmup_days,
        lake_dir=args.lake_dir,
        log_dir=args.log_dir,
        extract_sources=sources,
        enable_fundamental=args.enable_fundamental and not args.disable_fundamental,
        enable_google_news=args.enable_google_news and not args.disable_google_news,
        google_news_period=args.google_news_period,
        enable_mysql_load=not args.disable_mysql_load,
        enable_market_duckdb_load=not args.disable_duckdb_market_load,
        enable_tick_eod=not args.disable_tick_eod,
        tick_source=args.tick_source,
        enable_dnse_tick_backfill=not args.disable_dnse_tick_backfill,
        dnse_tick_session_date=args.dnse_tick_session_date,
        force_dnse_tick_backfill=args.force_dnse_tick_backfill,
        run_mode=args.run_mode,
        incremental_overlap_days=args.incremental_overlap_days,
        merge_with_latest=not args.no_merge_with_latest,
    )
    run(cfg)


if __name__ == "__main__":
    main()
