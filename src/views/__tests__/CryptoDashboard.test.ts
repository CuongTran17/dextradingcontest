import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getCryptoAccount } from '@/services/cryptoTradingApi'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import { fetchContestLeaderboard, fetchContests } from '@/services/cryptoContestApi'
import CryptoDashboard from '@/views/CryptoDashboard.vue'

vi.mock('@/services/authApi', () => ({
  isLoggedIn: () => true,
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  getCryptoAccount: vi.fn(),
}))

vi.mock('@/services/cryptoMarketData', () => ({
  fetchLatestCryptoPrices: vi.fn(),
}))

vi.mock('@/services/cryptoContestApi', () => ({
  fetchContestLeaderboard: vi.fn(),
  fetchContests: vi.fn(),
}))

vi.mock('@/components/crypto/PortfolioSummary.vue', () => ({
  default: {
    props: ['account'],
    template: '<div data-test="portfolio-summary">{{ account.equity }}</div>',
  },
}))

vi.mock('@/components/crypto/LeaderboardTable.vue', () => ({
  default: {
    props: ['rows'],
    template: '<div data-test="leaderboard">{{ rows.map((row) => row.user).join(",") }}</div>',
  },
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
    vi.mocked(fetchContests).mockReset()
    vi.mocked(fetchContests).mockResolvedValue([
      {
        id: 'backend-cup',
        title: 'Backend Cup',
        status: 'active',
        rawStatus: 'active',
        mode: 'contest',
        initialCapital: 15000,
        symbols: ['BTCUSDT'],
        startsAt: '2026-07-01T00:00:00+00:00',
        endsAt: '2026-07-10T00:00:00+00:00',
        participantCount: 7,
      },
    ])
    vi.mocked(fetchContestLeaderboard).mockReset()
    vi.mocked(fetchContestLeaderboard).mockResolvedValue([
      {
        rank: 1,
        user: 'Backend Student',
        equity: 15100,
        pnl: 100,
        roi: 0.66,
        volume: 1000,
        tradeCount: 2,
        lastTrade: 'BTCUSDT buy',
      },
    ])
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

  it('loads active contests and leaderboard rows from the backend', async () => {
    const wrapper = mount(CryptoDashboard, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })
    await flushPromises()

    expect(fetchContests).toHaveBeenCalled()
    expect(fetchContestLeaderboard).toHaveBeenCalledWith('backend-cup')
    expect(wrapper.text()).toContain('Backend Cup')
    expect(wrapper.get('[data-test="leaderboard"]').text()).toContain('Backend Student')
  })
})
