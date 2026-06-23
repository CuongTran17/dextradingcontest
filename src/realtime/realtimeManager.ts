import { dnseWebSocket, type RealtimeQuote } from '@/services/dnseWebSocket'
import {
  isBackendAvailableHealth,
  stockBackendApi,
  type StockSnapshot,
} from '@/services/stockBackendApi'
import { stockPriceStore, type StockPriceState } from '@/stores/stockPriceStore'
import { symbolRegistry } from '@/realtime/symbolRegistry'

type ConnectionStatus = 'connected' | 'disconnected' | 'error' | 'fallback'

interface RegistryLike {
  getActiveSymbols(): string[]
  subscribe(listener: (symbols: string[]) => void): () => void
}

interface PriceStoreLike {
  backendAvailable: { value: boolean }
  error: { value: string | null }
  applySnapshots(snapshots: StockPriceState[]): void
  applyRealtimeQuote(quote: RealtimeQuote): void
  markConnectionMode(mode: 'idle' | 'connecting' | 'realtime' | 'polling' | 'offline'): void
}

interface WebSocketLike {
  connect(): void
  retryConnection(): void
  destroy(): void
  subscribe(symbol: string, callback: (quote: RealtimeQuote) => void): () => void
  onConnectionChange(callback: (status: ConnectionStatus) => void): () => void
}

interface SnapshotApiLike {
  checkHealth(): Promise<{ status: string }>
  getSnapshots(symbols: string[]): Promise<{ data: StockSnapshot[] }>
}

export interface RealtimeManagerDependencies {
  registry: RegistryLike
  priceStore: PriceStoreLike
  webSocketService: WebSocketLike
  snapshotApi: SnapshotApiLike
  pollingMs: number
  retryRealtimeMs: number
}

function snapshotToPriceState(snapshot: StockSnapshot): StockPriceState {
  return {
    symbol: snapshot.symbol.toUpperCase(),
    companyName: snapshot.companyName || snapshot.symbol.toUpperCase(),
    price: Number(snapshot.price) || 0,
    change: Number(snapshot.change) || 0,
    changePercent: Number(snapshot.changePercent) || 0,
    volume: Number(snapshot.volume) || 0,
    high: Number(snapshot.high) || 0,
    low: Number(snapshot.low) || 0,
    open: Number(snapshot.open) || 0,
    refPrice: Number(snapshot.refPrice) || 0,
    lastUpdate: snapshot.lastUpdate || new Date().toISOString(),
    syncedAt: snapshot.syncedAt || null,
    priceSource: snapshot.priceSource || 'snapshot',
    dataStatus: snapshot.dataStatus || 'DATA_AVAILABLE',
    logoColor: '#465FFF',
  }
}

export function createRealtimeManager(dependencies: RealtimeManagerDependencies) {
  const { registry, priceStore, webSocketService, snapshotApi, pollingMs, retryRealtimeMs } = dependencies
  const symbolUnsubscribers = new Map<string, () => void>()
  let unsubscribeRegistry: (() => void) | null = null
  let unsubscribeConnection: (() => void) | null = null
  let pollingTimer: ReturnType<typeof setTimeout> | null = null
  let retryTimer: ReturnType<typeof setTimeout> | null = null
  let pollInFlight: Promise<void> | null = null
  let pollingActive = false
  let started = false

  function clearPollingTimer(): void {
    if (!pollingTimer) return
    clearTimeout(pollingTimer)
    pollingTimer = null
  }

  function clearRetryTimer(): void {
    if (!retryTimer) return
    clearTimeout(retryTimer)
    retryTimer = null
  }

  function schedulePoll(): void {
    clearPollingTimer()
    pollingTimer = setTimeout(async () => {
      await pollNow()
      if (started) schedulePoll()
    }, pollingMs)
  }

  function scheduleRealtimeRetry(): void {
    clearRetryTimer()
    retryTimer = setTimeout(() => {
      if (!started) return
      webSocketService.retryConnection()
      scheduleRealtimeRetry()
    }, retryRealtimeMs)
  }

  function startPolling(): void {
    pollingActive = true
    priceStore.markConnectionMode('polling')
    void pollNow()
    schedulePoll()
    scheduleRealtimeRetry()
  }

  function stopPolling(): void {
    pollingActive = false
    clearPollingTimer()
    clearRetryTimer()
  }

  function syncSubscriptions(symbols: string[] = registry.getActiveSymbols()): void {
    const wanted = new Set(symbols)
    for (const [symbol, unsubscribe] of symbolUnsubscribers) {
      if (wanted.has(symbol)) continue
      unsubscribe()
      symbolUnsubscribers.delete(symbol)
    }
    for (const symbol of wanted) {
      if (symbolUnsubscribers.has(symbol)) continue
      symbolUnsubscribers.set(
        symbol,
        webSocketService.subscribe(symbol, (quote) => priceStore.applyRealtimeQuote(quote)),
      )
    }
  }

  async function pollNow(): Promise<void> {
    if (pollInFlight) return pollInFlight
    const symbols = registry.getActiveSymbols()
    if (symbols.length === 0) return
    pollInFlight = (async () => {
      try {
        const response = await snapshotApi.getSnapshots(symbols)
        if (!started || !pollingActive) return
        priceStore.applySnapshots(response.data.map(snapshotToPriceState))
        priceStore.backendAvailable.value = true
        priceStore.error.value = null
        priceStore.markConnectionMode('polling')
      } catch {
        if (!started || !pollingActive) return
        priceStore.backendAvailable.value = false
        priceStore.error.value = 'Không thể cập nhật giá từ backend.'
        priceStore.markConnectionMode('offline')
      } finally {
        pollInFlight = null
      }
    })()
    return pollInFlight
  }

  async function start(): Promise<void> {
    if (started) return
    started = true
    priceStore.markConnectionMode('connecting')
    unsubscribeRegistry = registry.subscribe(syncSubscriptions)
    unsubscribeConnection = webSocketService.onConnectionChange((status) => {
      if (status === 'connected') {
        stopPolling()
        priceStore.markConnectionMode('realtime')
      } else if (status === 'fallback') {
        startPolling()
      } else if (status === 'disconnected') {
        priceStore.markConnectionMode('connecting')
      } else if (status === 'error') {
        priceStore.markConnectionMode('offline')
      }
    })
    syncSubscriptions()
    webSocketService.connect()
    try {
      const health = await snapshotApi.checkHealth()
      if (!started) return
      priceStore.backendAvailable.value = isBackendAvailableHealth(health)
    } catch {
      if (!started) return
      priceStore.backendAvailable.value = false
    }
  }

  function stop(): void {
    if (!started) return
    started = false
    stopPolling()
    unsubscribeRegistry?.()
    unsubscribeRegistry = null
    unsubscribeConnection?.()
    unsubscribeConnection = null
    symbolUnsubscribers.forEach((unsubscribe) => unsubscribe())
    symbolUnsubscribers.clear()
    webSocketService.destroy()
    priceStore.markConnectionMode('idle')
  }

  return { start, stop, syncSubscriptions, pollNow }
}

const configuredPollingMs = Math.max(Number(import.meta.env.VITE_BACKEND_POLLING_MS || 5000), 5000)

export const realtimeManager = createRealtimeManager({
  registry: symbolRegistry,
  priceStore: stockPriceStore,
  webSocketService: dnseWebSocket,
  snapshotApi: stockBackendApi,
  pollingMs: configuredPollingMs,
  retryRealtimeMs: 30000,
})
