import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchContest } from '@/services/cryptoContestApi'
import { joinCryptoContest } from '@/services/cryptoTradingApi'
import ContestDetail from '@/views/ContestDetail.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  joinCryptoContest: vi.fn(),
}))

vi.mock('@/services/cryptoContestApi', () => ({
  fetchContest: vi.fn(),
}))

describe('ContestDetail', () => {
  beforeEach(() => {
    vi.mocked(fetchContest).mockReset()
    vi.mocked(fetchContest).mockResolvedValue({
      id: 'practice-arena',
      title: 'Practice Arena From API',
      status: 'practice',
      mode: 'practice',
      initialCapital: 10000,
      symbols: ['BTCUSDT'],
      startsAt: '2026-06-01T00:00:00+00:00',
      endsAt: '2026-07-01T00:00:00+00:00',
      participantCount: 2,
    })
    vi.mocked(joinCryptoContest).mockReset()
    vi.mocked(joinCryptoContest).mockResolvedValue({
      accountId: 9,
      contestId: 'practice-arena',
      status: 'active',
      cash: 10000,
      initialEquity: 10000,
      equity: 10000,
      realizedPnl: 0,
      unrealizedPnl: 0,
      positions: [],
      orders: [],
    })
  })

  it('loads contest detail from the backend', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(fetchContest).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.text()).toContain('Practice Arena From API')
  })

  it('joins the selected contest through the backend', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(joinCryptoContest).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.get('button').text()).toContain('Joined')
  })
})
