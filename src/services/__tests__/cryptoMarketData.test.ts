import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  fetchCryptoCandles,
  fetchCryptoCandlesWithSource,
  fetchCryptoIndicator,
  fetchCryptoOrderBook,
  fetchLatestCryptoPrices,
} from '@/services/cryptoMarketData'

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('cryptoMarketData', () => {
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

  it('fetches precomputed indicators from the backend crypto API', async () => {
    const fetchSpy = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            symbol: 'BTCUSDT',
            timeframe: '1m',
            indicator: 'MACD',
            params: { fast: 12, slow: 26, signal: 9 },
            points: [{ time: 1, macd: 1, signal: 0.5, histogram: 0.5 }],
          }),
          { status: 200 },
        ),
    )
    vi.stubGlobal('fetch', fetchSpy)

    await expect(fetchCryptoIndicator('BTCUSDT', '1m', 'MACD', 120)).resolves.toEqual({
      symbol: 'BTCUSDT',
      timeframe: '1m',
      indicator: 'MACD',
      params: { fast: 12, slow: 26, signal: 9 },
      points: [{ time: 1, macd: 1, signal: 0.5, histogram: 0.5 }],
    })
    expect(fetchSpy).toHaveBeenCalledWith(
      '/api/crypto/indicators?symbol=BTCUSDT&timeframe=1m&indicator=MACD&limit=120',
    )
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
