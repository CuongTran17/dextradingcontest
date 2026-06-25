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

  it('does not invent order book depth when backend market depth is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))

    await expect(fetchCryptoOrderBook('BTCUSDT', 10)).rejects.toThrow(
      'Crypto market data request failed: 503',
    )
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

  it('does not invent candles when backend candles are unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))

    await expect(fetchCryptoCandlesWithSource('BTCUSDT', '1h', 3)).rejects.toThrow(
      'Crypto market data request failed: 503',
    )
  })

  it('returns no fake latest prices when the backend is unavailable', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('', { status: 503 })))

    await expect(fetchLatestCryptoPrices(['ETHUSDT'])).resolves.toEqual({})
  })
})
