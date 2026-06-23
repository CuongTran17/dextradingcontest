import { beforeEach, describe, expect, it } from 'vitest'

import {
  createInitialPortfolio,
  loadContestState,
  saveContestState,
} from '@/stores/cryptoContestStore'

describe('cryptoContestStore', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('saves and loads joined contests and virtual portfolios', () => {
    const portfolio = createInitialPortfolio('practice-arena', 10000)

    saveContestState({
      joinedContestIds: ['practice-arena'],
      portfolios: {
        'practice-arena': portfolio,
      },
    })

    expect(loadContestState()).toEqual({
      joinedContestIds: ['practice-arena'],
      portfolios: {
        'practice-arena': {
          contestId: 'practice-arena',
          cash: 10000,
          positions: [],
          orders: [],
        },
      },
    })
  })
})
