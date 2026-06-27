"""Backfill DuckDB market feature mart from an existing parquet snapshot."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from etl.load_to_duckdb import load_market_features_to_duckdb


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill DuckDB market_features_daily from a processed parquet file.",
    )
    parser.add_argument("--parquet", default="lake/gold/market_features/latest.parquet")
    parser.add_argument("--run-id", default="backfill-latest")
    args = parser.parse_args()

    parquet_path = Path(args.parquet)
    if not parquet_path.exists():
        raise FileNotFoundError(parquet_path)

    dataset = pd.read_parquet(parquet_path)
    count = load_market_features_to_duckdb(
        dataset=dataset,
        run_id=args.run_id,
        source_path=str(parquet_path),
    )
    print(f"Loaded {count} market feature rows from {parquet_path}")


if __name__ == "__main__":
    main()
