import { WalletReadyState, type Adapter } from '@solana/wallet-adapter-base'
import { PhantomWalletAdapter } from '@solana/wallet-adapter-phantom'
import { SolflareWalletAdapter } from '@solana/wallet-adapter-solflare'

export const SOLANA_WALLET_ADAPTER_STORAGE_KEY = 'crypto_contest_solana_wallet_adapter'

export interface VueSolanaWallet {
  name: Adapter['name']
  url: string
  icon: string
  adapter: Adapter & { ready: () => Promise<boolean> }
  ready: () => Promise<boolean>
}

export function createSolanaWalletAdapters(): VueSolanaWallet[] {
  return [new PhantomWalletAdapter(), new SolflareWalletAdapter()].map((adapter) =>
    toVueWallet(adapter),
  )
}

function toVueWallet(adapter: Adapter): VueSolanaWallet {
  const ready = async () =>
    adapter.readyState === WalletReadyState.Installed ||
    adapter.readyState === WalletReadyState.Loadable

  return {
    name: adapter.name,
    url: adapter.url,
    icon: adapter.icon,
    adapter: Object.assign(adapter, { ready }),
    ready,
  }
}

export function walletReadyStateLabel(readyState: WalletReadyState): string {
  if (readyState === WalletReadyState.Installed) return 'Installed'
  if (readyState === WalletReadyState.Loadable) return 'Available'
  if (readyState === WalletReadyState.Unsupported) return 'Unsupported'
  return 'Not installed'
}
