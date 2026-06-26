import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CryptoChart from '@/components/crypto/CryptoChart.vue'
import {
  fetchCryptoCandlesWithSource,
  fetchCryptoIndicator,
} from '@/services/cryptoMarketData'

vi.mock('lightweight-charts', () => ({
  CandlestickSeries: 'CandlestickSeries',
  createChart: vi.fn(() => ({
    addSeries: vi.fn(() => ({
      setData: vi.fn(),
      update: vi.fn(),
    })),
    timeScale: vi.fn(() => ({ fitContent: vi.fn() })),
    remove: vi.fn(),
  })),
}))

vi.mock('@/services/cryptoRealtime', () => ({
  onCryptoRealtimeCandle: vi.fn(() => vi.fn()),
}))

vi.mock('@/services/cryptoMarketData', () => ({
  fetchCryptoCandlesWithSource: vi.fn(),
  fetchCryptoIndicator: vi.fn(),
}))

describe('CryptoChart', () => {
  beforeEach(() => {
    vi.mocked(fetchCryptoCandlesWithSource).mockResolvedValue({
      source: 'binance',
      candles: [{ time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 }],
    })
    vi.mocked(fetchCryptoIndicator).mockResolvedValue({
      symbol: 'BTCUSDT',
      timeframe: '1m',
      indicator: 'MACD',
      params: { fast: 12, slow: 26, signal: 9 },
      points: [{ time: 1, macd: 1.2, signal: 1.0, histogram: 0.2 }],
    })
  })

  it('opens a searchable indicator picker and renders a MACD panel from backend data', async () => {
    const wrapper = mount(CryptoChart, {
      props: { symbol: 'BTCUSDT', timeframe: '1m' },
    })
    await flushPromises()

    await wrapper.get('[data-test="indicator-picker-button"]').trigger('click')
    await wrapper.get('[data-test="indicator-search"]').setValue('macd')
    await wrapper.get('[data-test="indicator-option-MACD"]').trigger('click')
    await flushPromises()

    expect(fetchCryptoIndicator).toHaveBeenCalledWith('BTCUSDT', '1m', 'MACD', 120)
    expect(wrapper.get('[data-test="indicator-panel-MACD"]').text()).toContain('MACD 12 26 close 9 EMA EMA')
    expect(wrapper.text()).toContain('1.20')
    expect(wrapper.text()).toContain('0.20')
  })
})
