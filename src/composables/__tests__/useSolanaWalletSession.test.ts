import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { PublicKey, Transaction } from '@solana/web3.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ref, watch } from 'vue'

import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { isLoggedIn } from '@/services/authApi'

const phantomName = 'Phantom' as WalletName
const publicKey = ref<PublicKey | null>(null)
const connected = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const selectedWallet = ref(null)
const selectedAdapter = ref(null)
const ready = ref(true)
const signTransaction = ref<((transaction: Transaction) => Promise<Transaction>) | undefined>()
const sendTransaction = vi.fn()
function walletFixture(name: WalletName, adapterReady = async () => true) {
  return {
    name,
    url: 'https://phantom.app',
    icon: '',
    adapter: { name, readyState: WalletReadyState.Installed, ready: adapterReady },
    ready: adapterReady,
  } as never
}
const select = vi.fn((name: WalletName) => {
  const wallet = walletFixture(name)
  selectedWallet.value = wallet
  selectedAdapter.value = wallet.adapter
  ready.value = true
})
const connect = vi.fn(async () => {
  publicKey.value = new PublicKey('So11111111111111111111111111111111111111112')
  connected.value = true
})
const disconnect = vi.fn(async () => {
  publicKey.value = null
  connected.value = false
})

vi.mock('@solana/wallet-adapter-vue', () => ({
  useWallet: () => ({
    wallets: [
      {
        name: phantomName,
        url: 'https://phantom.app',
        icon: '',
        adapter: { name: phantomName, readyState: WalletReadyState.Installed },
        ready: async () => true,
      },
    ],
    wallet: selectedWallet,
    adapter: selectedAdapter,
    publicKey,
    ready,
    connected,
    connecting,
    disconnecting,
    select,
    connect,
    disconnect,
    sendTransaction,
    signTransaction,
  }),
}))

vi.mock('@/services/authApi', () => ({
  isLoggedIn: vi.fn(() => true),
}))

describe('useSolanaWalletSession', () => {
  beforeEach(() => {
    localStorage.clear()
    publicKey.value = null
    connected.value = false
    selectedWallet.value = null
    selectedAdapter.value = null
    ready.value = true
    signTransaction.value = async (transaction) => transaction
    sendTransaction.mockReset()
    select.mockClear()
    connect.mockClear()
    disconnect.mockClear()
    vi.mocked(isLoggedIn).mockReturnValue(true)
  })

  it('renders adapter wallet options for the selector', () => {
    const session = useSolanaWalletSession()

    expect(session.walletOptions.value).toEqual([
      {
        name: 'Phantom',
        readyState: WalletReadyState.Installed,
        readyStateLabel: 'Installed',
      },
    ])
  })

  it('selects and connects a wallet through the adapter', async () => {
    const session = useSolanaWalletSession()

    const result = await session.connectWallet(phantomName)

    expect(select).toHaveBeenCalledWith(phantomName)
    expect(connect).toHaveBeenCalledOnce()
    expect(result).toEqual({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
    expect(session.walletAddress.value).toBe('So11111111111111111111111111111111111111112')
    expect(session.activeSigner.value?.walletName).toBe('Phantom')
  })

  it('waits for the selected adapter readiness to settle before the first connect', async () => {
    let resolveReady!: (value: boolean) => void
    const readiness = new Promise<boolean>((resolve) => {
      resolveReady = resolve
    })
    const adapterReady = vi.fn(() => readiness)
    const selectedName = ref<WalletName | null>(null)
    const stopSelectionWatch = watch(selectedName, (name) => {
      if (!name) return
      const wallet = walletFixture(name, adapterReady)
      selectedWallet.value = wallet
      selectedAdapter.value = wallet.adapter
      ready.value = false
      void adapterReady().then((isReady) => {
        ready.value = isReady
      })
    })
    select.mockImplementationOnce((name: WalletName) => {
      selectedName.value = name
    })
    connect.mockImplementationOnce(async () => {
      if (!selectedWallet.value || !ready.value) {
        throw new Error('wallet not ready')
      }
      publicKey.value = new PublicKey('So11111111111111111111111111111111111111112')
      connected.value = true
    })
    const session = useSolanaWalletSession()

    const resultPromise = session.connectWallet(phantomName)
    await vi.waitFor(() => expect(adapterReady).toHaveBeenCalled())

    expect(connect).not.toHaveBeenCalled()

    resolveReady(true)
    const result = await resultPromise
    stopSelectionWatch()

    expect(result).toEqual({
      walletAddress: 'So11111111111111111111111111111111111111112',
      walletName: 'Phantom',
    })
  })

  it('stores stale hydrated wallets as display state only', () => {
    localStorage.setItem(
      'crypto_contest_solana_wallet',
      JSON.stringify({
        walletAddress: 'Saved11111111111111111111111111111111111111',
        walletName: 'Phantom',
      }),
    )

    const session = useSolanaWalletSession()

    expect(session.walletAddress.value).toBe('')
    expect(session.displayWalletAddress.value).toBe('Saved11111111111111111111111111111111111111')
    expect(session.displayWalletName.value).toBe('Phantom')
    expect(session.activeSigner.value).toBeNull()
  })

  it('requires an authenticated account before selecting a wallet', async () => {
    vi.mocked(isLoggedIn).mockReturnValue(false)
    const session = useSolanaWalletSession()

    await expect(session.connectWallet(phantomName)).resolves.toBeNull()

    expect(select).not.toHaveBeenCalled()
    expect(connect).not.toHaveBeenCalled()
    expect(session.error.value).toBe('Please sign in before connecting a wallet')
  })

  it('clears saved session state when the adapter disconnect rejects', async () => {
    const session = useSolanaWalletSession()
    await session.connectWallet(phantomName)
    localStorage.setItem('crypto_contest_solana_wallet_adapter', JSON.stringify(phantomName))
    disconnect.mockRejectedValueOnce(new Error('Wallet provider rejected disconnect'))

    await session.disconnectWallet()

    expect(disconnect).toHaveBeenCalledOnce()
    expect(session.walletAddress.value).toBe('')
    expect(localStorage.getItem('crypto_contest_solana_wallet')).toBeNull()
    expect(localStorage.getItem('crypto_contest_solana_wallet_adapter')).toBeNull()
    expect(session.error.value).toBe('Wallet request was rejected')
  })

  it('blocks reconnecting the same address immediately after logout', async () => {
    const session = useSolanaWalletSession()
    await session.connectWallet(phantomName)
    await session.disconnectWallet()

    await expect(session.connectWallet(phantomName)).resolves.toBeNull()

    expect(connect).toHaveBeenCalledTimes(2)
    expect(session.walletAddress.value).toBe('')
    expect(localStorage.getItem('crypto_contest_solana_wallet')).toBeNull()
    expect(session.error.value).toBe('Switch accounts in your wallet extension, then connect again.')
  })
})
