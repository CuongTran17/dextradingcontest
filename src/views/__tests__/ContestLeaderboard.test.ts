import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref } from 'vue'

import { useLeaderboardRealtime } from '@/composables/useLeaderboardRealtime'
import ContestLeaderboard from '@/views/ContestLeaderboard.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/composables/useLeaderboardRealtime', () => ({
  useLeaderboardRealtime: vi.fn(),
}))

describe('ContestLeaderboard', () => {
  beforeEach(() => {
    vi.mocked(useLeaderboardRealtime).mockReset()
    vi.mocked(useLeaderboardRealtime).mockReturnValue({
      rows: ref([
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
      ]),
      sortBy: ref('equity'),
      status: ref('connected'),
      lastUpdated: ref(new Date()),
      setSortBy: vi.fn(),
      refresh: vi.fn().mockResolvedValue(undefined),
    })
  })

  it('renders backend leaderboard rows', async () => {
    const wrapper = mount(ContestLeaderboard)
    await flushPromises()

    expect(useLeaderboardRealtime).toHaveBeenCalled()
    const passedRef = vi.mocked(useLeaderboardRealtime).mock.calls[0][0]
    expect(passedRef.value).toBe('practice-arena')

    expect(wrapper.text()).toContain('Student B')
    expect(wrapper.text()).toContain('$11,000.00')
  })

  it('triggers refresh when refresh button is clicked', async () => {
    const mockRefresh = vi.fn().mockResolvedValue(undefined)
    vi.mocked(useLeaderboardRealtime).mockReturnValue({
      rows: ref([]),
      sortBy: ref('equity'),
      status: ref('connected'),
      lastUpdated: ref(new Date()),
      setSortBy: vi.fn(),
      refresh: mockRefresh,
    })

    const wrapper = mount(ContestLeaderboard)
    await flushPromises()

    const button = wrapper.find('[data-test="refresh-button"]')
    expect(button.exists()).toBe(true)
    await button.trigger('click')
    await flushPromises()

    expect(mockRefresh).toHaveBeenCalled()
  })
})
