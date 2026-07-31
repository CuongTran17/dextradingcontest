import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import SidebarSolanaWallet from '../SidebarSolanaWallet.vue'
import { isLoggedIn } from '@/services/authApi'
import { connectSolanaWallet, disconnectSolanaWallet } from '@/services/solanaWallet'

vi.mock('@/services/authApi', () => ({
  isLoggedIn: vi.fn(() => true),
}))

vi.mock('@/services/solanaWallet', () => ({
  connectSolanaWallet: vi.fn(),
  disconnectSolanaWallet: vi.fn(),
}))

describe('SidebarSolanaWallet', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(isLoggedIn).mockReset()
    vi.mocked(isLoggedIn).mockReturnValue(true)
    vi.mocked(connectSolanaWallet).mockReset()
    vi.mocked(connectSolanaWallet).mockResolvedValue({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
    vi.mocked(disconnectSolanaWallet).mockReset()
    vi.mocked(disconnectSolanaWallet).mockResolvedValue(undefined)
  })

  it('connects and displays the wallet address from the sidebar', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    expect(wrapper.text()).toContain('Connect wallet')
    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()

    expect(connectSolanaWallet).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Phantom')
    expect(wrapper.text()).toContain('So11...1112')
    expect(wrapper.text()).toContain('Logout')
  })

  it('disconnects the wallet from the sidebar', async () => {
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()
    await wrapper.get('[data-test="sidebar-disconnect-wallet"]').trigger('click')
    await flushPromises()

    expect(disconnectSolanaWallet).toHaveBeenCalledOnce()
    expect(wrapper.text()).toContain('Connect wallet')
  })

  it('requires an authenticated account before connecting a wallet', async () => {
    vi.mocked(isLoggedIn).mockReturnValue(false)
    const wrapper = mount(SidebarSolanaWallet, {
      props: { expanded: true },
    })

    await wrapper.get('[data-test="sidebar-connect-wallet"]').trigger('click')
    await flushPromises()

    expect(connectSolanaWallet).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('Please sign in before connecting a wallet')
  })
})
