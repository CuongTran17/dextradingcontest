import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { Connection } from '@solana/web3.js'
import { computed, ref, watch } from 'vue'
import { useWallet } from '@solana/wallet-adapter-vue'

import { isLoggedIn } from '@/services/authApi'
import { walletReadyStateLabel } from '@/services/solanaWalletAdapters'
import { solanaRpcUrl } from '@/services/solanaWallet'
import type {
  ConnectSolanaWalletResult,
  SolanaWalletSigner,
} from '@/services/solanaWallet'

const STORAGE_KEY = 'crypto_contest_solana_wallet'

const walletAddress = ref('')
const walletName = ref('Solana wallet')
const connecting = ref(false)
const error = ref('')

export interface SolanaWalletOption {
  name: WalletName
  readyState: WalletReadyState
  readyStateLabel: string
}

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
  localStorage.setItem(STORAGE_KEY, JSON.stringify(wallet))
}

export function clearSolanaWalletSession(): void {
  walletAddress.value = ''
  walletName.value = 'Solana wallet'
  error.value = ''
  localStorage.removeItem(STORAGE_KEY)
}

function walletSessionErrorMessage(err: unknown): string {
  if (err instanceof Error && /reject|decline|denied|cancel/i.test(err.message)) {
    return 'Wallet request was rejected'
  }
  if (err instanceof Error && err.message) return err.message
  return 'Unable to connect Solana wallet'
}

export function useSolanaWalletSession() {
  hydrateSolanaWalletSession()

  const walletStore = useWallet()
  const selectorOpen = ref(false)

  const walletOptions = computed<SolanaWalletOption[]>(() =>
    walletStore.wallets.map((wallet) => ({
      name: wallet.adapter.name,
      readyState: wallet.adapter.readyState,
      readyStateLabel: walletReadyStateLabel(wallet.adapter.readyState),
    })),
  )

  const activeSigner = computed<SolanaWalletSigner | null>(() => {
    if (!walletStore.connected.value || !walletStore.publicKey.value) return null
    return {
      publicKey: walletStore.publicKey.value,
      walletName: walletName.value,
      signTransaction: walletStore.signTransaction.value,
      signAndSendTransaction: async (transaction) => ({
        signature: await walletStore.sendTransaction(transaction, new Connection(solanaRpcUrl(), 'confirmed')),
      }),
    }
  })

  watch(
    [walletStore.publicKey, walletStore.connected, walletStore.wallet],
    ([currentPublicKey, isConnected, selectedWallet]) => {
      if (!isConnected || !currentPublicKey) return
      saveSolanaWalletSession({
        walletAddress: currentPublicKey.toBase58(),
        walletName: String(selectedWallet?.adapter.name || 'Solana wallet'),
      })
    },
    { immediate: true },
  )

  function openWalletSelector(): void {
    error.value = ''
    selectorOpen.value = true
  }

  function closeWalletSelector(): void {
    selectorOpen.value = false
  }

  async function connectWallet(walletNameToSelect?: WalletName): Promise<ConnectSolanaWalletResult | null> {
    if (!isLoggedIn()) {
      clearSolanaWalletSession()
      error.value = 'Please sign in before connecting a wallet'
      return null
    }

    connecting.value = true
    error.value = ''
    try {
      if (walletNameToSelect) {
        await walletStore.select(walletNameToSelect)
      }
      if (!walletStore.wallet.value && !walletNameToSelect) {
        openWalletSelector()
        return null
      }
      await walletStore.connect()
      const connectedPublicKey = walletStore.publicKey.value
      if (!connectedPublicKey) {
        throw new Error('Wallet connected without a public key')
      }
      const wallet = {
        walletAddress: connectedPublicKey.toBase58(),
        walletName: String(walletStore.wallet.value?.adapter.name || 'Solana wallet'),
      }
      saveSolanaWalletSession(wallet)
      selectorOpen.value = false
      return wallet
    } catch (err) {
      error.value = walletSessionErrorMessage(err)
      return null
    } finally {
      connecting.value = false
    }
  }

  async function disconnectWallet(): Promise<void> {
    error.value = ''
    let disconnectError = ''
    try {
      await walletStore.disconnect()
    } catch (err) {
      disconnectError = walletSessionErrorMessage(err)
    } finally {
      clearSolanaWalletSession()
      error.value = disconnectError
    }
  }

  return {
    walletAddress,
    walletName,
    connecting,
    disconnecting: walletStore.disconnecting,
    connected: walletStore.connected,
    selectorOpen,
    walletOptions,
    activeSigner,
    error,
    openWalletSelector,
    closeWalletSelector,
    connectWallet,
    disconnectWallet,
    clearWallet: clearSolanaWalletSession,
  }
}
