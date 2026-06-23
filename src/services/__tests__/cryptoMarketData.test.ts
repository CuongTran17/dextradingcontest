import { describe, expect, it } from 'vitest'

import { getCryptoCandles, getLatestCryptoPrice } from '@/services/cryptoMarketData'

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
})
