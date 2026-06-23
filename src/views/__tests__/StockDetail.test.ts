import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import StockDetail from '../StockDetail.vue'
import { getMyPortfolio } from '@/services/authApi'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { symbol: 'FPT' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/components/layout/AdminLayout.vue', () => ({
  default: { template: '<main><slot /></main>' },
}))

vi.mock('@/components/stock/PortfolioChart.vue', () => ({
  default: { name: 'PortfolioChart', template: '<div data-test="portfolio-chart">Portfolio Performance</div>' },
}))

vi.mock('@/components/stock/TechnicalAnalysisChart.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/components/stock/TradingViewChart.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/components/stock/OrderLog.vue', () => ({
  default: { template: '<div />' },
}))

vi.mock('@/composables/usePriceSubscription', () => ({
  usePriceSubscription: vi.fn(),
}))

vi.mock('@/composables/useStockData', () => ({
  VN30_TICKERS: ['FPT', 'MBB'],
  useStockData: () => ({
    stocks: {},
    fetchInitialData: vi.fn().mockResolvedValue(undefined),
    getTechnicalAnalysis: vi.fn(),
  }),
}))

vi.mock('@/services/authApi', () => ({
  getMyPortfolio: vi.fn(),
}))

vi.mock('@/services/stockBackendApi', () => ({
  stockBackendApi: {
    getCompanyOverview: vi.fn(async () => null),
    getFinancials: vi.fn(async () => ({ data: [] })),
    getGoogleNews: vi.fn(async () => ({ data: [] })),
    getMarketEvents: vi.fn(async () => ({ data: [] })),
    getHistory: vi.fn(async () => ({ data: [] })),
    getIntraday: vi.fn(async () => ({ data: [] })),
    getOrderLog: vi.fn(async () => ({ ticks: [], count: 0, is_in_session: false })),
  },
}))

describe('StockDetail', () => {
  beforeEach(() => {
    vi.mocked(getMyPortfolio).mockReset()
    vi.mocked(getMyPortfolio).mockResolvedValue({ count: 0, items: [] })
  })

  it('does not show portfolio performance when the current symbol is not in the portfolio', async () => {
    const wrapper = mount(StockDetail)
    await flushPromises()

    expect(wrapper.find('[data-test="portfolio-chart"]').exists()).toBe(false)
  })

  it('shows portfolio performance when the current symbol has a holding', async () => {
    vi.mocked(getMyPortfolio).mockResolvedValueOnce({
      count: 1,
      items: [
        {
          id: 1,
          symbol: 'FPT',
          quantity: 100,
          avg_price: 90,
          tp_price: null,
          sl_price: null,
          note: null,
        },
      ],
    })

    const wrapper = mount(StockDetail)
    await flushPromises()

    expect(wrapper.find('[data-test="portfolio-chart"]').exists()).toBe(true)
  })
})
