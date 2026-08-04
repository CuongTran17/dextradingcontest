<template>
  <div class="min-w-64 rounded-lg border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900">
    <div class="flex items-start justify-between gap-3">
      <div>
        <p class="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">Solana wallet</p>
        <p class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ statusLabel }}</p>
        <p v-if="walletAddress" class="mt-1 text-xs text-gray-500 dark:text-gray-400">
          {{ walletName }} {{ shortWallet(walletAddress) }}
        </p>
      </div>
      <span
        class="rounded-full px-2 py-1 text-xs font-semibold"
        :class="joined ? 'bg-emerald-100 text-emerald-700' : walletAddress ? 'bg-blue-100 text-blue-700' : 'bg-gray-200 text-gray-600'"
      >
        {{ joined ? 'Joined' : walletAddress ? 'Ready' : 'Offline' }}
      </span>
    </div>

    <div class="mt-3 flex flex-wrap gap-2">
      <p v-if="!walletAddress && !joined" class="text-sm text-gray-500 dark:text-gray-400">
        Connect wallet from the sidebar
      </p>
      <button
        data-testid="join-solana-contest"
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60"
        :disabled="joining || joined || !walletAddress"
        @click="$emit('join')"
      >
        {{ joined ? 'Joined' : joining ? 'Joining...' : 'Join on Solana' }}
      </button>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    walletAddress?: string
    walletName?: string
    joined?: boolean
    connecting?: boolean
    joining?: boolean
    error?: string
  }>(),
  {
    walletAddress: '',
    walletName: 'Solana wallet',
    joined: false,
    connecting: false,
    joining: false,
    error: '',
  },
)

defineEmits<{
  join: []
}>()

const statusLabel = computed(() => {
  if (props.joined) return 'Joined'
  if (props.walletAddress) return 'Wallet connected'
  return 'Wallet not connected'
})

function shortWallet(value: string): string {
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}
</script>
