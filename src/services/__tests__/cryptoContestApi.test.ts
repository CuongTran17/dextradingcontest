import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  createAdminCryptoContest,
  fetchContest,
  fetchContestLeaderboard,
  fetchContests,
} from '@/services/cryptoContestApi'
import { backendFetch } from '@/services/httpClient'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
  normalizeBackendUrl: () => 'http://localhost:8000',
}))

vi.mock('@/services/authApi', () => ({
  getToken: () => 'token-123',
}))

describe('cryptoContestApi', () => {
  beforeEach(() => vi.mocked(backendFetch).mockReset())

  it('maps public contests from backend fields', async () => {
    vi.mocked(backendFetch).mockResolvedValue([
      {
        id: 'practice-arena',
        title: 'Practice Arena',
        status: 'practice',
        raw_status: 'active',
        mode: 'practice',
        initial_capital: 10000,
        quote_asset: 'USDT_TEST',
        symbols: ['BTCUSDT'],
        starts_at: '2026-06-01T00:00:00+00:00',
        ends_at: '2026-07-01T00:00:00+00:00',
        participant_count: 4,
      },
    ])

    const contests = await fetchContests()

    expect(backendFetch).toHaveBeenCalledWith(
      'http://localhost:8000',
      '/api/crypto/contests',
    )
    expect(contests[0]).toMatchObject({
      id: 'practice-arena',
      initialCapital: 10000,
      participantCount: 4,
    })
  })

  it('loads contest detail and leaderboard', async () => {
    vi.mocked(backendFetch)
      .mockResolvedValueOnce({
        id: 'practice-arena',
        title: 'Practice Arena',
        status: 'practice',
        raw_status: 'active',
        mode: 'practice',
        initial_capital: 10000,
        quote_asset: 'USDT_TEST',
        symbols: ['BTCUSDT'],
        starts_at: null,
        ends_at: null,
        participant_count: 1,
      })
      .mockResolvedValueOnce([
        {
          rank: 1,
          user: 'user-1',
          equity: 11000,
          pnl: 1000,
          roi: 10,
          volume: 5000,
          trade_count: 2,
          last_trade: 'BTCUSDT buy',
        },
      ])

    expect((await fetchContest('practice-arena')).id).toBe('practice-arena')
    expect((await fetchContestLeaderboard('practice-arena'))[0].tradeCount).toBe(2)
  })

  it('creates admin contests with bearer auth', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      id: 'new-contest',
      title: 'New Contest',
      status: 'upcoming',
      raw_status: 'scheduled',
      mode: 'contest',
      initial_capital: 10000,
      quote_asset: 'USDT_TEST',
      symbols: ['BTCUSDT'],
      starts_at: null,
      ends_at: null,
      participant_count: 0,
    })

    await createAdminCryptoContest({
      slug: 'new-contest',
      title: 'New Contest',
      mode: 'contest',
      status: 'scheduled',
      initialBalance: 10000,
      symbols: ['BTCUSDT'],
    })

    expect(vi.mocked(backendFetch).mock.calls[0][2]).toMatchObject({
      method: 'POST',
      headers: { Authorization: 'Bearer token-123' },
    })
  })
})
