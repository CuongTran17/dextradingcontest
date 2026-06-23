import { describe, expect, it } from 'vitest'
import { createStockPriceStore } from '@/stores/stockPriceStore'

describe('stockPriceStore', () => {
  it('applies snapshots by normalized symbol', () => {
    const store = createStockPriceStore()

    store.applySnapshot({
      symbol: 'fpt',
      companyName: 'FPT Corp',
      price: 100,
      change: 2,
      changePercent: 2,
      volume: 10,
      high: 101,
      low: 98,
      open: 99,
      refPrice: 98,
      lastUpdate: '2026-06-04T10:00:00+07:00',
      syncedAt: null,
      priceSource: 'snapshot',
      dataStatus: 'DATA_AVAILABLE',
      logoColor: '#000000',
    })

    expect(store.stocksBySymbol.FPT.price).toBe(100)
  })

  it('accepts valid realtime zero values', () => {
    const store = createStockPriceStore()
    store.applyRealtimeQuote({
      symbol: 'FPT',
      price: 100,
      change: 0,
      changePercent: 0,
      volume: 0,
      high: 100,
      low: 100,
      open: 100,
      time: '2026-06-04T10:01:00+07:00',
    })

    expect(store.stocksBySymbol.FPT.change).toBe(0)
    expect(store.stocksBySymbol.FPT.changePercent).toBe(0)
    expect(store.stocksBySymbol.FPT.volume).toBe(0)
  })

  it('tracks connection mode and freshness timestamps', () => {
    const store = createStockPriceStore()
    store.markConnectionMode('polling')
    store.markRefresh('2026-06-04T10:00:00+07:00')

    expect(store.connectionMode.value).toBe('polling')
    expect(store.lastRefreshAt.value).toBe('2026-06-04T10:00:00+07:00')
  })

  it('uses the newest snapshot data timestamp as freshness', () => {
    const store = createStockPriceStore()
    const baseSnapshot = {
      companyName: 'Company',
      price: 100,
      change: 0,
      changePercent: 0,
      volume: 10,
      high: 100,
      low: 100,
      open: 100,
      refPrice: 100,
      syncedAt: null,
      priceSource: 'snapshot',
      dataStatus: 'DATA_AVAILABLE',
      logoColor: '#000000',
    }

    store.applySnapshots([
      { ...baseSnapshot, symbol: 'FPT', lastUpdate: '2026-06-04T14:44:00+07:00' },
      { ...baseSnapshot, symbol: 'VCB', lastUpdate: '2026-06-04T14:45:00+07:00' },
    ])

    expect(store.lastRefreshAt.value).toBe('2026-06-04T14:45:00+07:00')
  })
})
