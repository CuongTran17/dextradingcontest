# Binance Spot WebSocket Realtime Design

## Goal

Add reliable Binance Spot realtime market data for BTCUSDT, ETHUSDT, SOLUSDT, XRPUSDT, and
BNBUSDT without API keys or real exchange trading.

The backend will maintain live prices, current `1m` candles, and synchronized order books. It
will expose one WebSocket connection to each frontend client and persist only closed `1m`
candles to DuckDB.

## Scope

### Included

- Always subscribe to all five supported Spot symbols.
- Stream latest prices for all five symbols.
- Stream current and closed `1m` candles.
- Maintain 100 bid and 100 ask levels per symbol.
- Synchronize local order books using REST snapshots and Binance diff-depth events.
- Persist closed `1m` candles to DuckDB.
- Rebuild `5m`, `15m`, `1h`, and `4h` intervals after closed candles are stored.
- Repair missing `1m` candles through REST after reconnect.
- Serve frontend clients through one backend WebSocket connection per browser tab.
- Keep existing REST endpoints as startup and outage fallback.

### Excluded

- Binance API keys.
- User data streams.
- Real Binance orders or account balances.
- Futures data.
- Persisting ticker events, trades, orderbook snapshots, or depth diffs.
- Redis, Kafka, or multi-instance pub/sub.

## Binance Connections

The backend opens one combined public market-data connection using:

```text
wss://data-stream.binance.vision/stream?streams=...
```

For each supported lowercase symbol, it subscribes to:

```text
<symbol>@miniTicker
<symbol>@kline_1m
<symbol>@depth@100ms
```

This produces 15 streams on one Binance connection, below Binance's 1024-stream limit.

The connection requires no API key. The client must respond to WebSocket ping frames and must
expect Binance to close a connection after 24 hours.

## Backend Components

### Binance Stream Client

Owns the outbound Binance connection. Responsibilities:

- Build the combined stream URL.
- Decode combined stream envelopes.
- Route ticker, kline, and depth messages by event type.
- Reconnect with bounded exponential backoff.
- Rotate the connection before the 24-hour limit.
- Report connection state and last event time.

Only one stream-client task runs per backend process.

### Realtime Market Cache

An in-memory, concurrency-safe cache stores:

- Latest price and update time for each symbol.
- Current `1m` candle for each symbol.
- Last closed `1m` candle for each symbol.
- Synchronized orderbook state for each symbol.
- Connection and synchronization status.

Ticker and candle reads return immutable snapshots so API routes and frontend broadcasters do
not observe partially updated state.

### Orderbook Synchronizer

Each symbol owns an independent local orderbook:

1. Start buffering Binance diff-depth events.
2. Request a REST depth snapshot.
3. Discard buffered events whose final update ID is not newer than the snapshot.
4. Find the first event whose update range bridges the snapshot update ID.
5. Apply buffered and subsequent events in sequence.
6. Set quantity to the new value; remove a level when quantity is zero.
7. Keep only the best 100 bids and best 100 asks.
8. If a sequence gap is detected, clear synchronization state and repeat the process.

The orderbook is considered usable only after snapshot synchronization succeeds. Until then,
the existing REST orderbook endpoint remains the fallback.

### Candle Persistence Worker

When a `kline_1m` event has `x = true`:

1. Normalize all Binance fields into the existing DuckDB candle schema.
2. Queue the candle for persistence.
3. Upsert the closed `1m` candle idempotently.
4. Update the ingestion checkpoint.
5. Materialize `5m`, `15m`, `1h`, and `4h` for that symbol.
6. Broadcast the closed candle to frontend clients.

The WebSocket receive loop must not block on DuckDB writes. A bounded asynchronous queue and
one persistence worker serialize DuckDB writes.

Ticker messages, open candles, orderbook snapshots, and depth events are never written to
DuckDB.

## Gap Repair

After initial connection and after every reconnect:

- Run the existing incremental backfill service for all five symbols.
- Compare DuckDB history through the last fully closed minute.
- Fetch and store only missing ranges.
- Resume stream processing without rebuilding the full one-year history.

Backfill errors do not stop realtime prices or orderbooks. They are recorded in service status
and retried after the next reconnect or scheduled repair.

## Frontend WebSocket Protocol

The frontend opens one connection:

```text
ws://localhost:8000/api/crypto/ws
```

On connection, the backend sends:

```json
{
  "type": "snapshot",
  "prices": {},
  "connection": {
    "status": "connected",
    "updated_at": 0
  }
}
```

The frontend sends a subscription message when the selected trade symbol changes:

```json
{
  "type": "subscribe",
  "symbol": "ETHUSDT"
}
```

Only one detailed symbol subscription is active per frontend connection. Price updates for all
five symbols are always sent.

Server event types:

```text
prices
candle
orderbook
status
error
```

Example price event:

```json
{
  "type": "prices",
  "prices": {
    "BTCUSDT": 60000.0,
    "ETHUSDT": 1600.0
  },
  "event_time": 1782400000000
}
```

Example candle event:

```json
{
  "type": "candle",
  "symbol": "ETHUSDT",
  "interval": "1m",
  "closed": false,
  "candle": {
    "time": 1782400000,
    "open": 1600.0,
    "high": 1602.0,
    "low": 1599.0,
    "close": 1601.0,
    "volume": 120.0
  }
}
```

Example orderbook event:

```json
{
  "type": "orderbook",
  "symbol": "ETHUSDT",
  "last_update_id": 123,
  "bids": [],
  "asks": [],
  "spread": 0.01,
  "mid_price": 1600.0,
  "source": "binance-websocket"
}
```

Malformed subscription messages return an `error` event and do not close the connection.

## Frontend Integration

A single frontend market-data client will:

- Open and reconnect one backend WebSocket.
- Maintain reactive prices for all five symbols.
- Track connection status and last message time.
- Subscribe to the current trade symbol.
- Route candle updates to the chart.
- Route orderbook snapshots to the orderbook component.
- Fall back to existing REST calls during startup or WebSocket outages.

The current five-second price polling and three-second orderbook polling will be removed after
the WebSocket connection is healthy. Low-frequency REST reconciliation may remain as a safety
fallback but will not be the primary data path.

## REST Integration

Existing REST endpoints continue to work:

```text
GET /api/crypto/prices/latest
GET /api/crypto/candles
GET /api/crypto/orderbook
```

They prefer synchronized realtime cache data when available:

- Prices: realtime cache, then Binance REST, then latest DuckDB close.
- Candles: DuckDB history plus current in-memory candle where appropriate.
- Orderbook: synchronized cache, then Binance REST.

No endpoint returns fabricated market data.

## Lifecycle

Backend startup:

1. Initialize MySQL migrations.
2. Initialize DuckDB schema.
3. Start candle persistence worker.
4. Start Binance combined stream client.
5. Run incremental candle gap repair.

Backend shutdown:

1. Stop accepting new realtime work.
2. Close Binance WebSocket.
3. Flush queued closed candles.
4. Stop persistence and broadcast tasks.

## Reconnect Policy

- Initial retry delay: 1 second.
- Exponential delays: 1, 2, 4, 8, 16 seconds.
- Maximum delay: 30 seconds.
- Add small random jitter to prevent synchronized reconnects.
- Reset the backoff after a stable connection.
- Proactively rotate before 24 hours.
- Resynchronize every orderbook after reconnect.
- Run candle gap repair after reconnect.

## Backpressure

- Keep only the latest pending price state; price events may be coalesced.
- Orderbook broadcasts are throttled to a practical frontend rate such as 100-250ms.
- The closed-candle persistence queue is bounded.
- If the candle queue is full, log the condition and trigger gap repair rather than blocking
  the stream indefinitely.
- Slow frontend clients receive the latest snapshot rather than an unbounded event backlog.

## Error Handling

- Binance connection loss marks service status as reconnecting.
- Invalid JSON or unknown stream events are logged and ignored.
- Orderbook sequence gaps trigger symbol-level resynchronization.
- DuckDB write failures do not stop ticker or orderbook processing.
- Frontend disconnects remove their subscription state immediately.
- REST fallback remains available while realtime initialization is incomplete.

## Observability

Expose realtime status through the health API:

```json
{
  "binance_realtime": {
    "status": "connected",
    "connected_at": 1782400000000,
    "last_event_at": 1782400001000,
    "reconnect_count": 0,
    "symbols": {
      "BTCUSDT": {
        "orderbook_synced": true,
        "last_price_at": 1782400001000,
        "last_candle_at": 1782400000000
      }
    }
  }
}
```

Logs must include reconnects, depth resynchronizations, candle persistence failures, and gap
repair results without logging every market event.

## Testing

Backend unit tests:

- Combined stream URL contains all 15 streams.
- Binance event parsing for ticker, kline, and depth.
- Orderbook snapshot bridging and sequential updates.
- Quantity-zero level deletion.
- Sequence-gap resynchronization.
- 100-level trimming.
- Closed candle normalization and idempotent persistence.
- Reconnect backoff and status transitions.
- Frontend subscription protocol validation.

Frontend unit tests:

- One shared WebSocket connection.
- All-symbol price updates.
- Symbol subscription changes.
- Candle and orderbook event routing.
- Reconnect behavior.
- REST fallback before the WebSocket becomes healthy.

Integration tests:

- FastAPI lifespan starts and stops realtime workers.
- Closed candle reaches DuckDB.
- REST routes prefer cache data.
- Browser dashboard and trade screen update without polling.

## Rollout

1. Implement and test in-memory cache and event normalization.
2. Implement orderbook synchronization.
3. Implement Binance stream lifecycle and closed-candle persistence.
4. Add backend WebSocket protocol.
5. Integrate REST cache preference.
6. Add frontend shared WebSocket client.
7. Remove primary polling timers.
8. Verify live prices, candle updates, orderbook sequence, DuckDB writes, reconnect, and gap
   repair.

## Future Extension

The same service boundaries can later support Binance Futures by adding a separate market
adapter and cache namespace. Futures is not part of this implementation.
