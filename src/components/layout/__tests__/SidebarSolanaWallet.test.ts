import { flushPromises, mount } from '@vue/test-utils'
import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SidebarSolanaWallet from '../SidebarSolanaWallet.vue'

let allowConnection = true
let preventReconnect = false

const walletSession = {
  walletAddress: ref(''),
  walletName: ref('Solana wallet'),
  displayWalletAddress: ref(''),
  displayWalletName: ref('Solana wallet'),
  connecting: ref(false),
  disconnecting: ref(false),
  connected: ref(false),
  selectorOpen: ref(false),
  walletOptions: computed(() => [
    {
      name: 'Phantom' as WalletName,
      readyState: WalletReadyState.Installed,
      readyStateLabel: 'Installed',
    },
  ]),
  activeSigner: computed(() => null),
  error: ref(''),
  openWalletSelector: vi.fn(() => {
    walletSession.selectorOpen.value = true
  }),
  closeWalletSelector: vi.fn(() => {
    walletSession.selectorOpen.value = false
  }),
  connectWallet: vi.fn(async (_walletName?: WalletName) => {
    if (!allowConnection) {
      walletSession.error.value = 'Please sign in before connecting a wallet'
      return null
    }
    if (preventReconnect) {
      walletSession.error.value = 'Switch accounts in your wallet extension'
      return null
    }
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    walletSession.displayWalletAddress.value = walletSession.walletAddress.value
    walletSession.displayWalletName.value = walletSession.walletName.value
    walletSession.connected.value = true
    walletSession.selectorOpen.value = false
    localStorage.setItem(
      'crypto_contest_solana_wallet',
      JSON.stringify({
        walletAddress: walletSession.walletAddress.value,
        walletName: walletSession.walletName.value,
      }),
    )
    return {
      walletAddress: walletSession.walletAddress.value,
      walletName: walletSession.walletName.value,
    }
  }),
  disconnectWallet: vi.fn(async () => {
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
    walletSession.displayWalletAddress.value = ''
    walletSession.displayWalletName.value = 'Solana wallet'
    walletSession.connected.value = false
    localStorage.removeItem('crypto_contest_solana_wallet')
  }),
}

vi.mock('@/composables/useSolanaWalletSession', () => ({
  useSolanaWalletSession: () => walletSession,
}))

describe('SidebarSolanaWallet', () => {
  beforeEach(() => {
    localStorage.clear()
    allowConnection = true
    preventReconnect = false
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
    walletSession.displayWalletAddress.value = ''
    walletSession.displayWalletName.value = 'Solana wallet'
    walletSession.connecting.value = false
    walletSession.disconnecting.value = false
    walletSession.connected.value = false
    walletSession.selectorOpen.value = false
    walletSession.error.value = ''
    walletSession.openWalletSelector.mockClear()
    walletSession.closeWalletSelector.mockClear()
    walletSession.connectWallet.mockClear()
    walletSession.disconnectWallet.mockClear()
  })

  it('opens the wallet selector and connects the chosen wallet', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    expect(wrapper.text()).toContain('Connect wallet')
    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()

    expect(walletSession.openWalletSelector).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Solana devnet')
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()

    expect(walletSession.connectWallet).toHaveBeenCalledWith('Phantom')
    expect(wrapper.text()).toContain('Phantom')
    expect(wrapper.text()).toContain('So11...1112')
    expect(wrapper.text()).toContain('devnet')
    expect(wrapper.text()).toContain('Logout')
  })

  it('offers connection instead of logout for a hydrated display-only wallet', async () => {
    walletSession.displayWalletAddress.value = 'Saved11111111111111111111111111111111111111'
    walletSession.displayWalletName.value = 'Phantom'

    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    expect(wrapper.text()).toContain('Saved wallet')
    expect(wrapper.text()).toContain('Connect wallet')
    expect(wrapper.text()).not.toContain('Logout')

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')

    expect(walletSession.openWalletSelector).toHaveBeenCalledOnce()
  })

  it('disconnects the wallet from the sidebar', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="sidebar-disconnect-wallet"]').trigger('click')
    await flushPromises()

    expect(walletSession.disconnectWallet).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Connect wallet')
  })

  it('closes the expanded wallet selector', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="wallet-selector-close"]').trigger('click')
    await flushPromises()

    expect(walletSession.closeWalletSelector).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(false)
  })

  it('opens and closes the wallet selector from the collapsed sidebar', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: false },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()

    expect(walletSession.openWalletSelector).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(true)
    await wrapper.get('[data-test="wallet-selector-close"]').trigger('click')
    await flushPromises()

    expect(walletSession.closeWalletSelector).toHaveBeenCalledOnce()
    expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(false)
  })

  it('renders the session error and clears persisted state after a failed provider disconnect', async () => {
    walletSession.disconnectWallet.mockImplementationOnce(async () => {
      walletSession.walletAddress.value = ''
      walletSession.walletName.value = 'Solana wallet'
      walletSession.connected.value = false
      localStorage.removeItem('crypto_contest_solana_wallet')
      walletSession.error.value = 'Wallet provider rejected disconnect'
    })
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()
    expect(localStorage.getItem('crypto_contest_solana_wallet')).toContain('So11111111111111111111111111111111111111112')

    await wrapper.get('[data-test="sidebar-disconnect-wallet"]').trigger('click')
    await flushPromises()

    expect(walletSession.disconnectWallet).toHaveBeenCalledOnce()
    expect(localStorage.getItem('crypto_contest_solana_wallet')).toBeNull()
    expect(wrapper.text()).toContain('Connect wallet')
    expect(wrapper.text()).toContain('Wallet provider rejected disconnect')
  })

  it('does not reconnect immediately after logout when the session rejects it', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="sidebar-disconnect-wallet"]').trigger('click')
    await flushPromises()
    preventReconnect = true
    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()

    expect(walletSession.connectWallet).toHaveBeenCalledTimes(2)
    expect(localStorage.getItem('crypto_contest_solana_wallet')).toBeNull()
    expect(wrapper.text()).toContain('Connect wallet')
    expect(wrapper.text()).not.toContain('So11...1112')
    expect(wrapper.text()).toContain('Switch accounts in your wallet extension')
  })

  it('renders the unauthenticated session error without connecting a wallet', async () => {
    allowConnection = false
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()

    expect(walletSession.connectWallet).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Please sign in before connecting a wallet')
    expect(wrapper.text()).toContain('Connect wallet')
  })
})
