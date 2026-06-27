from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from etl.config import DEFAULT_SYMBOLS

try:
    from backend_v2.src.database.data_lake import DATA_LAKE_DIR, dump_ticks_to_parquet_for_date, read_ticks_from_parquet
    from backend_v2.src.services.dnse_market_data import DnseMarketDataClient, get_dnse_market_client
except ModuleNotFoundError:
    from src.database.data_lake import DATA_LAKE_DIR, dump_ticks_to_parquet_for_date, read_ticks_from_parquet  # type: ignore
    from src.services.dnse_market_data import DnseMarketDataClient, get_dnse_market_client  # type: ignore


VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


@dataclass
class DnseTickBackfillResult:
    session_date: date
    backfilled: list[str] = field(default_factory=list)
    skipped_existing: list[str] = field(default_factory=list)
    empty_from_dnse: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


def latest_completed_session_date(now: datetime | None = None) -> date:
    current = now.astimezone(VN_TZ) if now else datetime.now(tz=VN_TZ)
    candidate = current.date()
    if current.weekday() < 5 and current.hour >= 15:
        return candidate
    candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


def _has_existing_ticks(symbol: str, session_date: date, base_dir: Path) -> bool:
    path = base_dir / session_date.isoformat() / f"{symbol.upper()}.parquet"
    if not path.exists() or path.stat().st_size <= 0:
        return False
    ticks = read_ticks_from_parquet(symbol, session_date, base_dir=base_dir)
    return any(str(tick.get("source") or "") == "dnse_historical" for tick in ticks)


async def _backfill_dnse_ticks_for_session_async(
    symbols: list[str],
    session_date: date,
    *,
    base_dir: Path = DATA_LAKE_DIR,
    client: DnseMarketDataClient | Any | None = None,
    force: bool = False,
) -> DnseTickBackfillResult:
    market_client = client or get_dnse_market_client()
    result = DnseTickBackfillResult(session_date=session_date)

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        if not symbol:
            continue
        if not force and _has_existing_ticks(symbol, session_date, base_dir):
            result.skipped_existing.append(symbol)
            continue
        try:
            ticks = await market_client.get_historical_trades_for_session(symbol, session_date)
            if not ticks:
                result.empty_from_dnse.append(symbol)
                continue
            dump_ticks_to_parquet_for_date(symbol, ticks, session_date, base_dir=base_dir)
            result.backfilled.append(symbol)
        except Exception as exc:
            result.failed[symbol] = str(exc)

    return result


def backfill_dnse_ticks_for_session(
    symbols: list[str],
    session_date: date,
    *,
    base_dir: Path = DATA_LAKE_DIR,
    client: DnseMarketDataClient | Any | None = None,
    force: bool = False,
) -> DnseTickBackfillResult:
    return asyncio.run(
        _backfill_dnse_ticks_for_session_async(
            symbols,
            session_date,
            base_dir=base_dir,
            client=client,
            force=force,
        )
    )


def backfill_latest_session_ticks(
    symbols: list[str],
    *,
    base_dir: Path = DATA_LAKE_DIR,
    client: DnseMarketDataClient | Any | None = None,
    force: bool = False,
) -> DnseTickBackfillResult:
    return backfill_dnse_ticks_for_session(
        symbols,
        latest_completed_session_date(),
        base_dir=base_dir,
        client=client,
        force=force,
    )


def _parse_symbols(raw: str) -> list[str]:
    return [token.strip().upper() for token in raw.replace(";", ",").split(",") if token.strip()]


def main() -> None:
    env_path = Path("backend_v2/.env")
    if env_path.exists():
        load_dotenv(env_path)

    parser = argparse.ArgumentParser(description="Backfill DNSE historical ticks into Parquet.")
    parser.add_argument("--symbols", default=",".join(DEFAULT_SYMBOLS))
    parser.add_argument("--latest-session", action="store_true", default=False)
    parser.add_argument("--session-date", default=None)
    parser.add_argument("--force", action="store_true", default=False)
    args = parser.parse_args()

    if args.session_date:
        session_date = date.fromisoformat(args.session_date)
    else:
        session_date = latest_completed_session_date()

    result = backfill_dnse_ticks_for_session(
        _parse_symbols(args.symbols),
        session_date,
        force=args.force,
    )
    print(
        f"session_date={result.session_date} "
        f"backfilled={len(result.backfilled)} "
        f"skipped_existing={len(result.skipped_existing)} "
        f"empty_from_dnse={len(result.empty_from_dnse)} "
        f"failed={len(result.failed)}"
    )
    if result.failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
