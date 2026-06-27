from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class EtlManifest:
    run_id: str
    status: str
    processed_path: str
    processed_metadata_path: str
    gold_market_features_path: str
    gold_market_features_latest_path: str
    duckdb_path: str
    row_count: int
    symbol_count: int
    symbols: list[str]
    checksum_sha256: str
    quality_status: str
    published_at: str = ""
    manifest_version: int = 1

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        if not data["published_at"]:
            data["published_at"] = datetime.now(timezone.utc).isoformat()
        return data


def manifest_path(lake_dir: str | Path) -> Path:
    return Path(lake_dir) / "manifests" / "latest_success.json"


def publish_latest_manifest(lake_dir: str | Path, manifest: EtlManifest) -> Path:
    path = manifest_path(lake_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    tmp_path.replace(path)
    return path


def load_latest_manifest(lake_dir: str | Path) -> EtlManifest:
    path = manifest_path(lake_dir)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return EtlManifest(**raw)
