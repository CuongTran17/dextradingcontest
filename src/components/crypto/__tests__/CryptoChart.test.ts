import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import CryptoChart from '@/components/crypto/CryptoChart.vue'
import {
  fetchCryptoCandlesWithSource,
  fetchCryptoIndicator,
} from '@/services/cryptoMarketData'

const chartMocks = vi.hoisted(() => {
  const series = {
    setData: vi.fn(),
    update: vi.fn(),
  }
  const charts: Array<{
    addSeries: ReturnType<typeof vi.fn>
    clearCrosshairPosition: ReturnType<typeof vi.fn>
    setCrosshairPosition: ReturnType<typeof vi.fn>
    timeScaleApi: {
      fitContent: ReturnType<typeof vi.fn>
      setVisibleLogicalRange: ReturnType<typeof vi.fn>
      subscribeVisibleLogicalRangeChange: ReturnType<typeof vi.fn>
      unsubscribeVisibleLogicalRangeChange: ReturnType<typeof vi.fn>
    }
    subscribeCrosshairMove: ReturnType<typeof vi.fn>
    unsubscribeCrosshairMove: ReturnType<typeof vi.fn>
    remove: ReturnType<typeof vi.fn>
  }> = []
  return {
    charts,
    series,
    addSeries: vi.fn(() => series),
    createChart: vi.fn(() => {
      const chart = {
        addSeries: vi.fn(() => series),
        clearCrosshairPosition: vi.fn(),
        setCrosshairPosition: vi.fn(),
        timeScaleApi: {
          fitContent: vi.fn(),
          setVisibleLogicalRange: vi.fn(),
          subscribeVisibleLogicalRangeChange: vi.fn(),
          unsubscribeVisibleLogicalRangeChange: vi.fn(),
        },
        timeScale: vi.fn(),
        subscribeCrosshairMove: vi.fn(),
        unsubscribeCrosshairMove: vi.fn(),
        remove: vi.fn(),
      }
      chart.timeScale.mockReturnValue(chart.timeScaleApi)
      charts.push(chart)
      return chart
    }),
  }
})

vi.mock('lightweight-charts', () => ({
  CandlestickSeries: 'CandlestickSeries',
  HistogramSeries: 'HistogramSeries',
  LineSeries: 'LineSeries',
  createChart: chartMocks.createChart,
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
    chartMocks.charts.length = 0
    chartMocks.createChart.mockClear()
    chartMocks.series.setData.mockClear()
    chartMocks.series.update.mockClear()
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
    expect(chartMocks.createChart).toHaveBeenCalledTimes(2)
    expect(chartMocks.series.setData).toHaveBeenCalledWith([
      { time: 1, value: 0.2, color: '#10b981' },
    ])
    expect(chartMocks.series.setData).toHaveBeenCalledWith([{ time: 1, value: 1.2 }])
    expect(chartMocks.series.setData).toHaveBeenCalledWith([{ time: 1, value: 1.0 }])
    expect(wrapper.get('[data-test="indicator-panel-MACD"]').text()).toContain('MACD 12 26 close 9 EMA EMA')
    expect(wrapper.text()).toContain('1.20')
    expect(wrapper.text()).toContain('0.20')
  })

  it('synchronizes crosshair and visible range between price and MACD charts', async () => {
    const wrapper = mount(CryptoChart, {
      props: { symbol: 'BTCUSDT', timeframe: '1m' },
    })
    await flushPromises()

    await wrapper.get('[data-test="indicator-picker-button"]').trigger('click')
    await wrapper.get('[data-test="indicator-option-MACD"]').trigger('click')
    await flushPromises()

    const [priceChart, macdChart] = chartMocks.charts
    expect(priceChart.subscribeCrosshairMove).toHaveBeenCalledTimes(1)
    expect(macdChart.subscribeCrosshairMove).toHaveBeenCalledTimes(1)
    expect(priceChart.timeScaleApi.subscribeVisibleLogicalRangeChange).toHaveBeenCalledTimes(1)
    expect(macdChart.timeScaleApi.subscribeVisibleLogicalRangeChange).toHaveBeenCalledTimes(1)

    const priceCrosshairHandler = priceChart.subscribeCrosshairMove.mock.calls[0][0]
    priceCrosshairHandler({ time: 1 })
    expect(macdChart.setCrosshairPosition).toHaveBeenCalledWith(1.2, 1, chartMocks.series)

    const macdCrosshairHandler = macdChart.subscribeCrosshairMove.mock.calls[0][0]
    macdCrosshairHandler({ time: 1 })
    expect(priceChart.setCrosshairPosition).toHaveBeenCalledWith(1.5, 1, chartMocks.series)

    const priceRangeHandler = priceChart.timeScaleApi.subscribeVisibleLogicalRangeChange.mock.calls[0][0]
    priceRangeHandler({ from: 0, to: 10 })
    expect(macdChart.timeScaleApi.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 0, to: 10 })

    const macdRangeHandler = macdChart.timeScaleApi.subscribeVisibleLogicalRangeChange.mock.calls[0][0]
    macdRangeHandler({ from: 2, to: 8 })
    expect(priceChart.timeScaleApi.setVisibleLogicalRange).toHaveBeenCalledWith({ from: 2, to: 8 })
  })
})
