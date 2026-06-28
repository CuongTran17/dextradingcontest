import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  fetchAdminAccountDetail,
  fetchAdminAccounts,
  fetchAdminOverview,
} from '@/services/adminDashboardApi'
import { backendFetch } from '@/services/httpClient'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
  normalizeBackendUrl: () => 'http://localhost:8000',
}))

vi.mock('@/services/authApi', () => ({
  getToken: () => 'token-123',
}))

describe('adminDashboardApi', () => {
  beforeEach(() => vi.mocked(backendFetch).mockReset())

  it('loads admin overview with bearer auth', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      users: { total: 12, locked: 1, admins: 2 },
      contests: { total: 3, active: 1, participants: 24 },
      accounts: { total: 20, active: 18, total_equity: 201000 },
    })

    const overview = await fetchAdminOverview()

    expect(backendFetch).toHaveBeenCalledWith(
      'http://localhost:8000',
      '/api/admin/crypto/overview',
      { headers: { Authorization: 'Bearer token-123' } },
    )
    expect(overview.accounts.totalEquity).toBe(201000)
  })

  it('maps admin accounts and query filters', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      total: 1,
      page: 1,
      per_page: 20,
      accounts: [
        {
          account_id: 9,
          status: 'active',
          participant_status: 'active',
          user: { id: 7, email: 'student@example.com', fullname: 'Student A', role: 'user', is_locked: false },
          contest: { id: 'practice-arena', title: 'Practice Arena', status: 'active' },
          cash: 9500,
          locked_cash: 100,
          initial_equity: 10000,
          equity: 10100,
          realized_pnl: 100,
          unrealized_pnl: 0,
          roi: 1,
          position_count: 1,
          order_count: 2,
          updated_at: '2026-06-29T00:00:00+00:00',
        },
      ],
    })

    const result = await fetchAdminAccounts({
      contestId: 'practice-arena',
      q: 'student',
      status: 'active',
      page: 1,
      perPage: 20,
    })

    expect(backendFetch).toHaveBeenCalledWith(
      'http://localhost:8000',
      '/api/admin/crypto/accounts?contest_id=practice-arena&q=student&status=active&page=1&per_page=20',
      { headers: { Authorization: 'Bearer token-123' } },
    )
    expect(result.accounts[0].accountId).toBe(9)
    expect(result.accounts[0].lockedCash).toBe(100)
  })

  it('maps account detail balances positions and orders', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      account_id: 9,
      status: 'active',
      participant_status: 'active',
      user: { id: 7, email: 'student@example.com', fullname: 'Student A', role: 'user', is_locked: false },
      contest: { id: 'practice-arena', title: 'Practice Arena', status: 'active' },
      cash: 9500,
      locked_cash: 100,
      initial_equity: 10000,
      equity: 10100,
      realized_pnl: 100,
      unrealized_pnl: 0,
      roi: 1,
      position_count: 1,
      order_count: 1,
      updated_at: '2026-06-29T00:00:00+00:00',
      balances: [{ asset: 'USDT_TEST', available: 9500, locked: 100 }],
      positions: [
        {
          symbol: 'BTCUSDT',
          quantity: 0.1,
          average_entry_price: 50000,
          cost_basis: 5000,
          realized_pnl: 100,
          updated_at: '2026-06-29T00:00:00+00:00',
        },
      ],
      orders: [
        {
          order_id: 1,
          client_order_id: 'web-1',
          symbol: 'BTCUSDT',
          side: 'buy',
          order_type: 'market',
          status: 'filled',
          requested_quantity: 0.1,
          filled_quantity: 0.1,
          average_fill_price: 50000,
          executed_notional: 5000,
          fee_amount: 5,
          fee_asset: 'USDT_TEST',
          submitted_at: '2026-06-29T00:00:00+00:00',
          completed_at: '2026-06-29T00:00:01+00:00',
          fills: [],
        },
      ],
    })

    const detail = await fetchAdminAccountDetail(9)

    expect(detail.balances[0].available).toBe(9500)
    expect(detail.positions[0].averageEntryPrice).toBe(50000)
    expect(detail.orders[0].clientOrderId).toBe('web-1')
  })
})
