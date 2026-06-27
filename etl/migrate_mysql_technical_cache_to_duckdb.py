"""One-time migration for MySQL technical_cache rows into DuckDB."""
from __future__ import annotations

import argparse
import json

from sqlalchemy import create_engine, text

from backend_v2.src.database.market_duckdb import LazyMarketDuckDB, MarketDuckDB, market_repo
from backend_v2.src.settings import get_settings


def migrate(*, dry_run: bool = True, repo: MarketDuckDB | LazyMarketDuckDB = market_repo) -> int:
    settings = get_settings()
    engine = create_engine(settings.mysql_url)

    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT symbol, start_date, end_date, limit_value, history_count,
                       history_last_time, payload_json, source, updated_at
                FROM technical_cache
                ORDER BY symbol, limit_value, start_date, end_date
                """
            )
        ).mappings().all()

    if dry_run:
        print(f"DRY RUN: would migrate {len(rows)} technical_cache rows")
        return len(rows)

    total = 0
    for row in rows:
        payload = json.loads(row["payload_json"])
        if not isinstance(payload, dict):
            payload = {}
        repo.upsert_technical_cache(
            str(row["symbol"]).upper(),
            row["start_date"],
            row["end_date"],
            int(row["limit_value"]),
            int(row["history_count"]),
            row["history_last_time"],
            payload,
            str(row["source"] or "mysql-migrated"),
        )
        total += 1
    print(f"Migrated {total} technical_cache rows")
    return total


def main() -> None:
    parser = argparse.ArgumentParser(description="Migrate MySQL technical_cache rows into DuckDB.")
    parser.add_argument("--execute", action="store_true", help="Write rows into DuckDB. Without this flag, dry-run only.")
    args = parser.parse_args()
    migrate(dry_run=not args.execute)


if __name__ == "__main__":
    main()
