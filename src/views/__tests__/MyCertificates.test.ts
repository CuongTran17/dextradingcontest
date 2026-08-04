import { flushPromises, mount } from '@vue/test-utils'
import { PublicKey } from '@solana/web3.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import {
  confirmCertificateClaim,
  fetchMyCertificate,
} from '@/services/cryptoTradingApi'
import { claimCertificateOnchain } from '@/services/solanaWallet'
import MyCertificates from '@/views/MyCertificates.vue'

const walletSession = {
  walletAddress: { value: 'So11111111111111111111111111111111111111112' },
  walletName: { value: 'Phantom' },
  activeSigner: {
    value: {
      publicKey: new PublicKey('So11111111111111111111111111111111111111112'),
      walletName: 'Phantom',
      signAndSendTransaction: vi.fn(async () => ({ signature: '5'.repeat(88) })),
    },
  },
  connecting: { value: false },
  connectWallet: vi.fn(),
}

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

vi.mock('@/composables/useSolanaWalletSession', () => ({
  useSolanaWalletSession: () => walletSession,
}))

describe('MyCertificates', () => {
  beforeEach(() => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.connecting.value = false
    walletSession.connectWallet.mockReset()
    walletSession.connectWallet.mockResolvedValue({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
    vi.mocked(fetchMyCertificate).mockReset()
    vi.mocked(fetchMyCertificate).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      batchId: '401',
      topN: 5,
      batchAuthorized: true,
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
    vi.mocked(claimCertificateOnchain).mockResolvedValue({
      signature: '5'.repeat(88),
      mintAddress: 'Mint111111111111111111111111111111111111111',
    })
    vi.mocked(confirmCertificateClaim).mockReset()
    vi.mocked(confirmCertificateClaim).mockResolvedValue({
      contestId: 'practice-arena',
      eligible: true,
      batchId: '401',
      topN: 5,
      batchAuthorized: true,
      walletAddress: 'So11111111111111111111111111111111111111112',
      rank: 1,
      recipientName: 'Alice',
      imageUri: 'ipfs://QmImage',
      metadataUri: 'ipfs://QmMetadata',
      snapshotHash: 'aa'.repeat(32),
      proof: [],
      mintAddress: 'Mint111111111111111111111111111111111111111',
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

    expect(claimCertificateOnchain).toHaveBeenCalledWith(
      {
        contestId: 'practice-arena',
        batchId: '401',
        topN: 5,
        walletPublicKey: 'So11111111111111111111111111111111111111112',
        rank: 1,
        metadataUri: 'ipfs://QmMetadata',
        snapshotHash: 'aa'.repeat(32),
        proof: [],
      },
      expect.objectContaining({
        walletName: 'Phantom',
      }),
    )
    expect(confirmCertificateClaim).toHaveBeenCalledWith({
      contestId: 'practice-arena',
      batchId: '401',
      mintTxSignature: '5'.repeat(88),
      mintAddress: 'Mint111111111111111111111111111111111111111',
    })
    expect(wrapper.text()).toContain('Claimed')
  })

  it('blocks claim when the connected wallet does not match the joined wallet', async () => {
    walletSession.walletAddress.value = 'WrongWallet111111111111111111111111111111111'

    const wrapper = mount(MyCertificates)
    await flushPromises()
    await wrapper.get('[data-testid="claim-certificate"]').trigger('click')
    await flushPromises()

    expect(claimCertificateOnchain).not.toHaveBeenCalled()
    expect(confirmCertificateClaim).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Connect the wallet used to join this contest')
  })
})
