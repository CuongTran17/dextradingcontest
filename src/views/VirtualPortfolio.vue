<template>
  <main class="space-y-6">
    <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Virtual Portfolio</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Practice balances and positions are simulated with USDT_TEST.
        </p>
      </div>
      <button
        class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
        @click="resetPractice"
      >
        Reset Practice
      </button>
    </div>
    <PortfolioSummary :portfolio="portfolio" :metrics="metrics" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { getLatestCryptoPrice } from '@/services/cryptoMarketData'
import { calculatePortfolioMetrics } from '@/services/tradingSimulator'
import {
  createInitialPortfolio,
  loadContestState,
  saveContestState,
} from '@/stores/cryptoContestStore'

const state = ref(loadContestState())
const portfolio = ref(
  state.value.portfolios[DEFAULT_CONTEST_ID] ??
    createInitialPortfolio(DEFAULT_CONTEST_ID, 10000),
)
const metrics = computed(() =>
  calculatePortfolioMetrics(portfolio.value, {
    BTCUSDT: getLatestCryptoPrice('BTCUSDT'),
    ETHUSDT: getLatestCryptoPrice('ETHUSDT'),
    SOLUSDT: getLatestCryptoPrice('SOLUSDT'),
  }),
)

function resetPractice() {
  portfolio.value = createInitialPortfolio(DEFAULT_CONTEST_ID, 10000)
  saveContestState({
    ...state.value,
    portfolios: {
      ...state.value.portfolios,
      [DEFAULT_CONTEST_ID]: portfolio.value,
    },
  })
}
</script>
