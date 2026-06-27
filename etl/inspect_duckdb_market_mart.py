"""Inspect DuckDB market feature mart coverage."""
from __future__ import annotations

import duckdb

from backend_v2.src.database.market_duckdb import _resolve_duckdb_path


def main() -> None:
    db_path = _resolve_duckdb_path()
    with duckdb.connect(str(db_path), read_only=True) as conn:
        feature_summary = conn.execute(
            """
            SELECT
                COUNT(*) AS row_count,
                COUNT(DISTINCT symbol) AS symbol_count,
                MIN(data_date) AS min_date,
                MAX(data_date) AS max_date
            FROM market_features_daily
            """
        ).fetchone()
        print("market_features_daily")
        print(feature_summary)

        columns = conn.execute("PRAGMA table_info('market_features_daily')").fetchall()
        print("columns")
        print(len(columns))

        recent_runs = conn.execute(
            """
            SELECT run_id, row_count, symbol_count, min_date, max_date, source_path, loaded_at
            FROM market_feature_runs
            ORDER BY loaded_at DESC
            LIMIT 5
            """
        ).fetchall()
        print("market_feature_runs")
        for run in recent_runs:
            print(run)


if __name__ == "__main__":
    main()
