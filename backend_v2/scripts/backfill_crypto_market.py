from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.database.crypto_market_duckdb import crypto_market_repo
from src.services.crypto_market_backfill import (
    DEFAULT_SYMBOLS,
    CryptoMarketBackfillService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill Binance Spot 1m candles into crypto_market.duckdb.",
    )
    parser.add_argument(
        "--symbols",
        default=",".join(DEFAULT_SYMBOLS),
        help="Comma-separated Binance Spot symbols.",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=365,
        help="Rolling history window in days.",
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=1000,
        help="Binance page size from 1 to 1000.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    symbols = tuple(
        item.strip().upper()
        for item in args.symbols.split(",")
        if item.strip()
    )
    if not symbols:
        raise SystemExit("At least one symbol is required")
    if args.days < 1:
        raise SystemExit("--days must be greater than zero")
    if not 1 <= args.page_limit <= 1000:
        raise SystemExit("--page-limit must be between 1 and 1000")

    service = CryptoMarketBackfillService()
    for symbol in symbols:
        result = service.backfill_symbol(
            symbol,
            days=args.days,
            page_limit=args.page_limit,
        )
        checkpoint = result["last_closed_open_time"]
        checkpoint_text = checkpoint.isoformat() if checkpoint else "none"
        print(
            f"{symbol}: pages={result['pages']} stored={result['stored']} "
            f"checkpoint={checkpoint_text}"
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    deleted = crypto_market_repo.delete_older_than(cutoff)
    print(
        f"retention_deleted={deleted} warehouse={crypto_market_repo.db_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
