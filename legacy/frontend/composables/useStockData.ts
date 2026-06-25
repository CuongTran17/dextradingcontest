/**
 * useStockData composable
 * =======================
 * Data strategy:
 * 1) FastAPI backend snapshots, refreshed from DNSE OpenAPI during market session
 * 2) Backend WebSocket /api/ws/dnse, backed by the same DNSE-fed snapshot cache
 * 3) Direct browser DNSE fallback only when backend is unavailable
 */

import { ref, computed, watch } from 'vue'
import { dnseApi, type StockQuote, type OHLCVData } from '@/services/dnseApi'
import {
  isBackendAvailableHealth,
  stockBackendApi,
  type CompanyOverview,
  type StockSnapshot,
  type TechnicalResponse,
} from '@/services/stockBackendApi'
import { stockPriceStore } from '@/stores/stockPriceStore'

export const VN30_TICKERS = [
  'ACB', 'BCM', 'BID', 'BVH', 'CTG',
  'FPT', 'GAS', 'GVR', 'HDB', 'HPG',
  'MBB', 'MSN', 'MWG', 'PLX', 'POW',
  'SAB', 'SHB', 'SSB', 'SSI', 'STB',
  'TCB', 'TPB', 'VCB', 'VHM', 'VIB',
  'VIC', 'VJC', 'VNM', 'VPB', 'VRE',
]

export const FEATURED_STOCKS = ['FPT', 'VNM', 'VCB', 'HPG']

const WATCHLIST_STORAGE_KEY = 'stockai_watchlist'

export interface StockState {
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

const SYMBOL_COLOR_OVERRIDES: Record<string, string> = {
  FPT: '#F37021',
  VNM: '#0072BC',
  VCB: '#00553E',
  HPG: '#E31E24',
  MBB: '#1B3C87',
  TCB: '#E31E24',
  VIC: '#003366',
  MSN: '#E31E24',
}

const SYMBOL_COLOR_PALETTE = [
  '#465FFF', '#0EA5E9', '#22C55E', '#F59E0B', '#EF4444',
  '#06B6D4', '#8B5CF6', '#14B8A6', '#EC4899', '#64748B',
]

function getSymbolColor(symbol: string): string {
  const upper = symbol.toUpperCase()
  if (SYMBOL_COLOR_OVERRIDES[upper]) {
    return SYMBOL_COLOR_OVERRIDES[upper]
  }

  let hash = 0
  for (const char of upper) {
    hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  }

  return SYMBOL_COLOR_PALETTE[hash % SYMBOL_COLOR_PALETTE.length]
}

const OVERVIEW_NAME_KEYS = [
  'company_name',
  'companyName',
  'name',
  'company',
  'company_full_name',
  'fullname',
  'short_name',
]

function toNumber(value: unknown, fallback: number = 0): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/,/g, ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return fallback
}

function extractCompanyName(overview: CompanyOverview | null, symbol: string): string {
  if (!overview) return symbol

  for (const key of OVERVIEW_NAME_KEYS) {
    const value = overview[key]
    if (typeof value === 'string' && value.trim().length > 0) {
      return value.trim()
    }
  }

  return symbol
}

function createEmptyState(symbol: string, companyName: string = symbol): StockState {
  return {
    symbol,
    companyName,
    price: 0,
    change: 0,
    changePercent: 0,
    volume: 0,
    high: 0,
    low: 0,
    open: 0,
    refPrice: 0,
    lastUpdate: new Date().toISOString(),
    syncedAt: null,
    priceSource: 'no_data',
    dataStatus: 'NO_DATA_IN_SNAPSHOT',
    logoColor: getSymbolColor(symbol),
  }
}

function snapshotToState(snapshot: StockSnapshot): StockState {
  const symbol = snapshot.symbol.toUpperCase()
  return {
    symbol,
    companyName: snapshot.companyName || symbol,
    price: toNumber(snapshot.price),
    change: toNumber(snapshot.change),
    changePercent: toNumber(snapshot.changePercent),
    volume: toNumber(snapshot.volume),
    high: toNumber(snapshot.high),
    low: toNumber(snapshot.low),
    open: toNumber(snapshot.open),
    refPrice: toNumber(snapshot.refPrice),
    lastUpdate: snapshot.lastUpdate || new Date().toISOString(),
    syncedAt: snapshot.syncedAt || null,
    priceSource: snapshot.priceSource || 'no_data',
    dataStatus: snapshot.dataStatus || (toNumber(snapshot.price) > 0 ? 'DATA_AVAILABLE' : 'NO_DATA_IN_SNAPSHOT'),
    logoColor: getSymbolColor(symbol),
  }
}

function hasUsableSnapshotPrice(snapshot: StockSnapshot): boolean {
  return toNumber(snapshot.price) > 0 && snapshot.dataStatus !== 'NO_DATA_IN_SNAPSHOT'
}

function normalizeSymbols(symbols: string[]): string[] {
  return [...new Set(
    symbols
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => /^[A-Z0-9]{2,10}$/.test(symbol)),
  )]
}

function loadSavedWatchlist(): string[] {
  try {
    const raw = window.localStorage.getItem(WATCHLIST_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    const symbols = normalizeSymbols(parsed)
    return symbols
  } catch {
    return []
  }
}

function createStockDataStore() {
  const stocks = stockPriceStore.stocksBySymbol as Record<string, StockState>
  const watchlist = ref<string[]>(loadSavedWatchlist())
  const featuredSymbols = ref<string[]>([...FEATURED_STOCKS])
  const isLoading = ref(false)
  const error = ref<string | null>(null)
  const lastRefresh = ref<Date>(new Date())
  const lastDataSyncAt = ref<string | null>(null)
  const backendAvailable = ref(false)

  const featuredStocks = computed(() =>
    featuredSymbols.value.map((symbol) => stocks[symbol]).filter(Boolean),
  )

  const watchlistStocks = computed(() =>
    watchlist.value.map((symbol) => stocks[symbol]).filter(Boolean),
  )

  const allRequestedSymbols = computed(() =>
    normalizeSymbols([...featuredSymbols.value, ...watchlist.value]),
  )

  const hasUsableData = computed(() =>
    Object.values(stocks).some((stock) => stock.price > 0 && stock.dataStatus !== 'NO_DATA_IN_SNAPSHOT'),
  )

  watch(watchlist, (symbols) => {
    try {
      window.localStorage.setItem(WATCHLIST_STORAGE_KEY, JSON.stringify(symbols))
    } catch {
      // Ignore storage failures; the in-memory watchlist remains usable.
    }
  }, { deep: true })

  async function checkBackendAvailability(): Promise<boolean> {
    try {
      const health = await stockBackendApi.checkHealth()
      backendAvailable.value = isBackendAvailableHealth(health)
    } catch {
      backendAvailable.value = false
    }

    return backendAvailable.value
  }

  function updateLastDataSyncFromStocks(): void {
    const candidates = Object.values(stocks)
      .map((item) => item.syncedAt)
      .filter((value): value is string => Boolean(value))

    if (candidates.length === 0) {
      return
    }

    const latest = candidates.reduce((best, current) => (
      new Date(current).getTime() > new Date(best).getTime() ? current : best
    ))

    lastDataSyncAt.value = latest
  }

  async function fetchBackendSnapshot(symbol: string): Promise<StockState | null> {
    const upperSymbol = symbol.toUpperCase()

    try {
      const response = await stockBackendApi.getSnapshots([upperSymbol])
      const snapshot = response.data.find((item) => item.symbol.toUpperCase() === upperSymbol)
      if (snapshot && hasUsableSnapshotPrice(snapshot)) {
        return snapshotToState(snapshot)
      }
    } catch {
      // Continue to compatibility fallback below.
    }

    const [overviewResult, historyResult] = await Promise.allSettled([
      stockBackendApi.getCompanyOverview(upperSymbol),
      stockBackendApi.getHistory(upperSymbol, undefined, undefined, 2),
    ])

    const overview = overviewResult.status === 'fulfilled' ? overviewResult.value : null
    const companyName = extractCompanyName(overview, upperSymbol)

    if (historyResult.status !== 'fulfilled' || historyResult.value.data.length === 0) {
      return createEmptyState(upperSymbol, companyName)
    }

    const candles = historyResult.value.data
    const latest = candles[candles.length - 1]
    const previous = candles.length > 1 ? candles[candles.length - 2] : latest

    const latestClose = toNumber(latest.close)
    const refPrice = toNumber(previous.close, toNumber(latest.open, latestClose))
    const change = latestClose - refPrice
    const changePercent = refPrice > 0 ? (change / refPrice) * 100 : 0

    return {
      symbol: upperSymbol,
      companyName,
      price: latestClose,
      change,
      changePercent,
      volume: toNumber(latest.volume),
      high: toNumber(latest.high, latestClose),
      low: toNumber(latest.low, latestClose),
      open: toNumber(latest.open, latestClose),
      refPrice,
      lastUpdate: latest.time || new Date().toISOString(),
      syncedAt: historyResult.value.last_synced_at || historyResult.value.data[historyResult.value.data.length - 1]?.time || null,
      priceSource: 'eod_snapshot',
      dataStatus: latestClose > 0 ? 'DATA_AVAILABLE' : 'NO_DATA_IN_SNAPSHOT',
      logoColor: getSymbolColor(upperSymbol),
    }
  }

  async function loadFromBackend(symbols: string[]): Promise<boolean> {
    const bySymbol = new Map<string, StockState>()

    try {
      const batch = await stockBackendApi.getSnapshots(symbols)
      if (batch.last_synced_at) {
        lastDataSyncAt.value = batch.last_synced_at
      } else if (batch.cached_at) {
        lastDataSyncAt.value = batch.cached_at
      }

      batch.data.forEach((item) => {
        if (hasUsableSnapshotPrice(item)) {
          bySymbol.set(item.symbol.toUpperCase(), snapshotToState(item))
        }
      })
    } catch {
      // Continue with per-symbol fallback.
    }

    const missingSymbols = symbols.filter((symbol) => !bySymbol.has(symbol.toUpperCase()))

    if (missingSymbols.length > 0) {
      const fallbacks = await Promise.all(
        missingSymbols.map(async (symbol) => {
          try {
            return await fetchBackendSnapshot(symbol)
          } catch {
            return null
          }
        }),
      )

      fallbacks.forEach((snapshot) => {
        if (snapshot) {
          bySymbol.set(snapshot.symbol.toUpperCase(), snapshot)
        }
      })
    }

    const usable = Array.from(bySymbol.values())
    usable.forEach((snapshot) => {
      stocks[snapshot.symbol] = snapshot
    })

    if (usable.length > 0) {
      lastRefresh.value = new Date()
      updateLastDataSyncFromStocks()
      return true
    }

    return false
  }

  async function loadFromDnse(symbols: string[]): Promise<boolean> {
    try {
      const quotes = await dnseApi.getMultipleQuotes(symbols)
      if (quotes.length === 0) return false

      quotes.forEach((quote) => {
        stocks[quote.symbol] = quoteToState(quote)
      })

      lastRefresh.value = new Date()
      return true
    } catch {
      return false
    }
  }

  function applyEmptyData(symbols: string[]): void {
    symbols.forEach((symbol) => {
      const upperSymbol = symbol.toUpperCase()
      if (!stocks[upperSymbol]) {
        stocks[upperSymbol] = createEmptyState(upperSymbol)
      }
    })

    lastRefresh.value = new Date()
  }

  async function fetchInitialData(): Promise<void> {
    isLoading.value = true
    error.value = null

    const allSymbols = allRequestedSymbols.value

    try {
      await checkBackendAvailability()

      let loaded = false

      if (backendAvailable.value) {
        loaded = await loadFromBackend(allSymbols)
      }

      if (!loaded && !backendAvailable.value) {
        loaded = await loadFromDnse(allSymbols)
      }

      if (!loaded) {
        applyEmptyData(allSymbols)
        error.value = backendAvailable.value
          ? 'Không tải được dữ liệu từ backend cache.'
          : 'Backend không khả dụng và DNSE không phản hồi.'
      }
    } finally {
      isLoading.value = false
    }
  }

  async function loadSymbolData(symbol: string): Promise<void> {
    const upperSymbol = symbol.toUpperCase()

    if (backendAvailable.value) {
      try {
        const backendSnapshot = await fetchBackendSnapshot(upperSymbol)
        if (backendSnapshot) {
          stocks[upperSymbol] = backendSnapshot
          if (backendSnapshot.syncedAt) {
            lastDataSyncAt.value = backendSnapshot.syncedAt
          }
          return
        }
      } catch {
        // Skip DNSE REST fallback when backend is available to avoid browser CORS issues.
      }
    } else {
      try {
        const quote = await dnseApi.getStockQuote(upperSymbol)
        stocks[upperSymbol] = quoteToState(quote)
        return
      } catch {
        // Keep empty-state fallback.
      }
    }

    stocks[upperSymbol] = createEmptyState(upperSymbol)
  }

  function addToWatchlist(symbol: string): void {
    const upperSymbol = symbol.trim().toUpperCase()

    if (/^[A-Z0-9]{2,10}$/.test(upperSymbol) && !watchlist.value.includes(upperSymbol)) {
      watchlist.value.push(upperSymbol)
      void loadSymbolData(upperSymbol)
    }
  }

  function removeFromWatchlist(symbol: string): void {
    watchlist.value = watchlist.value.filter((item) => item !== symbol.toUpperCase())
  }

  function clearWatchlist(): void {
    watchlist.value = []
  }

  async function getHistoricalData(
    symbol: string,
    resolution: string = '1D',
    fromTs?: number,
    toTs?: number,
    refresh: boolean = false,
  ): Promise<OHLCVData[]> {
    if (backendAvailable.value) {
      try {
        const resp = await stockBackendApi.getHistory(symbol, undefined, undefined, 365, refresh)
        if (resp.last_synced_at) {
          lastDataSyncAt.value = resp.last_synced_at
        }

        if (resp.data.length > 0) {
          return resp.data.map((item) => ({
            time: item.time,
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
            volume: item.volume,
          }))
        }
      } catch {
        // Skip DNSE REST fallback when backend is available to avoid browser CORS issues.
      }
    } else {
      try {
        return await dnseApi.getHistoricalData(symbol, resolution, fromTs, toTs)
      } catch {
        return []
      }
    }

    return []
  }

  async function getTechnicalAnalysis(
    symbol: string,
    limit: number = 365,
  ): Promise<TechnicalResponse | null> {
    try {
      const response = await stockBackendApi.getTechnicalAnalysis(symbol, undefined, undefined, limit)
      backendAvailable.value = true
      return response
    } catch {
      return null
    }
  }

  function quoteToState(quote: StockQuote): StockState {
    return {
      symbol: quote.symbol,
      companyName: quote.companyName,
      price: quote.price,
      change: quote.change,
      changePercent: quote.changePercent,
      volume: quote.volume,
      high: quote.high,
      low: quote.low,
      open: quote.open,
      refPrice: quote.refPrice,
      lastUpdate: quote.updatedAt,
      syncedAt: null,
      priceSource: 'dnse_live',
      dataStatus: 'DATA_AVAILABLE',
      logoColor: getSymbolColor(quote.symbol),
    }
  }

  return {
    stocks,
    watchlist,
    featuredSymbols,
    isConnected: computed(() => stockPriceStore.connectionMode.value === 'realtime'),
    isLoading,
    error,
    lastRefresh: computed(() => (
      stockPriceStore.lastRefreshAt.value
        ? new Date(stockPriceStore.lastRefreshAt.value)
        : lastRefresh.value
    )),
    lastDataSyncAt,
    backendAvailable: stockPriceStore.backendAvailable,
    connectionMode: stockPriceStore.connectionMode,
    hasUsableData,

    featuredStocks,
    watchlistStocks,

    fetchInitialData,
    loadSymbolData,
    addToWatchlist,
    removeFromWatchlist,
    clearWatchlist,
    getHistoricalData,
    getTechnicalAnalysis,
  }
}

const stockDataStore = createStockDataStore()

export function useStockData() {
  return stockDataStore
}
