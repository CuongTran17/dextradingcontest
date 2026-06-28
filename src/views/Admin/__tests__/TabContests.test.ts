import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TabContests from '@/views/Admin/components/TabContests.vue'
import {
  createAdminCryptoContest,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
  updateAdminCryptoContest,
} from '@/services/cryptoContestApi'
import type { Contest } from '@/types/crypto'

vi.mock('@/services/cryptoContestApi', () => ({
  createAdminCryptoContest: vi.fn(),
  fetchAdminCryptoContests: vi.fn(),
  setAdminCryptoContestStatus: vi.fn(),
  updateAdminCryptoContest: vi.fn(),
}))

const contest: Contest = {
  id: 'summer-cup',
  title: 'Summer Cup',
  status: 'upcoming',
  rawStatus: 'scheduled',
  mode: 'contest',
  initialCapital: 10000,
  symbols: ['BTCUSDT', 'ETHUSDT'],
  startsAt: '2026-07-01T00:00:00+00:00',
  endsAt: '2026-07-15T00:00:00+00:00',
  participantCount: 2,
}

describe('TabContests', () => {
  beforeEach(() => {
    vi.mocked(fetchAdminCryptoContests).mockReset()
    vi.mocked(createAdminCryptoContest).mockReset()
    vi.mocked(updateAdminCryptoContest).mockReset()
    vi.mocked(setAdminCryptoContestStatus).mockReset()
    vi.mocked(fetchAdminCryptoContests).mockResolvedValue([contest])
  })

  it('creates contests with start and end times', async () => {
    vi.mocked(createAdminCryptoContest).mockResolvedValue({
      ...contest,
      id: 'winter-cup',
      title: 'Winter Cup',
      startsAt: '2026-12-01T01:00:00.000Z',
      endsAt: '2026-12-08T01:00:00.000Z',
    })

    const wrapper = mount(TabContests)
    await flushPromises()

    await wrapper.get('[data-test="contest-slug"]').setValue('winter-cup')
    await wrapper.get('[data-test="contest-title"]').setValue('Winter Cup')
    await wrapper.get('[data-test="contest-initial-balance"]').setValue(25000)
    await wrapper.get('[data-test="contest-starts-at"]').setValue('2026-12-01T08:00')
    await wrapper.get('[data-test="contest-ends-at"]').setValue('2026-12-08T08:00')
    await wrapper.get('[data-test="contest-form"]').trigger('submit')

    expect(createAdminCryptoContest).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: 'winter-cup',
        title: 'Winter Cup',
        initialBalance: 25000,
        startsAt: '2026-12-01T01:00:00.000Z',
        endsAt: '2026-12-08T01:00:00.000Z',
      }),
    )
  })

  it('updates editable contest details from the table', async () => {
    vi.mocked(updateAdminCryptoContest).mockResolvedValue({
      ...contest,
      title: 'Summer Cup Updated',
      symbols: ['BTCUSDT', 'SOLUSDT'],
    })

    const wrapper = mount(TabContests)
    await flushPromises()

    await wrapper.get('[data-test="edit-contest-summer-cup"]').trigger('click')
    await wrapper.get('[data-test="contest-title"]').setValue('Summer Cup Updated')
    await wrapper.get('[data-test="contest-symbols"]').setValue('BTCUSDT,SOLUSDT')
    await wrapper.get('[data-test="contest-form"]').trigger('submit')

    expect(updateAdminCryptoContest).toHaveBeenCalledWith(
      'summer-cup',
      expect.objectContaining({
        title: 'Summer Cup Updated',
        symbols: ['BTCUSDT', 'SOLUSDT'],
      }),
    )
  })
})
