import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchContestLeaderboard } from '@/services/cryptoContestApi'
import ContestLeaderboard from '@/views/ContestLeaderboard.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoContestApi', () => ({
  fetchContestLeaderboard: vi.fn(),
}))

describe('ContestLeaderboard', () => {
  beforeEach(() => {
    vi.mocked(fetchContestLeaderboard).mockReset()
    vi.mocked(fetchContestLeaderboard).mockResolvedValue([
      {
        rank: 1,
        user: 'Student B',
        equity: 11000,
        pnl: 1000,
        roi: 10,
        volume: 5000,
        tradeCount: 2,
        lastTrade: 'BTCUSDT buy',
      },
    ])
  })

  it('renders backend leaderboard rows', async () => {
    const wrapper = mount(ContestLeaderboard)
    await flushPromises()
    await flushPromises()

    expect(fetchContestLeaderboard).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.text()).toContain('Student B')
    expect(wrapper.text()).toContain('$11,000.00')
  })
})
