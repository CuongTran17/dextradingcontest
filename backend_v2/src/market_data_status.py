from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import HTTPException


class MarketDataStatus(StrEnum):
    DATA_AVAILABLE = "DATA_AVAILABLE"
    NO_DATA_IN_SNAPSHOT = "NO_DATA_IN_SNAPSHOT"
    SNAPSHOT_NOT_BUILT = "SNAPSHOT_NOT_BUILT"
    REFRESH_DISABLED_IN_SNAPSHOT_MODE = "REFRESH_DISABLED_IN_SNAPSHOT_MODE"
    ETL_RUNNING = "ETL_RUNNING"
    ETL_FAILED = "ETL_FAILED"
    STALE_SNAPSHOT = "STALE_SNAPSHOT"


DATA_AVAILABLE = MarketDataStatus.DATA_AVAILABLE
NO_DATA_IN_SNAPSHOT = MarketDataStatus.NO_DATA_IN_SNAPSHOT
SNAPSHOT_NOT_BUILT = MarketDataStatus.SNAPSHOT_NOT_BUILT
REFRESH_DISABLED_IN_SNAPSHOT_MODE = MarketDataStatus.REFRESH_DISABLED_IN_SNAPSHOT_MODE
ETL_RUNNING = MarketDataStatus.ETL_RUNNING
ETL_FAILED = MarketDataStatus.ETL_FAILED
STALE_SNAPSHOT = MarketDataStatus.STALE_SNAPSHOT


def market_meta(
    status: MarketDataStatus | str,
    *,
    run_id: str | None = None,
    last_synced_at: str | None = None,
    stale: bool = False,
    message: str | None = None,
) -> dict[str, Any]:
    return {
        "data_status": str(status),
        "run_id": run_id,
        "last_synced_at": last_synced_at,
        "stale": stale,
        "message": message,
    }


def reject_refresh_in_snapshot_mode(refresh: bool | str | object) -> None:
    requested = refresh is True or (isinstance(refresh, str) and refresh.strip().lower() == "true")
    if not requested:
        return

    raise HTTPException(
        status_code=409,
        detail={
            "code": REFRESH_DISABLED_IN_SNAPSHOT_MODE,
            "message": "Read APIs cannot refresh upstream market data in snapshot mode. Run CLI/admin ETL instead.",
        },
    )
