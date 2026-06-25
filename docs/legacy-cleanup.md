# Legacy Cleanup Inventory

## Removed From Runtime

- Vietnam stock and DNSE market data
- VNStock ingestion and ETL
- Stock AI and Kaggle integration
- News, events, and stock technical analysis
- Payment, premium subscriptions, promotions, and flash sales
- Stock portfolio APIs and stock realtime WebSockets

## Retained

- Existing MySQL database and Alembic history
- Authentication and user profiles
- Crypto contest and virtual trading tables
- Binance REST market data
- DuckDB crypto candle warehouse
- Shared frontend layout and CSS

## Reference Code

Old frontend feature files are stored under `legacy/frontend/` and are excluded from the
production build.
