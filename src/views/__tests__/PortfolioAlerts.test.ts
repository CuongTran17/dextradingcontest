import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PortfolioAlerts from '../PortfolioAlerts.vue'
import { getMyPortfolio } from '@/services/authApi'

vi.mock('@/components/layout/AdminLayout.vue', () => ({
  default: { template: '<main><slot /></main>' },
}))

vi.mock('@/services/authApi', () => ({
  getMyPortfolio: vi.fn().mockResolvedValue({ count: 0, items: [] }),
}))

vi.mock('@/composables/usePriceSubscription', () => ({
  usePriceSubscription: vi.fn((_key: string, symbols: () => string[]) => {
    symbols()
  }),
}))

vi.mock('@/composables/useStockData', () => ({
  useStockData: () => ({
    stocks: {},
    fetchInitialData: vi.fn(),
    loadSymbolData: vi.fn(),
  }),
}))

describe('PortfolioAlerts', () => {
  beforeEach(() => {
    vi.mocked(getMyPortfolio).mockReset()
    vi.mocked(getMyPortfolio).mockResolvedValue({ count: 0, items: [] })
  })

  it('does not render demo portfolio rows when the portfolio API is empty', async () => {
    const wrapper = mount(PortfolioAlerts)
    await flushPromises()

    expect(wrapper.text()).not.toContain('FPT')
    expect(wrapper.text()).not.toContain('VCB')
    expect(wrapper.text()).toContain('Chưa có vị thế')
  })

  it('renders TP and SL alerts from real portfolio items', async () => {
    vi.mocked(getMyPortfolio).mockResolvedValueOnce({
      count: 1,
      items: [
        {
          id: 1,
          symbol: 'MBB',
          quantity: 1000,
          avg_price: 23.5,
          tp_price: 28,
          sl_price: 21,
          note: null,
        },
      ],
    })

    const wrapper = mount(PortfolioAlerts)
    await flushPromises()

    expect(wrapper.text()).toContain('MBB')
    expect(wrapper.text()).toContain('TP')
    expect(wrapper.text()).toContain('SL')
    expect(wrapper.text()).not.toContain('VCB')
  })
})
