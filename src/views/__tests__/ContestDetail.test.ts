import { PublicKey } from '@solana/web3.js'
import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { fetchContest } from '@/services/cryptoContestApi'
import { confirmSolanaJoin, fetchContestWallet } from '@/services/cryptoTradingApi'
import { joinContestOnchain } from '@/services/solanaWallet'
import ContestDetail from '@/views/ContestDetail.vue'

const walletSession = vi.hoisted(() => ({
  walletAddress: { value: '' },
  walletName: { value: 'Solana wallet' },
  activeSigner: {
    get value() {
      return {
        publicKey: new PublicKey(walletSession.walletAddress.value),
        walletName: walletSession.walletName.value,
        signAndSendTransaction: vi.fn(async () => ({ signature: '5'.repeat(88) })),
      }
    },
  },
  connecting: { value: false },
  error: { value: '' },
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { contestId: 'practice-arena' } }),
}))

vi.mock('@/services/cryptoTradingApi', () => ({
  confirmSolanaJoin: vi.fn(),
  fetchContestWallet: vi.fn(),
}))

vi.mock('@/services/solanaWallet', () => ({
  joinContestOnchain: vi.fn(),
}))

vi.mock('@/composables/useSolanaWalletSession', () => ({
  useSolanaWalletSession: () => walletSession,
}))

vi.mock('@/services/cryptoContestApi', () => ({
  fetchContest: vi.fn(),
}))

describe('ContestDetail', () => {
  beforeEach(() => {
    localStorage.clear()
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
    walletSession.connecting.value = false
    walletSession.error.value = ''
    vi.mocked(fetchContest).mockReset()
    vi.mocked(fetchContest).mockResolvedValue({
      id: 'practice-arena',
      title: 'Practice Arena From API',
      status: 'practice',
      mode: 'practice',
      initialCapital: 10000,
      symbols: ['BTCUSDT'],
      startsAt: '2026-06-01T00:00:00+00:00',
      endsAt: '2026-07-01T00:00:00+00:00',
      participantCount: 2,
      onchainInitializeTxSignature: '5'.repeat(88),
    })
    vi.mocked(joinContestOnchain).mockReset()
    vi.mocked(joinContestOnchain).mockResolvedValue({
      walletAddress: 'So11111111111111111111111111111111111111112',
      signature: '5'.repeat(88),
    })
    vi.mocked(confirmSolanaJoin).mockReset()
    vi.mocked(confirmSolanaJoin).mockResolvedValue({
      contest_id: 'practice-arena',
      wallet_address: 'So11111111111111111111111111111111111111112',
      wallet_type: 'solana',
      join_tx_signature: '5'.repeat(88),
      joined_onchain_at: '2026-07-28T12:00:00+00:00',
    })
    vi.mocked(fetchContestWallet).mockReset()
    vi.mocked(fetchContestWallet).mockResolvedValue({
      contest_id: 'practice-arena',
      wallet_address: null,
      wallet_type: null,
      join_tx_signature: null,
      joined_onchain_at: null,
    })
  })

  it('loads contest detail from the backend', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    expect(fetchContest).toHaveBeenCalledWith('practice-arena')
    expect(fetchContestWallet).toHaveBeenCalledWith('practice-arena')
    expect(wrapper.text()).toContain('Practice Arena From API')
  })

  it('links to the certificate claim page', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: {
            props: ['to'],
            template: '<a :href="to"><slot /></a>',
          },
        },
      },
    })

    await flushPromises()

    const certificateLink = wrapper.find('a[href="/contests/practice-arena/certificates"]')
    expect(certificateLink.exists()).toBe(true)
    expect(certificateLink.text()).toContain('Certificate')
  })

  it('prompts users to connect a wallet from the sidebar before on-chain join', async () => {
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Wallet not connected')
    expect(wrapper.text()).toContain('Connect wallet from the sidebar')
    expect(wrapper.find('[data-testid="connect-solana-wallet"]').exists()).toBe(false)
  })

  it('uses the wallet connected from the sidebar before joining on-chain', async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Phantom')
    expect(wrapper.text()).toContain('So11...1112')
    expect(wrapper.text()).toContain('Join on Solana')
  })

  it('does not render a contest-level wallet logout action', async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.find('[data-testid="disconnect-solana-wallet"]').exists()).toBe(false)
  })

  it('shows joined state from an existing backend wallet binding', async () => {
    vi.mocked(fetchContestWallet).mockResolvedValue({
      contest_id: 'practice-arena',
      wallet_address: 'So11111111111111111111111111111111111111112',
      wallet_type: 'solana',
      join_tx_signature: '5'.repeat(88),
      joined_onchain_at: '2026-07-28T12:00:00+00:00',
    })
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Joined')
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    expect(joinContestOnchain).not.toHaveBeenCalled()
  })

  it('explains that Solana join is unavailable before on-chain initialization', async () => {
    vi.mocked(fetchContest).mockResolvedValue({
      id: 'practice-arena',
      title: 'Practice Arena From API',
      status: 'practice',
      mode: 'practice',
      initialCapital: 10000,
      symbols: ['BTCUSDT'],
      startsAt: '2026-06-01T00:00:00+00:00',
      endsAt: '2026-07-01T00:00:00+00:00',
      participantCount: 2,
      onchainInitializeTxSignature: null,
    })

    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Contest is not initialized on Solana yet')
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    expect(joinContestOnchain).not.toHaveBeenCalled()
  })

  it('blocks the admin wallet that initialized the contest from joining', async () => {
    vi.mocked(fetchContest).mockResolvedValue({
      id: 'practice-arena',
      title: 'Practice Arena From API',
      status: 'practice',
      mode: 'practice',
      initialCapital: 10000,
      symbols: ['BTCUSDT'],
      startsAt: '2026-06-01T00:00:00+00:00',
      endsAt: '2026-07-01T00:00:00+00:00',
      participantCount: 2,
      onchainInitializeTxSignature: '5'.repeat(88),
      onchainAdminWallet: 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB',
    })
    walletSession.walletAddress.value = 'ExUBrwnH1fLHTbCWy3W7iTetApp58weES84BPZXiJ2NB'
    walletSession.walletName.value = 'Phantom'

    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()

    expect(wrapper.text()).toContain('Admin wallet ExUB...J2NB')
    expect(wrapper.text()).toContain('The admin wallet that initialized this contest cannot join it')
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    expect(joinContestOnchain).not.toHaveBeenCalled()
  })

  it('joins the selected contest through the backend', async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    await flushPromises()

    expect(joinContestOnchain).toHaveBeenCalledWith(
      {
        contestId: 'practice-arena',
        walletPublicKey: 'So11111111111111111111111111111111111111112',
      },
      expect.objectContaining({
        walletName: 'Phantom',
      }),
    )
    expect(confirmSolanaJoin).toHaveBeenCalledWith({
      contestId: 'practice-arena',
      walletAddress: 'So11111111111111111111111111111111111111112',
      joinTxSignature: '5'.repeat(88),
    })
    expect(wrapper.get('button').text()).toContain('Joined')
  })

  it('retries backend confirmation with a pending Solana join signature', async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    vi.mocked(confirmSolanaJoin)
      .mockRejectedValueOnce(new Error('Request timed out after 30000ms'))
      .mockResolvedValueOnce({
        contest_id: 'practice-arena',
        wallet_address: 'So11111111111111111111111111111111111111112',
        wallet_type: 'solana',
        join_tx_signature: '5'.repeat(88),
        joined_onchain_at: '2026-07-28T12:00:00+00:00',
      })

    const wrapper = mount(ContestDetail, {
      global: {
        stubs: {
          RouterLink: { template: '<a><slot /></a>' },
        },
      },
    })

    await flushPromises()
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    await flushPromises()
    await wrapper.find('[data-testid="join-solana-contest"]').trigger('click')
    await flushPromises()

    expect(joinContestOnchain).toHaveBeenCalledOnce()
    expect(confirmSolanaJoin).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('Joined')
  })
})
