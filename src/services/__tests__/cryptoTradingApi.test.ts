import { beforeEach, describe, expect, it, vi } from 'vitest'

import { backendFetch } from '@/services/httpClient'
import {
  confirmSolanaJoin,
  confirmCertificateClaim,
  fetchMyCertificate,
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

  it('uses an extended timeout when confirming a Solana join transaction', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue({
      contest_id: 'summer-cup',
      wallet_address: 'So11111111111111111111111111111111111111112',
      wallet_type: 'solana',
      join_tx_signature: '5'.repeat(88),
      joined_onchain_at: '2026-07-28T12:00:00+00:00',
    })

    await confirmSolanaJoin({
      contestId: 'summer-cup',
      walletAddress: 'So11111111111111111111111111111111111111112',
      joinTxSignature: '5'.repeat(88),
    })

    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend',
      '/api/crypto/contests/summer-cup/join/confirm',
      expect.objectContaining({
        method: 'POST',
        headers: { Authorization: 'Bearer token-123' },
      }),
      { timeoutMs: 30000 },
    )
  })

  it('fetches my certificate claim status', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue({
      contest_id: 'practice-arena',
      eligible: true,
      batch_id: '401',
      top_n: 5,
      batch_authorized: true,
      wallet_address: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipient_name: 'Alice',
      image_uri: 'ipfs://QmImage',
      metadata_uri: 'ipfs://QmMetadata',
      snapshot_hash: 'aa'.repeat(32),
      proof: [],
      mint_address: null,
      mint_tx_signature: null,
      claimed_at: null,
    })

    const result = await fetchMyCertificate('practice-arena')

    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend',
      '/api/crypto/contests/practice-arena/certificates/me',
      expect.objectContaining({
        headers: { Authorization: 'Bearer token-123' },
      }),
    )
    expect(result.eligible).toBe(true)
    expect(result.batchId).toBe('401')
    expect(result.topN).toBe(5)
    expect(result.batchAuthorized).toBe(true)
    expect(result.imageUri).toBe('ipfs://QmImage')
  })

  it('confirms a certificate claim transaction', async () => {
    localStorage.setItem('crypto_contest_token', 'token-123')
    vi.mocked(backendFetch).mockResolvedValue({
      contest_id: 'practice-arena',
      eligible: true,
      batch_id: '401',
      top_n: 5,
      batch_authorized: true,
      wallet_address: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipient_name: 'Alice',
      image_uri: 'ipfs://QmImage',
      metadata_uri: 'ipfs://QmMetadata',
      snapshot_hash: 'aa'.repeat(32),
      proof: [],
      mint_address: null,
      mint_tx_signature: '5'.repeat(88),
      claimed_at: '2026-07-30T10:00:00+00:00',
    })

    const result = await confirmCertificateClaim({
      contestId: 'practice-arena',
      batchId: '401',
      mintTxSignature: '5'.repeat(88),
    })

    const request = vi.mocked(backendFetch).mock.calls[0][2]
    expect(JSON.parse(request?.body as string)).toEqual({
      batch_id: 401,
      mint_address: null,
      mint_tx_signature: '5'.repeat(88),
    })
    expect(result.mintTxSignature).toBe('5'.repeat(88))
  })
})
