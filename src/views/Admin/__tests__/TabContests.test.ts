import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import TabContests from '@/views/Admin/components/TabContests.vue'
import {
  confirmCertificateBatchAuthorization,
  confirmContestOnchainInitialize,
  createAdminCryptoContest,
  exportContestCertificates,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
  settleAdminCryptoContest,
  updateAdminCryptoContest,
} from '@/services/cryptoContestApi'
import {
  initializeContestOnchain,
  publishCertificateRootOnchain,
  setContestJoinEnabledOnchain,
} from '@/services/solanaWallet'
import type { Contest } from '@/types/crypto'

vi.mock('@/services/cryptoContestApi', () => ({
  confirmCertificateBatchAuthorization: vi.fn(),
  confirmContestOnchainInitialize: vi.fn(),
  createAdminCryptoContest: vi.fn(),
  exportContestCertificates: vi.fn(),
  fetchAdminCryptoContests: vi.fn(),
  setAdminCryptoContestStatus: vi.fn(),
  settleAdminCryptoContest: vi.fn(),
  updateAdminCryptoContest: vi.fn(),
}))

vi.mock('@/services/solanaWallet', () => ({
  initializeContestOnchain: vi.fn(),
  publishCertificateRootOnchain: vi.fn(),
  setContestJoinEnabledOnchain: vi.fn(),
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
    vi.mocked(confirmCertificateBatchAuthorization).mockReset()
    vi.mocked(confirmContestOnchainInitialize).mockReset()
    vi.mocked(exportContestCertificates).mockReset()
    vi.mocked(initializeContestOnchain).mockReset()
    vi.mocked(publishCertificateRootOnchain).mockReset()
    vi.mocked(setContestJoinEnabledOnchain).mockReset()
    vi.mocked(settleAdminCryptoContest).mockReset()
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

  it('normalizes contest slug and symbols before creating', async () => {
    vi.mocked(createAdminCryptoContest).mockResolvedValue({
      ...contest,
      id: 'winter-cup',
      title: 'Winter Cup',
      symbols: ['BTCUSDT', 'SOLUSDT'],
    })

    const wrapper = mount(TabContests)
    await flushPromises()

    await wrapper.get('[data-test="contest-slug"]').setValue('Winter Cup')
    await wrapper.get('[data-test="contest-title"]').setValue('Winter Cup')
    await wrapper.get('[data-test="contest-symbols"]').setValue('btcusdt, solusdt')
    await wrapper.get('[data-test="contest-form"]').trigger('submit')

    expect(createAdminCryptoContest).toHaveBeenCalledWith(
      expect.objectContaining({
        slug: 'winter-cup',
        symbols: ['BTCUSDT', 'SOLUSDT'],
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

  it('exports contest certificates and displays root publishing details', async () => {
    vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
      {
        ...contest,
        onchainContestAddress: 'ContestPda1111111111111111111111111111111',
        onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      },
    ])
    vi.mocked(exportContestCertificates).mockResolvedValue({
      batch_id: '91',
      contest_id: 'summer-cup',
      top_n: 5,
      snapshot_hash: 'aa'.repeat(32),
      merkle_root: 'bb'.repeat(32),
      claims: [
        {
          participant_id: 1,
          wallet_address: 'So11111111111111111111111111111111111111112',
          rank: 1,
          recipient_name: 'Alice',
          image_uri: 'ipfs://QmImage',
          metadata_uri: 'ipfs://QmMetadata',
          merkle_leaf: 'cc'.repeat(32),
          proof: [],
        },
      ],
    })
    vi.mocked(publishCertificateRootOnchain).mockResolvedValue({
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      signature: '5'.repeat(88),
    })
    vi.mocked(confirmCertificateBatchAuthorization).mockResolvedValue({
      batch_id: '91',
      contest_id: 'summer-cup',
      top_n: 5,
      snapshot_hash: 'aa'.repeat(32),
      merkle_root: 'bb'.repeat(32),
      status: 'authorized',
      authorized_by_wallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      authorize_tx_signature: '5'.repeat(88),
      authorized_at: '2026-08-01T10:00:00+00:00',
    })

    const wrapper = mount(TabContests)
    await flushPromises()
    await wrapper.get('[data-test="certificate-topn-summer-cup"]').setValue(5)
    await wrapper.get('[data-test="export-certificates-summer-cup"]').trigger('click')
    await flushPromises()

    expect(exportContestCertificates).toHaveBeenCalledWith('summer-cup', { topN: 5 })
    expect(wrapper.text()).toContain('Merkle root')
    expect(wrapper.text()).toContain('bb'.repeat(32))
    expect(wrapper.text()).toContain('Claims exported: 1')
    expect(wrapper.text()).toContain('Batch 91')

    await wrapper.get('[data-test="publish-certificate-root"]').trigger('click')
    await flushPromises()

    expect(publishCertificateRootOnchain).toHaveBeenCalledWith({
      contestId: 'summer-cup',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      rootHex: 'bb'.repeat(32),
      snapshotHashHex: 'aa'.repeat(32),
      topN: 5,
      batchId: '91',
      expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    })
    expect(confirmCertificateBatchAuthorization).toHaveBeenCalledWith({
      contestId: 'summer-cup',
      batchId: '91',
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      authorizeTxSignature: '5'.repeat(88),
    })
    expect(wrapper.text()).toContain('Certificate batch authorized on Solana')
  })

  it('initializes a contest on Solana from the admin table', async () => {
    vi.mocked(initializeContestOnchain).mockResolvedValue({
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      signature: '5'.repeat(88),
    })
    vi.mocked(confirmContestOnchainInitialize).mockResolvedValue({
      ...contest,
      onchainContestAddress: 'ContestPda1111111111111111111111111111111',
      onchainInitializeTxSignature: '5'.repeat(88),
      onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      onchainInitializedAt: '2026-07-30T10:00:00+00:00',
    })

    const wrapper = mount(TabContests)
    await flushPromises()
    await wrapper.get('[data-test="initialize-onchain-summer-cup"]').trigger('click')
    await flushPromises()

    expect(initializeContestOnchain).toHaveBeenCalledWith({ contestId: 'summer-cup' })
    expect(confirmContestOnchainInitialize).toHaveBeenCalledWith({
      contestId: 'summer-cup',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      initializeTxSignature: '5'.repeat(88),
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    })
    expect(wrapper.text()).toContain('On-chain ready')
    expect(wrapper.text()).toContain('ExUB...J2NB')
  })

  it('locks joins on-chain, ends early, settles, and exports certificates', async () => {
    vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
      {
        ...contest,
        rawStatus: 'active',
        onchainContestAddress: 'ContestPda1111111111111111111111111111111',
        onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
        onchainInitializeTxSignature: '5'.repeat(88),
      },
    ])
    vi.mocked(setContestJoinEnabledOnchain).mockResolvedValue({
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      signature: '4'.repeat(88),
    })
    vi.mocked(updateAdminCryptoContest).mockResolvedValue({
      ...contest,
      rawStatus: 'active',
      endsAt: '2026-07-30T10:00:00.000Z',
    })
    vi.mocked(settleAdminCryptoContest).mockResolvedValue({
      status: 'completed',
      contest_id: 'summer-cup',
      version: 1,
      snapshot_hash: 'aa'.repeat(32),
      settlement_prices: {},
      rows: [],
      cancelled_orders: [],
      settled_at: '2026-07-30T10:00:00+00:00',
    })
    vi.mocked(exportContestCertificates).mockResolvedValue({
      batch_id: '91',
      contest_id: 'summer-cup',
      top_n: 10,
      snapshot_hash: 'aa'.repeat(32),
      merkle_root: 'bb'.repeat(32),
      claims: [],
    })

    const wrapper = mount(TabContests)
    await flushPromises()
    await wrapper.get('[data-test="end-export-summer-cup"]').trigger('click')
    await flushPromises()

    expect(setContestJoinEnabledOnchain).toHaveBeenCalledWith({
      contestId: 'summer-cup',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      enabled: false,
      expectedAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    })
    expect(updateAdminCryptoContest).toHaveBeenCalledWith('summer-cup', {
      endsAt: expect.any(String),
    })
    expect(settleAdminCryptoContest).toHaveBeenCalledWith('summer-cup')
    expect(exportContestCertificates).toHaveBeenCalledWith('summer-cup', { topN: 10 })
    expect(wrapper.text()).toContain('Certificates exported for summer-cup')
    expect(wrapper.text()).toContain('Claims exported: 0')
  })

  it('does not end and export when contest is not initialized on-chain', async () => {
    vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
      {
        ...contest,
        rawStatus: 'active',
        onchainAdminWallet: null,
        onchainInitializeTxSignature: null,
      },
    ])

    const wrapper = mount(TabContests)
    await flushPromises()
    await wrapper.get('[data-test="end-export-summer-cup"]').trigger('click')
    await flushPromises()

    expect(setContestJoinEnabledOnchain).not.toHaveBeenCalled()
    expect(updateAdminCryptoContest).not.toHaveBeenCalled()
    expect(settleAdminCryptoContest).not.toHaveBeenCalled()
    expect(exportContestCertificates).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Initialize this contest on Solana before ending it')
  })

  it('labels the failing step when end and export fails', async () => {
    vi.mocked(fetchAdminCryptoContests).mockResolvedValue([
      {
        ...contest,
        rawStatus: 'active',
        onchainContestAddress: 'ContestPda1111111111111111111111111111111',
        onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
        onchainInitializeTxSignature: '5'.repeat(88),
      },
    ])
    vi.mocked(setContestJoinEnabledOnchain).mockResolvedValue({
      adminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
      contestAddress: 'ContestPda1111111111111111111111111111111',
      signature: '4'.repeat(88),
    })
    vi.mocked(updateAdminCryptoContest).mockResolvedValue({
      ...contest,
      rawStatus: 'active',
      endsAt: '2026-07-30T10:00:00.000Z',
    })
    vi.mocked(settleAdminCryptoContest).mockResolvedValue({
      status: 'completed',
      contest_id: 'summer-cup',
      version: 1,
      snapshot_hash: 'aa'.repeat(32),
      settlement_prices: {},
      rows: [],
      cancelled_orders: [],
      settled_at: '2026-07-30T10:00:00+00:00',
    })
    vi.mocked(exportContestCertificates).mockRejectedValue(new Error('Database error'))

    const wrapper = mount(TabContests)
    await flushPromises()
    await wrapper.get('[data-test="end-export-summer-cup"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Export certificates failed: Database error')
  })
})
