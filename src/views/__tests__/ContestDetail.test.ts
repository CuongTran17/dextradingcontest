import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { joinCryptoContest } from '@/services/cryptoTradingApi'
import ContestDetail from '@/views/ContestDetail.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  joinCryptoContest: vi.fn(),
}))

describe('ContestDetail', () => {
  beforeEach(() => {
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

  it('joins the selected contest through the backend', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(joinCryptoContest).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.get('button').text()).toContain('Joined')
  })
})
