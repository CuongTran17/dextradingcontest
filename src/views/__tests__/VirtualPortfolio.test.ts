import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getCryptoAccount } from '@/services/cryptoTradingApi'
import VirtualPortfolio from '@/views/VirtualPortfolio.vue'

vi.mock('@/services/cryptoTradingApi', () => ({
  getCryptoAccount: vi.fn(),
}))

vi.mock('@/components/crypto/PortfolioSummary.vue', () => ({
  default: {
    props: ['account'],
    template: '<div data-test="portfolio-summary">{{ account.cash }}</div>',
  },
}))

describe('VirtualPortfolio', () => {
  beforeEach(() => {
    vi.mocked(getCryptoAccount).mockReset()
    vi.mocked(getCryptoAccount).mockResolvedValue({
      accountId: 9,
      contestId: 'practice-arena',
      status: 'active',
      cash: 9750,
      initialEquity: 10000,
      equity: 10020,
      realizedPnl: 20,
      unrealizedPnl: 0,
      positions: [],
      orders: [],
    })
  })

  it('loads the persisted practice account from the backend', async () => {
    const wrapper = mount(VirtualPortfolio)
    await flushPromises()

    expect(getCryptoAccount).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.get('[data-test="portfolio-summary"]').text()).toContain('9750')
    expect(wrapper.text()).not.toContain('Reset Practice')
  })
})
