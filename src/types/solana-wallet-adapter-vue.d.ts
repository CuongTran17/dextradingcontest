declare module '@solana/wallet-adapter-vue' {
  import type { WalletName } from '@solana/wallet-adapter-base'
  import type { Connection, PublicKey, Transaction } from '@solana/web3.js'
  import type { Ref } from 'vue'

  interface WalletAdapter {
    name: WalletName
    readyState: import('@solana/wallet-adapter-base').WalletReadyState
    ready(): Promise<boolean>
  }

  interface Wallet {
    adapter: WalletAdapter
  }

  export interface WalletStoreOptions {
    wallets: unknown[]
    autoConnect?: boolean
    localStorageKey?: string
    onError?: (error: unknown) => void
  }

  export function initWallet(walletStoreProps: WalletStoreOptions): void

  export interface WalletStore {
    wallets: Wallet[]
    wallet: Ref<Wallet | null>
    adapter: Ref<WalletAdapter | null>
    publicKey: Ref<PublicKey | null>
    ready: Ref<boolean>
    connected: Ref<boolean>
    connecting: Ref<boolean>
    disconnecting: Ref<boolean>
    select(walletName: WalletName): Promise<void>
    connect(): Promise<void>
    disconnect(): Promise<void>
    sendTransaction(transaction: Transaction, connection: Connection): Promise<string>
    signTransaction: Ref<((transaction: Transaction) => Promise<Transaction>) | undefined>
  }

  export function useWallet(): WalletStore
}
