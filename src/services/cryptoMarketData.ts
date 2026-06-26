import type {
  Candle,
  CryptoIndicator,
  CryptoIndicatorResponse,
  CryptoOrderBook,
  CryptoSymbol,
  MarketDataSource,
  Timeframe,
} from '@/types/crypto'

export async function fetchLatestCryptoPrices(
  symbols: CryptoSymbol[] = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT'],
): Promise<Partial<Record<CryptoSymbol, number>>> {
  try {
    const prices = await fetchJson<Partial<Record<CryptoSymbol, number>>>('/api/crypto/prices/latest')
    return symbols.reduce<Partial<Record<CryptoSymbol, number>>>((result, symbol) => {
      const price = prices[symbol]
      if (typeof price === 'number' && Number.isFinite(price) && price > 0) {
        result[symbol] = price
      }
      return result
    }, {})
  } catch {
    return {}
  }
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
  const candles = await fetchJson<Candle[]>(
    `/api/crypto/candles?symbol=${symbol}&timeframe=${encodeURIComponent(timeframe)}&limit=${count}`,
  )
  return { candles, source: 'binance' }
}

export async function fetchCryptoOrderBook(
  symbol: CryptoSymbol,
  limit = 100,
): Promise<CryptoOrderBook> {
  return fetchJson<CryptoOrderBook>(`/api/crypto/orderbook?symbol=${symbol}&limit=${limit}`)
}

export async function fetchCryptoIndicator(
  symbol: CryptoSymbol,
  timeframe: Exclude<Timeframe, '1D'>,
  indicator: CryptoIndicator,
  limit = 300,
): Promise<CryptoIndicatorResponse> {
  return fetchJson<CryptoIndicatorResponse>(
    `/api/crypto/indicators?symbol=${symbol}&timeframe=${timeframe}&indicator=${indicator}&limit=${limit}`,
  )
}

async function fetchJson<T>(path: string): Promise<T> {
  const response = await fetch(path)
  if (!response.ok) {
    throw new Error(`Crypto market data request failed: ${response.status}`)
  }
  return response.json() as Promise<T>
}
