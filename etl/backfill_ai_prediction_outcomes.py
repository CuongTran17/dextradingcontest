from __future__ import annotations

import argparse

from backend_v2.src.database.market_duckdb import MarketDuckDB, market_repo


def _direction_for_return(value: float | None) -> str | None:
    if value is None:
        return None
    if value > 0:
        return "UP"
    if value < 0:
        return "DOWN"
    return "FLAT"


def _is_correct(decision: str | None, actual_direction: str | None) -> bool | None:
    if decision is None or actual_direction is None:
        return None
    decision = decision.upper()
    if decision == "BUY":
        return actual_direction == "UP"
    if decision == "SELL":
        return actual_direction == "DOWN"
    if decision == "HOLD":
        return actual_direction == "FLAT"
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill AI prediction outcomes from DuckDB daily prices.")
    parser.add_argument(
        "--horizon-trading-days",
        type=int,
        default=5,
        help=(
            "Number of trading sessions after analysis_date. Weekends and holidays are skipped "
            "because daily_ohlcv only has market sessions."
        ),
    )
    args = parser.parse_args()

    repo = market_repo._get_repo() if hasattr(market_repo, "_get_repo") else MarketDuckDB()
    with repo.connect() as conn:
        runs = conn.execute(
            """
            SELECT analysis_id, symbol, analysis_date, decision, current_price
            FROM ai_analysis_runs
            WHERE status = 'success'
            ORDER BY analysis_date
            """
        ).fetchall()

    updated = 0
    with repo.connect() as conn:
        for analysis_id, symbol, analysis_date, decision, current_price in runs:
            # Trading-day horizon, not calendar-day horizon:
            # OFFSET 4 means the 5th available daily_ohlcv row after analysis_date.
            price_row = conn.execute(
                """
                SELECT date, close
                FROM daily_ohlcv
                WHERE symbol = ? AND date > ?
                ORDER BY date
                LIMIT 1 OFFSET ?
                """,
                [symbol, analysis_date, max(args.horizon_trading_days - 1, 0)],
            ).fetchone()
            if not price_row or not current_price:
                continue
            exit_date, exit_price = price_row
            future_return_pct = ((float(exit_price) - float(current_price)) / float(current_price)) * 100
            actual_direction = _direction_for_return(future_return_pct)
            repo.upsert_ai_prediction_outcome(
                analysis_id=analysis_id,
                horizon_days=args.horizon_trading_days,
                entry_price=float(current_price),
                exit_date=exit_date,
                exit_price=float(exit_price),
                future_return_pct=future_return_pct,
                actual_direction=actual_direction,
                is_correct=_is_correct(decision, actual_direction),
            )
            updated += 1

    print(f"Updated {updated} AI prediction outcomes for horizon={args.horizon_trading_days} trading days")


if __name__ == "__main__":
    main()
