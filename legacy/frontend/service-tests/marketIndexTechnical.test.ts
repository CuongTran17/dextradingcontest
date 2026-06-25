import { describe, expect, it } from 'vitest'
import type { MarketIndexHistoryResponse } from '@/services/stockBackendApi'
import { buildMarketIndexTechnicalResponse } from '@/services/marketIndexTechnical'

function makeHistoryResponse(count: number): MarketIndexHistoryResponse {
  return {
    symbol: 'VNINDEX',
    name: 'VN-Index',
    count,
    source: 'test',
    data_status: 'DATA_AVAILABLE',
    data: Array.from({ length: count }, (_, index) => {
      const close = 1200 + index * 3
      return {
        time: `2026-01-${String((index % 28) + 1).padStart(2, '0')}`,
        open: close - 2,
        high: close + 4,
        low: close - 5,
        close,
        volume: 1000000 + index * 1000,
      }
    }),
  }
}

describe('buildMarketIndexTechnicalResponse', () => {
  it('converts market index history into technical chart data', () => {
    const technical = buildMarketIndexTechnicalResponse(makeHistoryResponse(80))

    expect(technical.symbol).toBe('VNINDEX')
    expect(technical.count).toBe(80)
    expect(technical.ohlcv.close).toHaveLength(80)
    expect(technical.indicators.sma_20).toHaveLength(80)
    expect(technical.indicators.rsi_14).toHaveLength(80)
    expect(technical.indicators.macd_line).toHaveLength(80)
    expect(technical.indicators.bb_upper.at(-1)).toBeGreaterThan(technical.indicators.bb_lower.at(-1) || 0)
    expect(['bullish', 'bearish']).toContain(technical.signals.macd)
    expect(['strong_buy', 'buy', 'neutral', 'sell', 'strong_sell']).toContain(technical.signals.summary)
  })
})
