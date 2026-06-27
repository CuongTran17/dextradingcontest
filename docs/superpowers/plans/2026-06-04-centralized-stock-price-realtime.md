# Centralized Stock Price Realtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make current stock prices update without page reload across Dashboard, Stock Detail, My Portfolio, Portfolio Alerts, Stock Screener, and price widgets on News Events, while centralizing frontend price state and realtime lifecycle.

**Architecture:** Introduce a lightweight Vue reactive stock-price store, a reference-counted symbol registry, and one application-owned realtime manager. The manager owns the single WebSocket connection, polling fallback, reconnect attempts, and dynamic symbol subscriptions. Pages only retain the symbols they display and read prices from the central store; they never open or close the shared connection.

**Tech Stack:** Vue 3 Composition API, TypeScript, native WebSocket, FastAPI snapshot API, Vitest, jsdom, Vite.

---

## Scope

### In scope

- Automatically update current stock price, change, change percentage, volume, high, low, open, and last-update timestamp.
- One application-level WebSocket connection.
- One polling fallback loop that only requests active symbols.
- Dynamic subscribe and unsubscribe when pages or displayed symbols change.
- Reconnect from polling fallback to WebSocket without reloading the browser.
- Central price state used by:
  - Stock Dashboard
  - Stock Detail
  - My Portfolio
  - Portfolio Alerts
  - Stock Screener
  - Price widgets on News Events
- Connection state display: `realtime`, `polling`, `offline`, and `stale`.

### Out of scope

- Automatic refresh of historical charts.
- Automatic refresh of technical analysis.
- Automatic refresh of company overview, financial statements, news, events, or AI analysis.
- Replacing Vue reactive state with Pinia.
- Backend API contract redesign.
- Changing the existing Market Overview 60-second refresh behavior.

---

## Target Data Flow

```text
App.vue
  -> realtimeManager.start()
       -> WebSocket connected
            -> subscribe active symbols
            -> realtime quote -> stockPriceStore.applyRealtimeQuote()
       -> WebSocket unavailable
            -> polling active symbols
            -> snapshot response -> stockPriceStore.applySnapshots()
       -> retry WebSocket while polling

Page mounted / symbols changed
  -> usePriceSubscription(ownerId, symbols)
       -> symbolRegistry.replaceSymbols(ownerId, symbols)
       -> realtimeManager.syncSubscriptions()

Page unmounted
  -> symbolRegistry.releaseOwner(ownerId)
  -> symbols with reference count zero are unsubscribed
```

---

## File Structure

### New files

- `src/stores/stockPriceStore.ts`
  - Owns normalized current-price state and connection metadata.
- `src/realtime/symbolRegistry.ts`
  - Owns reference-counted active symbol demand by page owner.
- `src/realtime/realtimeManager.ts`
  - Owns WebSocket, polling fallback, retry, and subscription synchronization.
- `src/composables/usePriceSubscription.ts`
  - Connects a Vue component's reactive symbol list to the registry.
- `src/test/setup.ts`
  - Shared frontend unit-test setup.
- `src/stores/__tests__/stockPriceStore.test.ts`
- `src/realtime/__tests__/symbolRegistry.test.ts`
- `src/realtime/__tests__/realtimeManager.test.ts`

### Modified files

- `package.json`
  - Add Vitest scripts and dependencies.
- `vite.config.ts`
  - Add Vitest configuration.
- `src/services/dnseWebSocket.ts`
  - Expose recoverable connection and dynamic subscription behavior.
- `src/App.vue`
  - Start and stop the realtime manager at application lifecycle boundaries.
- `src/composables/useStockData.ts`
  - Keep watchlist, history, and technical compatibility while delegating prices to the new store.
- `src/components/stock/ConnectionStatus.vue`
  - Display centralized connection mode and stale state.
- `src/views/StockDashboard.vue`
- `src/views/StockDetail.vue`
- `src/views/MyPortfolio.vue`
- `src/views/PortfolioAlerts.vue`
- `src/views/StockScreener.vue`
- `src/views/NewsEvents.vue`

---

### Task 1: Add Frontend Unit-Test Harness

**Files:**
- Modify: `package.json`
- Modify: `vite.config.ts`
- Create: `src/test/setup.ts`
- Create: `src/stores/__tests__/stockPriceStore.test.ts`

- [ ] **Step 1: Add Vitest dependencies and scripts**

Add these dev dependencies:

```json
"@vue/test-utils": "^2.4.6",
"jsdom": "^26.1.0",
"vitest": "^3.2.4"
```

Add scripts:

```json
"test:unit": "vitest run",
"test:unit:watch": "vitest"
```

- [ ] **Step 2: Configure Vitest**

In `vite.config.ts`, import the Vitest config type:

```ts
/// <reference types="vitest/config" />
```

Add to `defineConfig`:

```ts
test: {
  environment: 'jsdom',
  setupFiles: ['./src/test/setup.ts'],
  clearMocks: true,
  restoreMocks: true,
},
```

- [ ] **Step 3: Create shared test setup**

Create `src/test/setup.ts`:

```ts
import { afterEach, vi } from 'vitest'

afterEach(() => {
  vi.useRealTimers()
  window.localStorage.clear()
})
```

- [ ] **Step 4: Add an intentionally failing store import test**

Create `src/stores/__tests__/stockPriceStore.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { createStockPriceStore } from '@/stores/stockPriceStore'

describe('stockPriceStore', () => {
  it('starts with no prices and an idle connection', () => {
    const store = createStockPriceStore()

    expect(store.stocksBySymbol).toEqual({})
    expect(store.connectionMode.value).toBe('idle')
  })
})
```

- [ ] **Step 5: Run test to verify it fails**

Run:

```powershell
npm.cmd run test:unit -- src/stores/__tests__/stockPriceStore.test.ts
```

Expected: FAIL because `src/stores/stockPriceStore.ts` does not exist.

- [ ] **Step 6: Commit**

```powershell
git add package.json package-lock.json vite.config.ts src/test/setup.ts src/stores/__tests__/stockPriceStore.test.ts
git commit -m "test: add frontend realtime test harness"
```

---

### Task 2: Add Reference-Counted Symbol Registry

**Files:**
- Create: `src/realtime/symbolRegistry.ts`
- Create: `src/realtime/__tests__/symbolRegistry.test.ts`

- [ ] **Step 1: Write failing registry tests**

Create `src/realtime/__tests__/symbolRegistry.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest'
import { createSymbolRegistry } from '@/realtime/symbolRegistry'

describe('symbolRegistry', () => {
  it('keeps a symbol active while at least one owner retains it', () => {
    const registry = createSymbolRegistry()

    registry.replaceSymbols('dashboard', ['fpt', 'VCB'])
    registry.replaceSymbols('portfolio', ['FPT'])
    registry.releaseOwner('dashboard')

    expect(registry.getActiveSymbols()).toEqual(['FPT'])
    expect(registry.getReferenceCount('FPT')).toBe(1)
  })

  it('notifies only when the active symbol set changes', () => {
    const registry = createSymbolRegistry()
    const listener = vi.fn()
    registry.subscribe(listener)

    registry.replaceSymbols('dashboard', ['FPT', 'FPT'])
    registry.replaceSymbols('dashboard', ['FPT'])
    registry.releaseOwner('dashboard')

    expect(listener).toHaveBeenCalledTimes(2)
    expect(listener).toHaveBeenLastCalledWith([])
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
npm.cmd run test:unit -- src/realtime/__tests__/symbolRegistry.test.ts
```

Expected: FAIL because `createSymbolRegistry` does not exist.

- [ ] **Step 3: Implement the registry**

Create `src/realtime/symbolRegistry.ts`:

```ts
export type SymbolRegistryListener = (symbols: string[]) => void

function normalizeSymbols(symbols: Iterable<string>): string[] {
  return [...new Set(
    [...symbols]
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => /^[A-Z0-9]{2,10}$/.test(symbol)),
  )].sort()
}

export function createSymbolRegistry() {
  const symbolsByOwner = new Map<string, Set<string>>()
  const listeners = new Set<SymbolRegistryListener>()
  let activeSymbols: string[] = []

  function calculateActiveSymbols(): string[] {
    return normalizeSymbols(
      [...symbolsByOwner.values()].flatMap((symbols) => [...symbols]),
    )
  }

  function publishIfChanged(): void {
    const next = calculateActiveSymbols()
    if (next.join('|') === activeSymbols.join('|')) return
    activeSymbols = next
    listeners.forEach((listener) => listener([...activeSymbols]))
  }

  function replaceSymbols(ownerId: string, symbols: Iterable<string>): void {
    symbolsByOwner.set(ownerId, new Set(normalizeSymbols(symbols)))
    publishIfChanged()
  }

  function releaseOwner(ownerId: string): void {
    if (!symbolsByOwner.delete(ownerId)) return
    publishIfChanged()
  }

  function getReferenceCount(symbol: string): number {
    const normalized = symbol.trim().toUpperCase()
    return [...symbolsByOwner.values()].filter((symbols) => symbols.has(normalized)).length
  }

  function subscribe(listener: SymbolRegistryListener): () => void {
    listeners.add(listener)
    return () => listeners.delete(listener)
  }

  return {
    replaceSymbols,
    releaseOwner,
    getActiveSymbols: () => [...activeSymbols],
    getReferenceCount,
    subscribe,
  }
}

export const symbolRegistry = createSymbolRegistry()
```

- [ ] **Step 4: Run registry tests**

Run:

```powershell
npm.cmd run test:unit -- src/realtime/__tests__/symbolRegistry.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/realtime/symbolRegistry.ts src/realtime/__tests__/symbolRegistry.test.ts
git commit -m "feat: add reference-counted symbol registry"
```

---

### Task 3: Add Central Stock Price Store

**Files:**
- Create: `src/stores/stockPriceStore.ts`
- Modify: `src/stores/__tests__/stockPriceStore.test.ts`

- [ ] **Step 1: Extend failing price-store tests**

Replace `src/stores/__tests__/stockPriceStore.test.ts` with:

```ts
import { describe, expect, it } from 'vitest'
import { createStockPriceStore } from '@/stores/stockPriceStore'

describe('stockPriceStore', () => {
  it('applies snapshots by normalized symbol', () => {
    const store = createStockPriceStore()

    store.applySnapshot({
      symbol: 'fpt',
      companyName: 'FPT Corp',
      price: 100,
      change: 2,
      changePercent: 2,
      volume: 10,
      high: 101,
      low: 98,
      open: 99,
      refPrice: 98,
      lastUpdate: '2026-06-04T10:00:00+07:00',
      syncedAt: null,
      priceSource: 'snapshot',
      dataStatus: 'DATA_AVAILABLE',
      logoColor: '#000000',
    })

    expect(store.stocksBySymbol.FPT.price).toBe(100)
  })

  it('accepts valid realtime zero values', () => {
    const store = createStockPriceStore()
    store.applyRealtimeQuote({
      symbol: 'FPT',
      price: 100,
      change: 0,
      changePercent: 0,
      volume: 0,
      high: 100,
      low: 100,
      open: 100,
      time: '2026-06-04T10:01:00+07:00',
    })

    expect(store.stocksBySymbol.FPT.change).toBe(0)
    expect(store.stocksBySymbol.FPT.changePercent).toBe(0)
    expect(store.stocksBySymbol.FPT.volume).toBe(0)
  })

  it('tracks connection mode and freshness timestamps', () => {
    const store = createStockPriceStore()
    store.markConnectionMode('polling')
    store.markRefresh('2026-06-04T10:00:00+07:00')

    expect(store.connectionMode.value).toBe('polling')
    expect(store.lastRefreshAt.value).toBe('2026-06-04T10:00:00+07:00')
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
npm.cmd run test:unit -- src/stores/__tests__/stockPriceStore.test.ts
```

Expected: FAIL because store actions do not exist.

- [ ] **Step 3: Implement the price store**

Create `src/stores/stockPriceStore.ts` with these public contracts:

```ts
import { computed, reactive, ref } from 'vue'
import type { RealtimeQuote } from '@/services/dnseWebSocket'
import type { StockSnapshot } from '@/services/stockBackendApi'

export type PriceConnectionMode = 'idle' | 'connecting' | 'realtime' | 'polling' | 'offline'

export interface StockPriceState {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  volume: number
  high: number
  low: number
  open: number
  refPrice: number
  lastUpdate: string
  syncedAt: string | null
  priceSource: string
  dataStatus: string
  logoColor: string
}

function finiteOr(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export function createStockPriceStore() {
  const stocksBySymbol = reactive<Record<string, StockPriceState>>({})
  const connectionMode = ref<PriceConnectionMode>('idle')
  const backendAvailable = ref(false)
  const error = ref<string | null>(null)
  const lastRefreshAt = ref<string | null>(null)
  const lastRealtimeAt = ref<string | null>(null)

  function applySnapshot(snapshot: StockPriceState | StockSnapshot): void {
    const symbol = snapshot.symbol.toUpperCase()
    stocksBySymbol[symbol] = { ...snapshot, symbol } as StockPriceState
  }

  function applySnapshots(snapshots: Array<StockPriceState | StockSnapshot>): void {
    snapshots.forEach(applySnapshot)
    markRefresh(new Date().toISOString())
  }

  function applyRealtimeQuote(quote: RealtimeQuote): void {
    const symbol = quote.symbol.toUpperCase()
    const existing = stocksBySymbol[symbol]
    const time = quote.time || new Date().toISOString()
    stocksBySymbol[symbol] = {
      symbol,
      companyName: existing?.companyName || symbol,
      price: finiteOr(quote.price, existing?.price ?? 0),
      change: finiteOr(quote.change, existing?.change ?? 0),
      changePercent: finiteOr(quote.changePercent, existing?.changePercent ?? 0),
      volume: finiteOr(quote.volume, existing?.volume ?? 0),
      high: finiteOr(quote.high, existing?.high ?? 0),
      low: finiteOr(quote.low, existing?.low ?? 0),
      open: finiteOr(quote.open, existing?.open ?? 0),
      refPrice: existing?.refPrice ?? 0,
      lastUpdate: time,
      syncedAt: existing?.syncedAt ?? null,
      priceSource: 'dnse_live',
      dataStatus: 'DATA_AVAILABLE',
      logoColor: existing?.logoColor || '#465FFF',
    }
    lastRealtimeAt.value = time
    markRefresh(time)
  }

  function markConnectionMode(mode: PriceConnectionMode): void {
    connectionMode.value = mode
  }

  function markRefresh(time: string): void {
    lastRefreshAt.value = time
  }

  return {
    stocksBySymbol,
    connectionMode,
    backendAvailable,
    error,
    lastRefreshAt,
    lastRealtimeAt,
    activeStocks: computed(() => Object.values(stocksBySymbol)),
    applySnapshot,
    applySnapshots,
    applyRealtimeQuote,
    markConnectionMode,
    markRefresh,
  }
}

export const stockPriceStore = createStockPriceStore()
```

During implementation, reuse the existing snapshot normalization and symbol-color helpers from `useStockData.ts` instead of duplicating them. Move those helpers into the store or a focused `src/stores/stockPriceMapping.ts` module if needed.

- [ ] **Step 4: Run store tests**

Run:

```powershell
npm.cmd run test:unit -- src/stores/__tests__/stockPriceStore.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/stores/stockPriceStore.ts src/stores/__tests__/stockPriceStore.test.ts
git commit -m "feat: add centralized stock price store"
```

---

### Task 4: Make WebSocket Fallback Recoverable

**Files:**
- Modify: `src/services/dnseWebSocket.ts`
- Create: `src/services/__tests__/dnseWebSocket.test.ts`

- [ ] **Step 1: Write failing reconnect and dynamic-subscription tests**

Create `src/services/__tests__/dnseWebSocket.test.ts` using a mock `WebSocket` class. Cover:

```ts
it('sends subscribe immediately when a symbol is added after connection')
it('can reconnect after entering fallback mode')
it('does not remove another callback when one subscriber unsubscribes')
```

The reconnect test must:

1. Exhaust `MAX_RECONNECT_ATTEMPTS`.
2. Observe `fallback`.
3. Call the new public `retryConnection()`.
4. Verify a new WebSocket instance is created.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/dnseWebSocket.test.ts
```

Expected: FAIL because the service cannot leave fallback mode and has no `retryConnection`.

- [ ] **Step 3: Update WebSocket public lifecycle**

Modify `src/services/dnseWebSocket.ts`:

- Add `retryConnection()` that resets `fallbackMode` and reconnect attempts before calling `connect()`.
- Ensure `disconnect()` resets internal fallback state for a future application start.
- Keep subscribers during transient disconnect/reconnect.
- Clear subscribers only during final application shutdown through a new explicit `destroy()` method.
- Preserve dynamic `subscribe()` and `unsubscribe()` behavior.
- Expose current connection state through a readonly getter.

Required public API:

```ts
connect(token?: string): void
retryConnection(): void
disconnect(): void
destroy(): void
subscribe(symbol: string, callback: QuoteCallback): () => void
onConnectionChange(callback: ConnectionCallback): () => void
```

- [ ] **Step 4: Run WebSocket tests**

Run:

```powershell
npm.cmd run test:unit -- src/services/__tests__/dnseWebSocket.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/services/dnseWebSocket.ts src/services/__tests__/dnseWebSocket.test.ts
git commit -m "fix: make websocket fallback recoverable"
```

---

### Task 5: Add Application Realtime Manager

**Files:**
- Create: `src/realtime/realtimeManager.ts`
- Create: `src/realtime/__tests__/realtimeManager.test.ts`

- [ ] **Step 1: Write failing manager tests**

Create tests covering:

```ts
it('starts only one websocket connection')
it('syncs added and removed active symbols')
it('starts one polling loop after websocket fallback')
it('does not overlap polling requests')
it('stops polling when websocket reconnects')
it('polls only active symbols')
```

Use fake timers and injected dependencies:

```ts
const manager = createRealtimeManager({
  registry,
  priceStore,
  webSocketService,
  snapshotApi,
  pollingMs: 5000,
  retryRealtimeMs: 30000,
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
npm.cmd run test:unit -- src/realtime/__tests__/realtimeManager.test.ts
```

Expected: FAIL because `createRealtimeManager` does not exist.

- [ ] **Step 3: Implement the manager**

Create `src/realtime/realtimeManager.ts` with:

```ts
export interface RealtimeManagerDependencies {
  registry: typeof symbolRegistry
  priceStore: typeof stockPriceStore
  webSocketService: typeof dnseWebSocket
  snapshotApi: Pick<typeof stockBackendApi, 'getSnapshots' | 'checkHealth'>
  pollingMs: number
  retryRealtimeMs: number
}
```

Required behavior:

- `start()` is idempotent.
- `stop()` clears all manager timers/listeners and destroys the WebSocket.
- Registry changes reconcile one unsubscribe callback per active symbol.
- Connected mode stops polling and marks `realtime`.
- Fallback mode starts self-scheduling polling and marks `polling`.
- Polling returns immediately when a previous request is still in flight.
- Polling loads only `registry.getActiveSymbols()`.
- While polling, a retry timer calls `webSocketService.retryConnection()`.
- Empty active-symbol sets do not call snapshots.

Required public API:

```ts
start(): Promise<void>
stop(): void
syncSubscriptions(symbols?: string[]): void
pollNow(): Promise<void>
```

- [ ] **Step 4: Run manager tests**

Run:

```powershell
npm.cmd run test:unit -- src/realtime/__tests__/realtimeManager.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/realtime/realtimeManager.ts src/realtime/__tests__/realtimeManager.test.ts
git commit -m "feat: add application realtime manager"
```

---

### Task 6: Move Realtime Lifecycle to App

**Files:**
- Create: `src/composables/usePriceSubscription.ts`
- Create: `src/composables/__tests__/usePriceSubscription.test.ts`
- Modify: `src/App.vue`

- [ ] **Step 1: Write failing subscription composable test**

Test that:

- Mounting retains initial symbols under the supplied owner ID.
- Updating reactive symbols replaces the owner's symbols.
- Unmounting releases the owner.

- [ ] **Step 2: Implement the composable**

Create `src/composables/usePriceSubscription.ts`:

```ts
import { onUnmounted, watch, type WatchSource } from 'vue'
import { symbolRegistry } from '@/realtime/symbolRegistry'

export function usePriceSubscription(
  ownerId: string,
  symbols: WatchSource<Iterable<string>>,
): void {
  watch(
    symbols,
    (nextSymbols) => symbolRegistry.replaceSymbols(ownerId, nextSymbols),
    { immediate: true },
  )

  onUnmounted(() => {
    symbolRegistry.releaseOwner(ownerId)
  })
}
```

- [ ] **Step 3: Move manager lifecycle into `App.vue`**

Update `src/App.vue`:

```ts
import { onMounted, onUnmounted } from 'vue'
import { realtimeManager } from '@/realtime/realtimeManager'

onMounted(() => {
  void realtimeManager.start()
})

onUnmounted(() => {
  realtimeManager.stop()
})
```

- [ ] **Step 4: Run composable tests and build**

Run:

```powershell
npm.cmd run test:unit -- src/composables/__tests__/usePriceSubscription.test.ts
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/App.vue src/composables/usePriceSubscription.ts src/composables/__tests__/usePriceSubscription.test.ts
git commit -m "refactor: move realtime lifecycle to application"
```

---

### Task 7: Add Compatibility Delegation in `useStockData`

**Files:**
- Modify: `src/composables/useStockData.ts`
- Create: `src/composables/__tests__/useStockDataCompatibility.test.ts`

- [ ] **Step 1: Write compatibility tests**

Cover:

- `stocks` is the same reactive object as `stockPriceStore.stocksBySymbol`.
- Existing snapshot loads update the central price store.
- Watchlist behavior remains unchanged.
- Historical and technical methods remain available.
- Page-facing `cleanup()` no longer closes global realtime resources.

- [ ] **Step 2: Delegate price state to the new store**

Modify `src/composables/useStockData.ts`:

- Replace its local `stocks` reactive object with `stockPriceStore.stocksBySymbol`.
- Delegate snapshot and realtime mapping to store actions.
- Keep:
  - watchlist persistence
  - `fetchInitialData`
  - `getHistoricalData`
  - `getTechnicalAnalysis`
- Mark `connectRealtime`, `startPolling`, `stopPolling`, and `cleanup` as compatibility no-ops during page migration.
- Remove those compatibility methods after all consumers are migrated.

- [ ] **Step 3: Run compatibility tests and build**

Run:

```powershell
npm.cmd run test:unit -- src/composables/__tests__/useStockDataCompatibility.test.ts
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/composables/useStockData.ts src/composables/__tests__/useStockDataCompatibility.test.ts
git commit -m "refactor: delegate stock prices to centralized store"
```

---

### Task 8: Migrate Dashboard and Stock Detail

**Files:**
- Modify: `src/views/StockDashboard.vue`
- Modify: `src/views/StockDetail.vue`

- [ ] **Step 1: Migrate Stock Dashboard**

- Read prices and connection state from `stockPriceStore`.
- Register featured and watchlist symbols through `usePriceSubscription`.
- Remove page calls to `connectRealtime`, `startPolling`, and `cleanup`.
- Keep the existing manual refresh action for explicit snapshot reload.

Use a stable owner:

```ts
usePriceSubscription(
  'stock-dashboard',
  () => [...featuredSymbols.value, ...watchlist.value],
)
```

- [ ] **Step 2: Migrate Stock Detail**

- Register only the current route symbol:

```ts
usePriceSubscription('stock-detail', () => [symbol.value])
```

- Remove `addToWatchlist(symbol.value)` from `reloadSymbolData`; viewing a stock must not persist it to the watchlist.
- Remove page calls to `connectRealtime`, `startPolling`, and `cleanup`.
- Keep order-log auto-refresh, history, overview, financial, news, and technical behavior unchanged.

- [ ] **Step 3: Run unit tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/views/StockDashboard.vue src/views/StockDetail.vue
git commit -m "refactor: migrate dashboard and detail to price subscriptions"
```

---

### Task 9: Migrate Portfolio and Alerts

**Files:**
- Modify: `src/views/MyPortfolio.vue`
- Modify: `src/views/PortfolioAlerts.vue`

- [ ] **Step 1: Migrate My Portfolio**

- Remove page-local `currentPrices`.
- Register symbols from loaded portfolio items.
- Calculate P&L from `stockPriceStore.stocksBySymbol`.
- Keep portfolio CRUD and available-symbol loading unchanged.

Required fallback:

```ts
const currentPriceRaw = stocksBySymbol[item.symbol]?.price ?? item.avg_price ?? 0
```

- [ ] **Step 2: Migrate Portfolio Alerts**

- Register the union of position and alert symbols.
- Remove calls that add alert symbols to the persistent watchlist only for realtime.
- Remove page calls to `connectRealtime`, `startPolling`, and `cleanup`.
- Keep alert evaluation as computed state based on central prices.

- [ ] **Step 3: Run unit tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/views/MyPortfolio.vue src/views/PortfolioAlerts.vue
git commit -m "refactor: migrate portfolio prices and alerts to central store"
```

---

### Task 10: Migrate Screener and News Price Widgets

**Files:**
- Modify: `src/views/StockScreener.vue`
- Modify: `src/views/NewsEvents.vue`

- [ ] **Step 1: Migrate Stock Screener**

- Keep technical and fundamental row fields loaded once.
- Register only the selected/displayed screener symbols.
- Derive displayed `price` and `changePercent` from `stockPriceStore`.
- Do not rebuild or refetch technical rows when prices change.

- [ ] **Step 2: Migrate News Events price widgets**

- Keep news and event loading unchanged.
- Register only symbols displayed in the price widget section.
- Remove page calls to `connectRealtime`, `startPolling`, and `cleanup`.

- [ ] **Step 3: Run unit tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add src/views/StockScreener.vue src/views/NewsEvents.vue
git commit -m "refactor: migrate screener and news price widgets"
```

---

### Task 11: Remove Legacy Page-Owned Realtime Lifecycle

**Files:**
- Modify: `src/composables/useStockData.ts`
- Modify: `src/components/stock/ConnectionStatus.vue`
- Modify: any remaining Vue file found by the verification search

- [ ] **Step 1: Search for legacy lifecycle consumers**

Run:

```powershell
rg -n "connectRealtime\(|startPolling\(|stopPolling\(|cleanup\(" src/views src/components src/composables
```

Expected: only the centralized realtime manager owns connection and polling lifecycle.

- [ ] **Step 2: Remove compatibility lifecycle methods**

From `useStockData.ts`, remove:

- `connectRealtime`
- `startPolling`
- `stopPolling`
- shared WebSocket unsubscribe state
- polling timers
- realtime quote persistence timer if it is still browser-owned
- `cleanup`

Keep watchlist, initial snapshots, historical data, and technical analysis compatibility until a separate refactor is justified.

- [ ] **Step 3: Update connection status component**

Use central store connection mode and freshness:

```text
realtime -> Realtime
polling + fresh -> Polling
polling + stale -> Dữ liệu cũ
offline -> Offline
```

Treat data as stale when `lastRefreshAt` exceeds the existing threshold used by `ConnectionStatus.vue`.

- [ ] **Step 4: Run tests and build**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add src/composables/useStockData.ts src/components/stock/ConnectionStatus.vue
git commit -m "refactor: remove legacy page-owned realtime lifecycle"
```

---

### Task 12: Full Verification and Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/frontend-realtime-architecture.md`

- [ ] **Step 1: Document the runtime contract**

Document:

- App owns manager lifecycle.
- Pages own only symbol demand.
- Watchlist is persistent user intent.
- Active subscription is temporary display demand.
- WebSocket is preferred; polling is fallback.
- Only current prices auto-update.

- [ ] **Step 2: Run all frontend verification**

Run:

```powershell
npm.cmd run test:unit
npm.cmd run build
```

Expected: all tests pass and production build succeeds.

- [ ] **Step 3: Run backend regression tests**

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest backend_v2/tests -q
```

Expected: all backend tests pass.

- [ ] **Step 4: Manually verify route transitions**

Verify:

1. Open Dashboard and confirm prices update without reload.
2. Navigate Dashboard -> Stock Detail and confirm connection remains alive.
3. Change Stock Detail symbol and confirm the new symbol receives updates.
4. Add a portfolio item and confirm its price and P&L update.
5. Open Alerts and confirm alert calculations react to price updates.
6. Open Screener and confirm prices update without reloading technical data.
7. Stop WebSocket/backend route and confirm polling fallback starts.
8. Restore WebSocket/backend route and confirm realtime resumes.
9. Confirm browser devtools shows only one WebSocket connection and no overlapping snapshot requests.

- [ ] **Step 5: Commit documentation**

```powershell
git add README.md docs/frontend-realtime-architecture.md
git commit -m "docs: document centralized frontend realtime architecture"
```

---

## Acceptance Criteria

- Current prices update without browser reload on all in-scope pages.
- Navigating between pages does not close or duplicate the WebSocket.
- Adding or removing displayed symbols updates WebSocket subscriptions dynamically.
- A symbol remains subscribed while at least one page owner still needs it.
- WebSocket failure switches to polling automatically.
- Polling performs no overlapping requests and only loads active symbols.
- The application attempts and succeeds at returning from polling to realtime.
- My Portfolio and Stock Screener no longer retain stale page-local price snapshots.
- Viewing Stock Detail no longer adds the symbol to persistent watchlist.
- News, financial, technical, historical, and AI data do not gain new automatic refresh behavior.
- `npm.cmd run test:unit`, `npm.cmd run build`, and backend regression tests pass.

---

## Rollback Strategy

- Each migration task is independently revertible.
- Keep `useStockData.ts` compatibility delegation until all page migrations pass.
- If a page migration fails manual verification, revert only that page to compatibility reads while keeping the centralized manager and store.
- Do not remove legacy lifecycle code until the final search confirms no page depends on it.

---

## Self-Review

**Spec coverage:** The plan covers centralized current-price state, application-owned realtime lifecycle, dynamic reference-counted subscriptions, recoverable fallback polling, migration of all agreed price-consuming pages, and final cleanup.

**Scope check:** Historical charts, technical analysis, news/events fetching, financial statements, AI analysis, backend redesign, and Pinia migration remain explicitly out of scope.

**Placeholder scan:** No `TBD`, `TODO`, or unspecified implementation phases remain.

**Type consistency:** `symbolRegistry`, `stockPriceStore`, `realtimeManager`, and `usePriceSubscription` use consistent public method names throughout the plan.
