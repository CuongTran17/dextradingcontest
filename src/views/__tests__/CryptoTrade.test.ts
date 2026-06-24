import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getCryptoAccount,
  placeCryptoMarketOrder,
} from '@/services/cryptoTradingApi'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import CryptoTrade from '@/views/CryptoTrade.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { symbol: 'BTCUSDT' } }),
  useRouter: () => ({ push: vi.fn() }),
}))

vi.mock('@/components/crypto/CryptoChart.vue', () => ({
  default: { template: '<div data-test="crypto-chart">BTCUSDT chart</div>' },
}))

vi.mock('@/components/crypto/OrderBook.vue', () => ({
  default: { template: '<div data-test="order-book">Order Book BTCUSDT</div>' },
}))

vi.mock('@/components/crypto/OrderTicket.vue', () => ({
  default: {
    emits: ['submit'],
    template: '<button data-test="submit-order" @click="$emit(\'submit\', { side: \'buy\', quantity: 0.01 })">Buy Sell</button>',
  },
}))

vi.mock('@/services/cryptoMarketData', () => ({
  fetchLatestCryptoPrices: vi.fn().mockResolvedValue({
    BTCUSDT: 65000,
    ETHUSDT: 3000,
    SOLUSDT: 150,
    XRPUSDT: 0.5,
    BNBUSDT: 600,
  }),
  getLatestCryptoPrice: vi.fn((symbol: string) => ({
    BTCUSDT: 65000,
    ETHUSDT: 3000,
    SOLUSDT: 150,
    XRPUSDT: 0.5,
    BNBUSDT: 600,
  })[symbol]),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  getCryptoAccount: vi.fn(),
  joinCryptoContest: vi.fn(),
  placeCryptoMarketOrder: vi.fn(),
}))

const accountFixture = {
  accountId: 9,
  contestId: 'practice-arena',
  status: 'active' as const,
  cash: 10000,
  initialEquity: 10000,
  equity: 10000,
  realizedPnl: 0,
  unrealizedPnl: 0,
  positions: [],
  orders: [],
}

describe('CryptoTrade', () => {
  beforeEach(() => {
    vi.mocked(getCryptoAccount).mockReset()
    vi.mocked(placeCryptoMarketOrder).mockReset()
    vi.mocked(fetchLatestCryptoPrices).mockResolvedValue({
      BTCUSDT: 65000,
      ETHUSDT: 3000,
      SOLUSDT: 150,
      XRPUSDT: 0.5,
      BNBUSDT: 600,
    })
    vi.mocked(getCryptoAccount).mockResolvedValue(accountFixture)
    vi.mocked(placeCryptoMarketOrder).mockResolvedValue({
      id: '12',
      contestId: 'practice-arena',
      symbol: 'BTCUSDT',
      side: 'buy',
      quantity: 0.01,
      executionPrice: 65000,
      notional: 650,
      fee: 0.65,
      slippage: 0,
      createdAt: '2026-06-25T00:00:00+00:00',
    })
    vi.stubGlobal('crypto', { randomUUID: () => 'web-001' })
  })

  it('renders simulator safety language and BTCUSDT order controls', () => {
    const wrapper = mount(CryptoTrade)

    expect(wrapper.text()).toContain('Educational simulator')
    expect(wrapper.text()).toContain('BTCUSDT')
    expect(wrapper.text()).toContain('Buy')
    expect(wrapper.text()).toContain('Sell')
    expect(wrapper.text()).toContain('Order Book')
  })

  it('loads the backend account and refreshes it after an order', async () => {
    const wrapper = mount(CryptoTrade)
    await flushPromises()

    expect(getCryptoAccount).toHaveBeenCalledWith('practice-arena')

    await wrapper.get('[data-test="submit-order"]').trigger('click')
    await flushPromises()

    expect(placeCryptoMarketOrder).toHaveBeenCalledWith({
      contestId: 'practice-arena',
      clientOrderId: 'web-001',
      symbol: 'BTCUSDT',
      side: 'buy',
      quantity: 0.01,
    })
    expect(getCryptoAccount).toHaveBeenCalledTimes(2)
  })
})
