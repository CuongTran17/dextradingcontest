from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from src.settings import REPO_ROOT
except ModuleNotFoundError:
    from backend_v2.src.settings import REPO_ROOT


def _marker_path(repo_root: Path | None = None) -> Path:
    return Path(repo_root or REPO_ROOT) / "lake" / "status" / "last_etl_run.json"


def write_last_etl_marker(
    run_id: str,
    data_date: str,
    status: str,
    symbols: list[str],
    repo_root: Path | None = None,
) -> Path:
    path = _marker_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": run_id,
        "data_date": data_date,
        "status": status,
        "symbols": symbols,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_last_etl_marker(repo_root: Path | None = None) -> dict[str, Any]:
    path = _marker_path(repo_root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}
