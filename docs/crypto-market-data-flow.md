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

## Startup Repair

The backend starts an incremental repair task with these settings:

```env
CRYPTO_REPAIR_ON_STARTUP=true
CRYPTO_REPAIR_LOOKBACK_DAYS=365
CRYPTO_REPAIR_INTERVAL_SECONDS=300
```

The task does not reload the full lookback window when data already exists. It uses the warehouse gap detection to fetch only missing `1m` ranges, then rebuilds derived intervals and indicators.

## Next Upgrade

Make the repair job easier to observe and operate:

- Add per-symbol freshness details to `/api/health`.
- Add admin-visible data source and repair status.
- Add manual admin trigger for one symbol/time range.

For Futures, keep the same shape but separate `market_type='futures'` and use Binance Futures endpoints instead of mixing Spot and Futures rows.
