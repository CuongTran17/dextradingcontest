import { beforeEach, describe, expect, it, vi } from 'vitest'

import { useApplicationLogout } from '@/composables/useApplicationLogout'
import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { logout as authLogout } from '@/services/authApi'

const disconnectWallet = vi.fn()

vi.mock('@/composables/useSolanaWalletSession', () => ({
  useSolanaWalletSession: vi.fn(() => ({ disconnectWallet })),
}))

vi.mock('@/services/authApi', () => ({
  logout: vi.fn(),
}))

describe('useApplicationLogout', () => {
  beforeEach(() => {
    disconnectWallet.mockReset()
    disconnectWallet.mockResolvedValue(undefined)
    vi.mocked(authLogout).mockReset()
  })

  it('disconnects the wallet adapter before clearing the application account', async () => {
    const { signOut } = useApplicationLogout()

    await signOut()

    expect(useSolanaWalletSession).toHaveBeenCalled()
    expect(disconnectWallet).toHaveBeenCalledOnce()
    expect(authLogout).toHaveBeenCalledOnce()
    expect(disconnectWallet.mock.invocationCallOrder[0]).toBeLessThan(
      vi.mocked(authLogout).mock.invocationCallOrder[0],
    )
  })

  it('clears the application account even when adapter cleanup rejects', async () => {
    disconnectWallet.mockRejectedValueOnce(new Error('adapter failure'))
    const { signOut } = useApplicationLogout()

    await expect(signOut()).resolves.toBeUndefined()

    expect(authLogout).toHaveBeenCalledOnce()
  })
})
