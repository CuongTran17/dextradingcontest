import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getCryptoAccount } from '@/services/cryptoTradingApi'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import CryptoDashboard from '@/views/CryptoDashboard.vue'

vi.mock('@/services/authApi', () => ({
  isLoggedIn: () => true,
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  getCryptoAccount: vi.fn(),
}))

vi.mock('@/services/cryptoMarketData', () => ({
  fetchLatestCryptoPrices: vi.fn(),
  getLatestCryptoPrice: vi.fn(() => 3420),
}))

vi.mock('@/components/crypto/PortfolioSummary.vue', () => ({
  default: {
    props: ['account'],
    template: '<div data-test="portfolio-summary">{{ account.equity }}</div>',
  },
}))

vi.mock('@/components/crypto/LeaderboardTable.vue', () => ({
  default: { template: '<div data-test="leaderboard"></div>' },
}))

describe('CryptoDashboard', () => {
  beforeEach(() => {
    vi.mocked(getCryptoAccount).mockReset()
    vi.mocked(getCryptoAccount).mockResolvedValue({
      accountId: 9,
      contestId: 'practice-arena',
      status: 'active',
      cash: 9000,
      initialEquity: 10000,
      equity: 10100,
      realizedPnl: 100,
      unrealizedPnl: 0,
      positions: [],
      orders: [],
    })
    vi.mocked(fetchLatestCryptoPrices).mockResolvedValue({
      BTCUSDT: 59500,
      ETHUSDT: 1570,
      SOLUSDT: 66,
      XRPUSDT: 1.04,
      BNBUSDT: 558,
    })
  })

  it('shows the backend account summary for a signed-in user', async () => {
    const wrapper = mount(CryptoDashboard, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(getCryptoAccount).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.get('[data-test="portfolio-summary"]').text()).toContain('10100')
  })

  it('renders latest backend prices instead of hardcoded fallback prices', async () => {
    const wrapper = mount(CryptoDashboard, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(fetchLatestCryptoPrices).toHaveBeenCalled()
    expect(wrapper.text()).toContain('$1,570.00')
    expect(wrapper.text()).not.toContain('$3,420.00')
  })
})
