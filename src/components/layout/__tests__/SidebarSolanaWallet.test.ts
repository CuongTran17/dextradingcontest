import { flushPromises, mount } from '@vue/test-utils'
import { WalletReadyState } from '@solana/wallet-adapter-base'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SidebarSolanaWallet from '../SidebarSolanaWallet.vue'

const walletSession = {
  walletAddress: ref(''),
  walletName: ref('Solana wallet'),
  connecting: ref(false),
  disconnecting: ref(false),
  connected: ref(false),
  selectorOpen: ref(false),
  walletOptions: computed(() => [
    {
      name: 'Phantom',
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
  connectWallet: vi.fn(async () => {
    walletSession.walletAddress.value = 'So11111111111111111111111111111111111111112'
    walletSession.walletName.value = 'Phantom'
    walletSession.connected.value = true
    walletSession.selectorOpen.value = false
    return {
      walletAddress: walletSession.walletAddress.value,
      walletName: walletSession.walletName.value,
    }
  }),
  disconnectWallet: vi.fn(async () => {
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
    walletSession.connected.value = false
  }),
}

vi.mock('@/composables/useSolanaWalletSession', () => ({
  useSolanaWalletSession: () => walletSession,
}))

describe('SidebarSolanaWallet', () => {
  beforeEach(() => {
    walletSession.walletAddress.value = ''
    walletSession.walletName.value = 'Solana wallet'
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

    expect(wrapper.find('[data-test="wallet-selector"]').exists()).toBe(true)
    await wrapper.get('[data-test="wallet-option-Phantom"]').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('Phantom')
    expect(wrapper.text()).toContain('So11...1112')
    expect(wrapper.text()).toContain('devnet')
    expect(wrapper.text()).toContain('Logout')
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
})
