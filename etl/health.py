"""Health checks for processed ETL outputs."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from etl.config import DEFAULT_SYMBOLS, EtlConfig
from etl.run_metadata import load_recent_runs


def _default_cfg() -> EtlConfig:
    today = datetime.now(timezone.utc).date()
    return EtlConfig(user_start=today, user_end=today, symbols=list(DEFAULT_SYMBOLS))


def _load_latest_snapshot_meta(cfg: EtlConfig) -> dict[str, Any] | None:
    files = sorted(cfg.processed_dir.glob("market_data_*.meta.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["_path"] = str(path)
            data["_mtime"] = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
            return data
        except json.JSONDecodeError:
            continue
    return None


def get_recent_runs(cfg: EtlConfig | None = None, limit: int = 10) -> list[dict[str, Any]]:
    cfg = cfg or _default_cfg()
    return [item.to_dict() for item in load_recent_runs(cfg, limit=limit)]


def check_etl_health(cfg: EtlConfig | None = None) -> dict[str, Any]:
    cfg = cfg or _default_cfg()
    latest_run = load_recent_runs(cfg, limit=1)
    latest_snapshot = _load_latest_snapshot_meta(cfg)

    if not latest_run and not latest_snapshot:
        return {"status": "error", "details": "No ETL metadata found", "latest_run": None, "latest_snapshot": None}

    now = datetime.now(timezone.utc)
    reference_time: datetime | None = None
    latest_run_dict = latest_run[0].to_dict() if latest_run else None
    if latest_run and latest_run[0].completed_at:
        reference_time = latest_run[0].completed_at
    elif latest_snapshot and latest_snapshot.get("_mtime"):
        reference_time = datetime.fromisoformat(latest_snapshot["_mtime"])

    age_hours = None
    status = "healthy"
    details = "ETL output is fresh"
    if reference_time:
        age_hours = (now - reference_time).total_seconds() / 3600
        if age_hours > 24:
            status = "stale"
            details = f"Latest ETL output is {age_hours:.1f} hours old"

    symbols = set(latest_snapshot.get("symbols") or []) if latest_snapshot else set()
    missing_symbols = sorted(set(cfg.symbols) - symbols) if symbols else []
    if missing_symbols and latest_snapshot:
        status = "stale" if status == "healthy" else status
        details = f"Missing symbols in latest snapshot: {','.join(missing_symbols[:10])}"

    if latest_run and latest_run[0].status == "failed":
        status = "error"
        details = "Latest ETL run failed"

    disk_target = cfg.processed_dir if cfg.processed_dir.exists() else cfg.lake_dir
    disk = None
    try:
        usage = shutil.disk_usage(disk_target if disk_target.exists() else Path("."))
        disk = {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "free_ratio": round(usage.free / usage.total, 4) if usage.total else None,
        }
        if disk["free_ratio"] is not None and disk["free_ratio"] < 0.05:
            status = "error"
            details = "Disk free space below 5%"
    except OSError:
        disk = None

    return {
        "status": status,
        "details": details,
        "age_hours": age_hours,
        "missing_symbols": missing_symbols,
        "disk": disk,
        "latest_run": latest_run_dict,
        "latest_snapshot": latest_snapshot,
    }
