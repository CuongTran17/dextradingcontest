<template>
  <div
    class="border-t border-gray-200 pt-4 dark:border-gray-800"
    :class="expanded ? 'px-1' : 'flex justify-center'"
  >
    <div v-if="expanded" class="rounded-lg bg-gray-50 p-3 dark:bg-gray-950">
      <div class="flex items-start gap-2">
        <span class="mt-0.5 text-gray-500 dark:text-gray-400">
          <PlugInIcon />
        </span>
        <div class="min-w-0">
          <p class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Solana wallet</p>
          <p class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">
            {{ walletAddress ? walletName : 'Not connected' }}
          </p>
          <p v-if="walletAddress" class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400" :title="walletAddress">
            {{ shortWallet(walletAddress) }}
          </p>
          <span
            v-if="walletAddress"
            class="mt-2 inline-flex rounded-full bg-violet-100 px-2 py-0.5 text-xs font-semibold text-violet-700 dark:bg-violet-500/15 dark:text-violet-200"
          >
            devnet
          </span>
        </div>
      </div>

      <div class="mt-3">
        <button
          v-if="!walletAddress"
          class="w-full rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
          data-test="sidebar-connect-wallet"
          type="button"
          :disabled="connecting"
          @click="openWalletSelector"
        >
          {{ connecting ? 'Connecting...' : 'Connect wallet' }}
        </button>
        <button
          v-else
          class="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-900"
          data-test="sidebar-disconnect-wallet"
          type="button"
          @click="disconnectWallet"
        >
          Logout
        </button>
      </div>
      <WalletSelectorPanel
        v-if="selectorOpen"
        class="mt-3"
        :wallet-options="walletOptions"
        :connecting="connecting"
        @close="closeWalletSelector"
        @select="(walletName) => connectWallet(walletName as never)"
      />
      <p v-if="error" class="mt-2 text-xs text-rose-600">{{ error }}</p>
    </div>

    <div v-else-if="!walletAddress" class="relative">
      <button
        class="flex h-10 w-10 items-center justify-center rounded-lg text-gray-500 hover:bg-gray-100 hover:text-gray-700 dark:text-gray-400 dark:hover:bg-gray-800 dark:hover:text-gray-200"
        data-test="sidebar-connect-wallet"
        type="button"
        title="Connect wallet"
        :disabled="connecting"
        @click="openWalletSelector"
      >
        <PlugInIcon />
      </button>
      <WalletSelectorPanel
        v-if="selectorOpen"
        class="absolute bottom-12 left-0 z-20 w-64 rounded-lg border border-gray-200 bg-white p-2 shadow-lg dark:border-gray-800 dark:bg-gray-950"
        :wallet-options="walletOptions"
        :connecting="connecting"
        @close="closeWalletSelector"
        @select="(walletName) => connectWallet(walletName as never)"
      />
    </div>
    <button
      v-else
      class="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300"
      data-test="sidebar-disconnect-wallet"
      type="button"
      :title="`Logout ${shortWallet(walletAddress)}`"
      @click="disconnectWallet"
    >
      <PlugInIcon />
    </button>
  </div>
</template>

<script setup lang="ts">
import { PlugInIcon } from '@/icons'
import { useSolanaWalletSession } from '@/composables/useSolanaWalletSession'
import WalletSelectorPanel from './WalletSelectorPanel.vue'

defineProps<{
  expanded: boolean
}>()

const {
  walletAddress,
  walletName,
  connecting,
  selectorOpen,
  walletOptions,
  error,
  openWalletSelector,
  closeWalletSelector,
  connectWallet,
  disconnectWallet,
} = useSolanaWalletSession()

function shortWallet(value: string): string {
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}
</script>
