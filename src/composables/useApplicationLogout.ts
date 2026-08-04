import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { logout as authLogout } from '@/services/authApi'

export function useApplicationLogout() {
  const { disconnectWallet } = useSolanaWalletSession()

  async function signOut(): Promise<void> {
    try {
      await disconnectWallet()
    } catch {
      // Account cleanup must still complete if a wallet adapter fails unexpectedly.
    } finally {
      authLogout()
    }
  }

  return { signOut }
}
