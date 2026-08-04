import './assets/main.css'

import { initWallet } from '@solana/wallet-adapter-vue'
import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import {
  SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  createSolanaWalletAdapters,
} from './services/solanaWalletAdapters'

initWallet({
  wallets: createSolanaWalletAdapters() as never,
  autoConnect: true,
  localStorageKey: SOLANA_WALLET_ADAPTER_STORAGE_KEY,
  onError: (error) => {
    console.error('Solana wallet adapter error:', error)
  },
})

const app = createApp(App)

app.use(router)

app.mount('#app')
