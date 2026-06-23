import { describe, expect, it, vi } from 'vitest'
import { backendFetch } from '@/services/httpClient'
import { getLatestTicks } from '@/services/dnseTickSandboxApi'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
}))

describe('dnseTickSandboxApi', () => {
  it('accepts saved stale ticks in a market-closed response', async () => {
    vi.mocked(backendFetch).mockResolvedValueOnce({
      status: 'market_closed',
      source: 'dnse',
      data_source: 'cached_last_tick',
      is_stale: true,
      symbols: ['FPT', 'VCB'],
      ticks: [
        {
          symbol: 'FPT',
          price: 100,
          volume: 10,
          trade_time: '2026-06-04T07:45:00+00:00',
          trade_time_local: '2026-06-04T14:45:00+07:00',
          source: 'dnse',
          storage_source: 'cache',
          raw: {},
        },
      ],
      missing_symbols: ['VCB'],
      errors: { market_session: 'Outside market hours' },
      latency_ms: 0,
    })

    const response = await getLatestTicks('FPT,VCB')

    expect(response.is_stale).toBe(true)
    expect(response.data_source).toBe('cached_last_tick')
    expect(response.ticks[0].storage_source).toBe('cache')
    expect(response.missing_symbols).toEqual(['VCB'])
  })
})
