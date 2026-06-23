import { computed, reactive, ref } from 'vue'
import type { RealtimeQuote } from '@/services/dnseWebSocket'

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

  function applySnapshot(snapshot: StockPriceState): void {
    const symbol = snapshot.symbol.toUpperCase()
    stocksBySymbol[symbol] = { ...snapshot, symbol }
  }

  function applySnapshots(snapshots: StockPriceState[]): void {
    snapshots.forEach(applySnapshot)
    const latest = snapshots.reduce<string | null>((current, snapshot) => {
      const timestamp = Date.parse(snapshot.lastUpdate)
      if (Number.isNaN(timestamp)) return current
      if (!current || timestamp > Date.parse(current)) return snapshot.lastUpdate
      return current
    }, null)
    if (latest) {
      markRefresh(latest)
    }
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
