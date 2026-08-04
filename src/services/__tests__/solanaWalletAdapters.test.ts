import { WalletReadyState } from '@solana/wallet-adapter-base'
import { describe, expect, it } from 'vitest'

import {
  SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  createSolanaWalletAdapters,
  walletReadyStateLabel,
} from '@/services/solanaWalletAdapters'

describe('solanaWalletAdapters', () => {
  it('creates the primary Solana wallet adapters used by the selector', () => {
    const wallets = createSolanaWalletAdapters()
    const names = wallets.map((wallet) => wallet.name)

    expect(names).toContain('Phantom')
    expect(names).toContain('Solflare')
  })

  it('wraps adapters with the Vue wallet shape expected by wallet-adapter-vue', async () => {
    const wallet = createSolanaWalletAdapters()[0]

    expect(wallet.adapter.name).toBe(wallet.name)
    expect(wallet.url).toBe(wallet.adapter.url)
    expect(wallet.icon).toBe(wallet.adapter.icon)
    await expect(wallet.ready()).resolves.toBeTypeOf('boolean')
  })

  it('uses a project-scoped wallet adapter storage key', () => {
    expect(SOLANA_WALLET_ADAPTER_STORAGE_KEY).toBe('crypto_contest_solana_wallet_adapter')
  })

  it('maps wallet ready states to compact labels', () => {
    expect(walletReadyStateLabel(WalletReadyState.Installed)).toBe('Installed')
    expect(walletReadyStateLabel(WalletReadyState.Loadable)).toBe('Available')
    expect(walletReadyStateLabel(WalletReadyState.NotDetected)).toBe('Not installed')
    expect(walletReadyStateLabel(WalletReadyState.Unsupported)).toBe('Unsupported')
  })
})
