import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  getCryptoAccount,
  placeCryptoMarketOrder,
} from '@/services/cryptoTradingApi'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import {
  connectCryptoRealtime,
  cryptoRealtimeState,
  subscribeCryptoRealtimeSymbol,
} from '@/services/cryptoRealtime'
import CryptoTrade from '@/views/CryptoTrade.vue'

const routeParams = vi.hoisted(() => ({ value: { symbol: 'BTCUSDT' } as Record<string, string> }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: routeParams.value }),
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
    name: 'OrderTicket',
    props: ['disabled', 'disabledReason'],
    emits: ['submit'],
    template: '<button data-test="submit-order" :disabled="disabled" @click="$emit(\'submit\', { side: \'buy\', quantity: 0.01 })">Buy Sell</button>',
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
}))

vi.mock('@/services/cryptoRealtime', () => ({
  connectCryptoRealtime: vi.fn(),
  subscribeCryptoRealtimeSymbol: vi.fn(),
  cryptoRealtimeState: {
    prices: { BTCUSDT: 66000 },
    status: 'connected',
    selectedSymbol: 'BTCUSDT',
    lastMessageAt: 0,
  },
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
    routeParams.value = { symbol: 'BTCUSDT' }
    vi.spyOn(window, 'setInterval')
    vi.mocked(getCryptoAccount).mockReset()
    vi.mocked(placeCryptoMarketOrder).mockReset()
    vi.mocked(connectCryptoRealtime).mockReset()
    vi.mocked(subscribeCryptoRealtimeSymbol).mockReset()
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

  it('uses the contest id from the scoped route for account and orders', async () => {
    routeParams.value = { contestId: 'summer-crypto-cup', symbol: 'ETHUSDT' }
    vi.mocked(getCryptoAccount).mockResolvedValue({
      ...accountFixture,
      contestId: 'summer-crypto-cup',
    })

    const wrapper = mount(CryptoTrade)
    await flushPromises()

    expect(getCryptoAccount).toHaveBeenCalledWith('summer-crypto-cup')

    await wrapper.get('[data-test="submit-order"]').trigger('click')
    await flushPromises()

    expect(placeCryptoMarketOrder).toHaveBeenCalledWith({
      contestId: 'summer-crypto-cup',
      clientOrderId: 'web-001',
      symbol: 'ETHUSDT',
      side: 'buy',
      quantity: 0.01,
    })
  })

  it('passes disabled state and reason when account is frozen', async () => {
    vi.mocked(getCryptoAccount).mockResolvedValue({
      ...accountFixture,
      status: 'frozen',
    })

    const wrapper = mount(CryptoTrade)
    await flushPromises()

    const ticket = wrapper.getComponent({ name: 'OrderTicket' })
    expect(ticket.props('disabled')).toBe(true)
    expect(ticket.props('disabledReason')).toContain('locked')
  })

  it('subscribes to realtime prices without starting a price polling timer', async () => {
    mount(CryptoTrade)
    await flushPromises()

    expect(connectCryptoRealtime).toHaveBeenCalledTimes(1)
    expect(subscribeCryptoRealtimeSymbol).toHaveBeenCalledWith('BTCUSDT')
    expect(fetchLatestCryptoPrices).toHaveBeenCalledTimes(1)
    expect(window.setInterval).not.toHaveBeenCalled()
    expect(cryptoRealtimeState.prices.BTCUSDT).toBe(66000)
  })

  it('shows realtime connection status in the trade header', async () => {
    const wrapper = mount(CryptoTrade)
    await flushPromises()

    expect(wrapper.get('[data-test="realtime-status"]').text()).toContain('Live')
  })
})
