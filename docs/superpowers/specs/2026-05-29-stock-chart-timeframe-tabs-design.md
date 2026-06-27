# Stock Chart Timeframe Tabs Design

## Goal

Add chart controls for minute, hourly, and daily/monthly views on the stock detail chart without breaking outside-session behavior.

## User Experience

The stock detail TradingView chart uses two levels of controls:

- Primary tabs: `Phút`, `Giờ`, `Ngày`
- `Phút`: `1P`, `5P`, `15P`
- `Giờ`: `1G`, `4G`
- `Ngày`: `1D`, `1T`, `3T`, `6T`, `1N`

Changing the primary tab selects the first child timeframe in that group. The active child timeframe controls the chart data. The chart remains a candlestick chart for stock detail views.

## Data Flow

Intraday timeframes call the existing stock intraday endpoint:

- `1P`: `/api/stocks/{symbol}/intraday?interval_minutes=1`
- `5P`: `/api/stocks/{symbol}/intraday?interval_minutes=5`
- `15P`: `/api/stocks/{symbol}/intraday?interval_minutes=15`
- `1G`: `/api/stocks/{symbol}/intraday?interval_minutes=60`
- `4G`: `/api/stocks/{symbol}/intraday?interval_minutes=240`

Daily/monthly/yearly timeframes keep using `/api/stocks/{symbol}/history`.

## Outside-Session Behavior

Outside trading hours, intraday views use cached DNSE ticks if available. If there are no cached ticks, the backend returns HTTP 200 with an empty data array and `NO_DATA_IN_SNAPSHOT`. The frontend then falls back to a short daily history view for `1D`; for minute/hour views it shows the available empty chart state instead of treating the response as a backend failure.

No ETL run is triggered by changing chart timeframe. The chart must not introduce DuckDB write conflicts.

## Backend Changes

The existing `/intraday` endpoint already aggregates ticks with `interval_minutes`, but currently caps the value below the requested hourly windows. Increase the allowed interval to support `240`.

## Frontend Changes

Expose `interval_minutes` from `stockBackendApi.getIntraday()`. Replace the flat stock detail timeframe button list with grouped controls and route the selected timeframe to either intraday or daily history loading.

## Verification

Backend tests should cover that `interval_minutes=240` is accepted and returned. Frontend type-check should pass after updating TypeScript types and chart control state.
