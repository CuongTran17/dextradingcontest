import { ref } from 'vue'

import { isLoggedIn } from '@/services/authApi'
import {
  connectSolanaWallet,
  disconnectSolanaWallet,
  type ConnectSolanaWalletResult,
} from '@/services/solanaWallet'

const STORAGE_KEY = 'crypto_contest_solana_wallet'

const walletAddress = ref('')
const walletName = ref('Solana wallet')
const connecting = ref(false)
const error = ref('')
const lastDisconnectedWalletAddress = ref('')

function hydrateSolanaWalletSession(): void {
  if (!isLoggedIn()) {
    clearSolanaWalletSession()
    return
  }

  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) {
      clearSolanaWalletSession()
      return
    }

    const saved = JSON.parse(raw) as Partial<ConnectSolanaWalletResult>
    walletAddress.value = saved.walletAddress || ''
    walletName.value = saved.walletName || 'Solana wallet'
  } catch {
    clearSolanaWalletSession()
  }
}

function saveSolanaWalletSession(wallet: ConnectSolanaWalletResult): void {
  walletAddress.value = wallet.walletAddress
  walletName.value = wallet.walletName
  lastDisconnectedWalletAddress.value = ''
  localStorage.setItem(STORAGE_KEY, JSON.stringify(wallet))
}

export function clearSolanaWalletSession(): void {
  walletAddress.value = ''
  walletName.value = 'Solana wallet'
  error.value = ''
  lastDisconnectedWalletAddress.value = ''
  localStorage.removeItem(STORAGE_KEY)
}

export function useSolanaWalletSession() {
  hydrateSolanaWalletSession()

  async function connectWallet(): Promise<ConnectSolanaWalletResult | null> {
    if (!isLoggedIn()) {
      clearSolanaWalletSession()
      error.value = 'Please sign in before connecting a wallet'
      return null
    }

    connecting.value = true
    error.value = ''
    try {
      const wallet = await connectSolanaWallet()
      if (lastDisconnectedWalletAddress.value && wallet.walletAddress === lastDisconnectedWalletAddress.value) {
        clearSolanaWalletSession()
        lastDisconnectedWalletAddress.value = wallet.walletAddress
        error.value = 'Switch accounts in your wallet extension, then connect again.'
        return null
      }
      saveSolanaWalletSession(wallet)
      return wallet
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Unable to connect Solana wallet'
      return null
    } finally {
      connecting.value = false
    }
  }

  async function disconnectWallet(): Promise<void> {
    error.value = ''
    let disconnectError = ''
    const disconnectedWalletAddress = walletAddress.value
    try {
      await disconnectSolanaWallet()
    } catch (err) {
      disconnectError = err instanceof Error ? err.message : 'Unable to disconnect Solana wallet'
    } finally {
      clearSolanaWalletSession()
      lastDisconnectedWalletAddress.value = disconnectedWalletAddress
      error.value = disconnectError
    }
  }

  return {
    walletAddress,
    walletName,
    connecting,
    error,
    connectWallet,
    disconnectWallet,
    clearWallet: clearSolanaWalletSession,
  }
}
