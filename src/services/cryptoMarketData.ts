import type { Candle, CryptoOrderBook, CryptoSymbol, MarketDataSource, Timeframe } from '@/types/crypto'

const BASE_PRICES: Record<CryptoSymbol, number> = {
  BTCUSDT: 64250,
  ETHUSDT: 3420,
  SOLUSDT: 148,
}

const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '1h': 3600,
  '4h': 14400,
  '1D': 86400,
}

function getSymbolPhase(symbol: CryptoSymbol): number {
  return symbol.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
}

export function getLatestCryptoPrice(symbol: CryptoSymbol): number {
  return BASE_PRICES[symbol]
}

export async function fetchLatestCryptoPrices(
  symbols: CryptoSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT'],
): Promise<Partial<Record<CryptoSymbol, number>>> {
  try {
    const prices = await fetchJson<Partial<Record<CryptoSymbol, number>>>('/api/crypto/prices/latest')
    return symbols.reduce<Partial<Record<CryptoSymbol, number>>>((result, symbol) => {
      result[symbol] = prices[symbol] ?? BASE_PRICES[symbol]
      return result
    }, {})
  } catch {
    return symbols.reduce<Partial<Record<CryptoSymbol, number>>>((result, symbol) => {
      result[symbol] = BASE_PRICES[symbol]
      return result
    }, {})
  }
}

export function getCryptoCandles(
  symbol: CryptoSymbol,
  timeframe: Timeframe,
  count: number,
): Candle[] {
  const safeCount = Math.max(0, Math.floor(count))
  const basePrice = BASE_PRICES[symbol]
  const stepSeconds = TIMEFRAME_SECONDS[timeframe]
  const phase = getSymbolPhase(symbol)
  const lastClosedTime = Math.floor(Date.now() / 1000 / stepSeconds) * stepSeconds
  const firstTime = lastClosedTime - (safeCount - 1) * stepSeconds

  return Array.from({ length: safeCount }, (_, index) => {
    const wave = Math.sin((index + phase) / 4)
    const trend = (index - safeCount / 2) * basePrice * 0.0007
    const open = basePrice + trend + wave * basePrice * 0.006
    const close = open + Math.cos((index + phase) / 3) * basePrice * 0.003
    const high = Math.max(open, close) * 1.002
    const low = Math.min(open, close) * 0.998

    return {
      time: firstTime + index * stepSeconds,
      open,
      high,
      low,
      close,
      volume: 1000 + Math.abs(wave) * 5000 + index * 25,
    }
  })
}

export async function fetchCryptoCandles(
  symbol: CryptoSymbol,
  timeframe: Timeframe,
  count: number,
): Promise<Candle[]> {
  const result = await fetchCryptoCandlesWithSource(symbol, timeframe, count)
  return result.candles
}

export async function fetchCryptoCandlesWithSource(
  symbol: CryptoSymbol,
  timeframe: Timeframe,
  count: number,
): Promise<{ candles: Candle[]; source: MarketDataSource }> {
  try {
    const candles = await fetchJson<Candle[]>(
      `/api/crypto/candles?symbol=${symbol}&timeframe=${encodeURIComponent(timeframe)}&limit=${count}`,
    )
    return { candles, source: 'binance' }
  } catch {
    return { candles: getCryptoCandles(symbol, timeframe, count), source: 'mock' }
  }
}

export async function fetchCryptoOrderBook(
  symbol: CryptoSymbol,
  limit = 100,
): Promise<CryptoOrderBook> {
  try {
    return await fetchJson<CryptoOrderBook>(`/api/crypto/orderbook?symbol=${symbol}&limit=${limit}`)
  } catch {
    return getMockOrderBook(symbol, limit)
  }
}

export function getMockOrderBook(symbol: CryptoSymbol, limit = 100): CryptoOrderBook {
  const count = Math.max(1, Math.floor(limit))
  const midPrice = BASE_PRICES[symbol]
  const bids = Array.from({ length: count }, (_, index) => {
    const price = midPrice - (index + 1) * midPrice * 0.0001
    const quantity = 0.1 + index * 0.03
    return { price, quantity, total: price * quantity }
  })
  const asks = Array.from({ length: count }, (_, index) => {
    const price = midPrice + (index + 1) * midPrice * 0.0001
    const quantity = 0.1 + index * 0.03
    return { price, quantity, total: price * quantity }
  })

  return {
    symbol,
    last_update_id: null,
    bids,
    asks,
    spread: asks[0].price - bids[0].price,
    mid_price: midPrice,
    source: 'mock',
  }
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Crypto market data request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}
