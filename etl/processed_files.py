from __future__ import annotations

from pathlib import Path

from etl.manifest import load_latest_manifest


def latest_processed_parquet(processed_dir: Path, *, exclude_run_id: str | None = None) -> Path | None:
    try:
        manifest = load_latest_manifest(processed_dir.parent)
        candidate = Path(manifest.processed_path)
        if candidate.exists() and (exclude_run_id is None or manifest.run_id != exclude_run_id):
            return candidate
    except Exception:
        pass

    files = sorted(
        (
            path
            for path in processed_dir.glob("market_data_*.parquet")
            if exclude_run_id is None or exclude_run_id not in path.name
        ),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return files[0] if files else None
