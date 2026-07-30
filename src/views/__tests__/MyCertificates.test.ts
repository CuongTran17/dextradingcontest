import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  confirmCertificateClaim,
  fetchMyCertificate,
} from '@/services/cryptoTradingApi'
import { claimCertificateOnchain } from '@/services/solanaWallet'
import MyCertificates from '@/views/MyCertificates.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  confirmCertificateClaim: vi.fn(),
  fetchMyCertificate: vi.fn(),
}))

vi.mock('@/services/solanaWallet', () => ({
  claimCertificateOnchain: vi.fn(),
}))

describe('MyCertificates', () => {
  beforeEach(() => {
    vi.mocked(fetchMyCertificate).mockReset()
    vi.mocked(fetchMyCertificate).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      walletAddress: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipientName: 'Alice',
      imageUri: 'ipfs://QmImage',
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
      mintAddress: null,
      mintTxSignature: null,
      claimedAt: null,
    })
    vi.mocked(claimCertificateOnchain).mockReset()
    vi.mocked(claimCertificateOnchain).mockResolvedValue({ signature: '5'.repeat(88) })
    vi.mocked(confirmCertificateClaim).mockReset()
    vi.mocked(confirmCertificateClaim).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      walletAddress: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipientName: 'Alice',
      imageUri: 'ipfs://QmImage',
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
      mintAddress: null,
      mintTxSignature: '5'.repeat(88),
      claimedAt: '2026-07-30T10:00:00+00:00',
    })
  })

  it('shows mint certificate when the connected wallet is eligible', async () => {
    const wrapper = mount(MyCertificates)
    await flushPromises()

    expect(fetchMyCertificate).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.text()).toContain('Mint Certificate')
    expect(wrapper.text()).toContain('Alice')
    expect(wrapper.find('img').attributes('src')).toBe('https://gateway.pinata.cloud/ipfs/QmImage')
  })

  it('submits on-chain claim and confirms the transaction', async () => {
    const wrapper = mount(MyCertificates)
    await flushPromises()
    await wrapper.get('[data-testid="claim-certificate"]').trigger('click')
    await flushPromises()

    expect(claimCertificateOnchain).toHaveBeenCalledWith({
      contestId: 'practice-arena',
      walletPublicKey: 'So11111111111111111111111111111111111111112',
      rank: 1,
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
    })
    expect(confirmCertificateClaim).toHaveBeenCalledWith({
      contestId: 'practice-arena',
      mintTxSignature: '5'.repeat(88),
    })
    expect(wrapper.text()).toContain('Claimed')
  })
})
