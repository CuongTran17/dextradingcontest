# Crypto Market Data Flow

## Goal

Crypto runs 24/7, so market data must not depend on trading sessions. DuckDB stores the canonical local market warehouse, and Binance Spot is the public source of truth for repair and fallback.

## Current Spot Flow

1. Binance WebSocket receives realtime mini ticker, closed `1m` kline, and order book depth for `BTCUSDT`, `ETHUSDT`, `SOLUSDT`, `XRPUSDT`, and `BNBUSDT`.
2. Closed `1m` candles are appended to DuckDB table `crypto_candles`.
3. `5m`, `15m`, `1h`, and `4h` candles are derived from complete `1m` buckets only.
4. Indicators such as MACD are materialized from DuckDB candles.
5. The chart API reads DuckDB first only when the requested window is complete, continuous, and fresh.
6. If DuckDB is incomplete, stale, or gapped, the chart API falls back to Binance REST so the UI does not show broken candles.

## Repair Flow

Run backfill whenever the backend has been offline or WebSocket persistence was interrupted:

```powershell
.\.venv\Scripts\python.exe backend_v2\scripts\backfill_crypto_market.py --symbols BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT --days 365 --page-limit 1000
```

The repair job fills missing `1m` ranges, rebuilds derived intervals, materializes indicators, and trims data outside the retention window.

## Next Upgrade

Add a scheduled 24/7 gap-repair job inside the backend:

- Run every few minutes.
- Check the latest closed `1m` candle for each symbol.
- Backfill missing ranges from Binance REST.
- Rebuild derived intervals and indicators after repair.
- Expose data freshness in `/api/health`.

For Futures, keep the same shape but separate `market_type='futures'` and use Binance Futures endpoints instead of mixing Spot and Futures rows.
