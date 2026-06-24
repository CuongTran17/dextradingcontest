<template>
  <main class="space-y-6">
    <div>
      <div>
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Virtual Portfolio</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Practice balances and positions are simulated with USDT_TEST.
        </p>
      </div>
    </div>
    <PortfolioSummary v-if="account" :account="account" :metrics="metrics" />
    <p v-else class="text-sm text-gray-500 dark:text-gray-400">{{ accountMessage }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { getCryptoAccount } from '@/services/cryptoTradingApi'
import type { TradingAccount } from '@/types/crypto'

const account = ref<TradingAccount | null>(null)
const accountMessage = ref('Loading your persistent practice account...')
const metrics = computed(() => {
  const current = account.value
  const equity = current?.equity ?? 0
  const initialEquity = current?.initialEquity ?? 0
  const pnl = equity - initialEquity
  return {
    cash: current?.cash ?? 0,
    positionsValue: Math.max(equity - (current?.cash ?? 0), 0),
    equity,
    pnl,
    roi: initialEquity > 0 ? (pnl / initialEquity) * 100 : 0,
    volume: current?.orders.reduce((sum, order) => sum + order.notional, 0) ?? 0,
    tradeCount: current?.orders.length ?? 0,
  }
})

onMounted(async () => {
  try {
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    accountMessage.value = error instanceof Error ? error.message : 'Unable to load practice account'
  }
})
</script>
