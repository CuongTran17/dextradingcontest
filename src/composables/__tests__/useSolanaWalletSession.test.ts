import { WalletReadyState, type WalletName } from '@solana/wallet-adapter-base'
import { PublicKey, Transaction } from '@solana/web3.js'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { computed, ref } from 'vue'

import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import { isLoggedIn } from '@/services/authApi'

const phantomName = 'Phantom' as WalletName
const publicKey = ref<PublicKey | null>(null)
const connected = ref(false)
const connecting = ref(false)
const disconnecting = ref(false)
const selectedWallet = ref(null)
const selectedAdapter = ref(null)
const signTransaction = ref<((transaction: Transaction) => Promise<Transaction>) | undefined>()
const sendTransaction = vi.fn()
function walletFixture(name: WalletName) {
  return {
    name,
    url: 'https://phantom.app',
    icon: '',
    adapter: { name, readyState: WalletReadyState.Installed },
    ready: async () => true,
  } as never
}
const select = vi.fn((name: WalletName) => {
  selectedWallet.value = walletFixture(name)
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
    ready: computed(() => true),
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

  it('waits for asynchronous wallet selection before connecting', async () => {
    select.mockImplementationOnce(async (name: WalletName) => {
      await Promise.resolve()
      selectedWallet.value = walletFixture(name)
    })
    connect.mockImplementationOnce(async () => {
      if (!selectedWallet.value) {
        throw new Error('wallet not selected')
      }
      publicKey.value = new PublicKey('So11111111111111111111111111111111111111112')
      connected.value = true
    })
    const session = useSolanaWalletSession()

    const result = await session.connectWallet(phantomName)

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

    expect(session.walletAddress.value).toBe('Saved11111111111111111111111111111111111111')
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
})
