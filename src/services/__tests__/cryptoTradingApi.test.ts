import { beforeEach, describe, expect, it, vi } from 'vitest'

import { backendFetch } from '@/services/httpClient'
import {
  getCryptoAccount,
  joinCryptoContest,
  placeCryptoMarketOrder,
} from '@/services/cryptoTradingApi'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
  normalizeBackendUrl: () => 'http://backend',
}))

const accountFixture = {
  account_id: 9,
  contest_id: 'practice-arena',
  status: 'active',
  cash: 10000,
  initial_equity: 10000,
  equity: 10000,
  realized_pnl: 0,
  unrealized_pnl: 0,
  positions: [],
  orders: [],
}

describe('cryptoTradingApi', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(backendFetch).mockReset()
  })

  it('joins a contest with the bearer token and maps the account', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue(accountFixture)

    const account = await joinCryptoContest('practice-arena')

    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend',
      '/api/crypto/contests/practice-arena/join',
      expect.objectContaining({
        method: 'POST',
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
    expect(account.accountId).toBe(9)
    expect(account.initialEquity).toBe(10000)
  })

  it('loads the current contest account', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue(accountFixture)

    await getCryptoAccount('practice-arena')

    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend',
      '/api/crypto/accounts/practice-arena',
      expect.objectContaining({
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
  })

  it('sends an idempotency key but never sends a portfolio', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue({
      order_id: 12,
      client_order_id: 'web-001',
      symbol: 'BTCUSDT',
      side: 'buy',
      status: 'filled',
      filled_quantity: 0.01,
      average_fill_price: 65000,
      executed_notional: 650,
      fee: 0.65,
      created_at: '2026-06-25T00:00:00+00:00',
    })

    const order = await placeCryptoMarketOrder({
      contestId: 'practice-arena',
      clientOrderId: 'web-001',
      symbol: 'BTCUSDT',
      side: 'buy',
      quantity: 0.01,
    })

    const request = vi.mocked(backendFetch).mock.calls[0][2]
    const body = JSON.parse(request?.body as string)
    expect(body.client_order_id).toBe('web-001')
    expect(body.portfolio).toBeUndefined()
    expect(order.executionPrice).toBe(65000)
  })

  it('rejects trading calls when no token exists', async () => {
    await expect(getCryptoAccount('practice-arena')).rejects.toThrow(
      'Please sign in to trade',
    )
    expect(backendFetch).not.toHaveBeenCalled()
  })
})
