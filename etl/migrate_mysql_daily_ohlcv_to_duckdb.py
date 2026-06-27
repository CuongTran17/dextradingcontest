"""One-time migration for MySQL daily_ohlcv rows into DuckDB."""
from __future__ import annotations

import argparse
from collections import defaultdict

from sqlalchemy import create_engine, text

from backend_v2.src.database.market_duckdb import LazyMarketDuckDB, MarketDuckDB, market_repo
from backend_v2.src.settings import get_settings


def migrate(
    *,
    dry_run: bool = True,
    repo: MarketDuckDB | LazyMarketDuckDB = market_repo,
) -> int:
    settings = get_settings()
    engine = create_engine(settings.mysql_url)
    grouped: dict[str, list[dict]] = defaultdict(list)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT symbol, date, open, high, low, close, volume
                FROM daily_ohlcv
                ORDER BY symbol, date
                """
            )
        ).mappings().all()

    for row in rows:
        grouped[str(row["symbol"]).upper()].append(dict(row))

    if dry_run:
        print(f"DRY RUN: would migrate {len(rows)} rows across {len(grouped)} symbols")
        return len(rows)

    total = 0
    for symbol, symbol_rows in grouped.items():
        total += repo.upsert_daily_rows(symbol, symbol_rows)
    print(f"Migrated {total} rows across {len(grouped)} symbols")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate MySQL daily_ohlcv rows into DuckDB.")
    parser.add_argument("--execute", action="store_true", help="Write rows into DuckDB. Without this flag, dry-run only.")
    args = parser.parse_args()
    migrate(dry_run=not args.execute)


if __name__ == "__main__":
    main()
