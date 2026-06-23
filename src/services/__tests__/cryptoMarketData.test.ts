import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  fetchCryptoCandles,
  fetchCryptoCandlesWithSource,
  fetchCryptoOrderBook,
  fetchLatestCryptoPrices,
  getCryptoCandles,
  getLatestCryptoPrice,
} from '@/services/cryptoMarketData'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cryptoMarketData', () => {
  it('returns a positive latest BTCUSDT price', () => {
    expect(getLatestCryptoPrice('BTCUSDT')).toBeGreaterThan(0)
  })

  it('returns the requested number of candles with increasing time', () => {
    const candles = getCryptoCandles('BTCUSDT', '1h', 20)

    expect(candles).toHaveLength(20)
    for (let index = 1; index < candles.length; index += 1) {
      expect(candles[index].time).toBeGreaterThan(candles[index - 1].time)
    }
  })

  it('fetches latest prices from the backend crypto API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ BTCUSDT: 65000 }), { status: 200 })),
    )

    await expect(fetchLatestCryptoPrices(['BTCUSDT'])).resolves.toEqual({ BTCUSDT: 65000 })
  })

  it('falls back to mock order book when backend market depth is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))

    const book = await fetchCryptoOrderBook('BTCUSDT', 10)

    expect(book.source).toBe('mock')
    expect(book.bids).toHaveLength(10)
    expect(book.asks).toHaveLength(10)
    expect(book.spread).toBeGreaterThan(0)
  })

  it('fetches candles from the backend crypto API', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify([{ time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }]),
            { status: 200 },
          ),
      ),
    )

    await expect(fetchCryptoCandles('BTCUSDT', '1h', 1)).resolves.toEqual([
      { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    ])
  })

  it('marks candles as mock when backend candles are unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))

    const result = await fetchCryptoCandlesWithSource('BTCUSDT', '1h', 3)

    expect(result.source).toBe('mock')
    expect(result.candles).toHaveLength(3)
  })
})
