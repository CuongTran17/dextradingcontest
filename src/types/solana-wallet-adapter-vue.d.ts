declare module '@solana/wallet-adapter-vue' {
  export interface WalletStoreOptions {
    wallets: unknown[]
    autoConnect?: boolean
    localStorageKey?: string
    onError?: (error: unknown) => void
  }

  export function initWallet(walletStoreProps: WalletStoreOptions): void
}
