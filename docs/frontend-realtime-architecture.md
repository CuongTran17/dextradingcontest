# Frontend Realtime Architecture

The application owns one realtime lifecycle through `realtimeManager`, started by
`App.vue`. Pages do not open or close WebSocket connections.

Pages declare temporary price demand with `usePriceSubscription(ownerId,
symbols)`. The symbol registry deduplicates symbols across pages and keeps a
symbol active until every owner releases it.

`stockPriceStore` is the shared source of current stock prices. WebSocket quotes
update it immediately. When WebSocket is unavailable, the realtime manager polls
backend snapshots for active symbols only and periodically retries WebSocket.

Persistent watchlist membership and temporary realtime subscription are separate:
viewing a stock does not add it to the user's watchlist.

Only current prices auto-update. Historical charts, technical analysis, news,
events, financial data, and AI analysis retain their existing refresh behavior.
