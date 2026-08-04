<template>
  <div
    data-test="wallet-selector"
    class="rounded-lg border border-gray-200 bg-white p-2 shadow-sm dark:border-gray-800 dark:bg-gray-950"
  >
    <div class="mb-2 flex items-center justify-between">
      <div>
        <p class="text-xs font-semibold uppercase text-gray-500 dark:text-gray-400">Choose wallet</p>
        <p class="mt-0.5 text-xs font-medium text-blue-600 dark:text-blue-300">Solana devnet</p>
      </div>
      <button
        type="button"
        class="rounded p-1 text-gray-500 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-900"
        data-test="wallet-selector-close"
        title="Close wallet selector"
        @click="$emit('close')"
      >
        <XIcon />
      </button>
    </div>

    <div v-if="walletOptions.length" class="space-y-1">
      <button
        v-for="option in walletOptions"
        :key="option.name"
        type="button"
        class="flex w-full items-center justify-between gap-3 rounded-md px-2 py-2 text-left hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:hover:bg-gray-900"
        :data-test="`wallet-option-${option.name}`"
        :disabled="connecting"
        @click="$emit('select', option.name)"
      >
        <span class="min-w-0">
          <span class="block truncate text-sm font-semibold text-gray-900 dark:text-white">{{ option.name }}</span>
          <span class="block text-xs text-gray-500 dark:text-gray-400">{{ option.readyStateLabel }}</span>
        </span>
        <span class="text-xs font-semibold text-blue-600 dark:text-blue-300">
          {{ connecting ? 'Connecting' : 'Connect' }}
        </span>
      </button>
    </div>
    <p v-else class="text-xs text-gray-500 dark:text-gray-400">
      Install Phantom, Solflare, or Backpack to use Solana devnet.
    </p>
  </div>
</template>

<script setup lang="ts">
import { XIcon } from '@/icons'
import type { SolanaWalletOption } from '@/composables/useSolanaWalletSession'
import type { WalletName } from '@solana/wallet-adapter-base'

defineProps<{
  walletOptions: SolanaWalletOption[]
  connecting: boolean
}>()

defineEmits<{
  close: []
  select: [walletName: WalletName]
}>()
</script>
