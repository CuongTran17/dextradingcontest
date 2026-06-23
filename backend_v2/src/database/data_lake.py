import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

logger = logging.getLogger(__name__)

_VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DATA_LAKE_DIR = Path(__file__).resolve().parents[2] / "data_lake" / "ticks"


def _jsonable_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def dump_ticks_to_parquet_for_date(
    symbol: str,
    ticks: list[dict],
    session_date: date,
    *,
    base_dir: Path = DATA_LAKE_DIR,
) -> Path | None:
    if not ticks:
        return None

    try:
        normalized = symbol.strip().upper()
        folder_path = base_dir / session_date.isoformat()
        folder_path.mkdir(parents=True, exist_ok=True)

        file_path = folder_path / f"{normalized}.parquet"
        temp_path = file_path.with_suffix(".tmp.parquet")

        df = pd.DataFrame(ticks)
        if not df.empty:
            df.to_parquet(temp_path, engine="pyarrow", index=False)
            temp_path.replace(file_path)
            logger.info("Dumped %d ticks to Data Lake: %s", len(df), file_path)
            return file_path
    except Exception as exc:
        logger.error("Failed to dump parquet for %s: %s", symbol, exc)
    return None


def dump_ticks_to_parquet(symbol: str, ticks: list[dict], *, base_dir: Path = DATA_LAKE_DIR):
    dump_ticks_to_parquet_for_date(symbol, ticks, datetime.now(tz=_VN_TZ).date(), base_dir=base_dir)


def read_ticks_from_parquet(
    symbol: str,
    session_date: date,
    *,
    base_dir: Path = DATA_LAKE_DIR,
) -> list[dict[str, Any]]:
    normalized = symbol.strip().upper()
    file_path = base_dir / session_date.isoformat() / f"{normalized}.parquet"
    if not file_path.exists():
        return []
    try:
        frame = pd.read_parquet(file_path)
    except Exception as exc:
        logger.warning("Failed to read tick parquet %s: %s", file_path, exc)
        return []
    if frame.empty:
        return []
    rows = [
        {key: _jsonable_value(value) for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]
    return sorted(rows, key=lambda item: str(item.get("time") or ""))


def read_latest_session_ticks_from_parquet(
    symbol: str,
    *,
    base_dir: Path = DATA_LAKE_DIR,
    max_days: int = 10,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    normalized = symbol.strip().upper()
    if not normalized or not base_dir.exists():
        return []

    date_dirs = sorted(
        (path for path in base_dir.iterdir() if path.is_dir()),
        reverse=True,
    )[:max_days]

    for date_dir in date_dirs:
        try:
            session_date = date.fromisoformat(date_dir.name)
        except ValueError:
            continue
        ticks = read_ticks_from_parquet(normalized, session_date, base_dir=base_dir)
        if ticks:
            return ticks[-limit:] if limit is not None else ticks
    return []


def read_latest_tick_from_parquet(
    symbol: str,
    *,
    base_dir: Path = DATA_LAKE_DIR,
    max_days: int = 10,
) -> dict[str, Any] | None:
    normalized = symbol.strip().upper()
    if not normalized or not base_dir.exists():
        return None

    date_dirs = sorted(
        (path for path in base_dir.iterdir() if path.is_dir()),
        reverse=True,
    )[:max_days]

    for date_dir in date_dirs:
        file_path = date_dir / f"{normalized}.parquet"
        if not file_path.exists():
            continue
        try:
            frame = pd.read_parquet(file_path)
        except Exception as exc:
            logger.warning("Failed to read tick parquet %s: %s", file_path, exc)
            continue
        if frame.empty:
            continue
        sort_key = "time" if "time" in frame.columns else None
        if sort_key:
            frame = frame.sort_values(sort_key)
        row = {
            key: _jsonable_value(value)
            for key, value in frame.iloc[-1].to_dict().items()
        }
        row["symbol"] = normalized
        row["storage_source"] = "parquet"
        return row

    return None
