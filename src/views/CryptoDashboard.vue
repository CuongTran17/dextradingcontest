<template>
  <main class="space-y-6">
    <SimulationDisclaimer />

    <section class="grid gap-4 md:grid-cols-3">
      <router-link
        v-for="asset in CRYPTO_ASSETS"
        :key="asset.symbol"
        :to="`/trade/${asset.symbol}`"
        class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
      >
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ asset.displayName }}</p>
        <h2 class="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">
          {{ formatCurrency(getLatestCryptoPrice(asset.symbol)) }}
        </h2>
        <p class="mt-3 text-xs font-medium text-emerald-600">Simulated market feed</p>
      </router-link>
    </section>

    <section class="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
      <div class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="mb-4 flex items-center justify-between">
          <h1 class="text-xl font-semibold text-gray-900 dark:text-white">Active Contests</h1>
          <router-link class="text-sm font-medium text-blue-600" to="/contests">View all</router-link>
        </div>
        <div class="grid gap-3 md:grid-cols-2">
          <router-link
            v-for="contest in activeContests"
            :key="contest.id"
            :to="`/contests/${contest.id}`"
            class="rounded-lg border border-gray-100 p-4 dark:border-gray-800"
          >
            <h2 class="font-semibold text-gray-900 dark:text-white">{{ contest.title }}</h2>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
              {{ contest.participantCount }} participants · {{ formatCurrency(contest.initialCapital) }}
            </p>
            <p class="mt-3 text-xs uppercase text-gray-400">{{ contest.status }}</p>
          </router-link>
        </div>
      </div>

      <PortfolioSummary :portfolio="portfolio" :metrics="metrics" />
    </section>

    <section>
      <LeaderboardTable :rows="leaderboardRows" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import LeaderboardTable, { type LeaderboardRow } from '@/components/crypto/LeaderboardTable.vue'
import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { CRYPTO_ASSETS } from '@/constants/cryptoAssets'
import { CRYPTO_CONTESTS, DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { getLatestCryptoPrice } from '@/services/cryptoMarketData'
import { calculatePortfolioMetrics } from '@/services/tradingSimulator'
import { createInitialPortfolio, loadContestState } from '@/stores/cryptoContestStore'

const latestPrices = {
  BTCUSDT: getLatestCryptoPrice('BTCUSDT'),
  ETHUSDT: getLatestCryptoPrice('ETHUSDT'),
  SOLUSDT: getLatestCryptoPrice('SOLUSDT'),
}

const state = loadContestState()
const practiceContest = CRYPTO_CONTESTS.find((contest) => contest.id === DEFAULT_CONTEST_ID)!
const portfolio =
  state.portfolios[DEFAULT_CONTEST_ID] ??
  createInitialPortfolio(DEFAULT_CONTEST_ID, practiceContest.initialCapital)

const activeContests = computed(() =>
  CRYPTO_CONTESTS.filter((contest) => contest.status === 'practice' || contest.status === 'active'),
)
const metrics = computed(() => calculatePortfolioMetrics(portfolio, latestPrices))
const leaderboardRows: LeaderboardRow[] = [
  {
    user: '0x7A...91F2',
    equity: 11240,
    pnl: 1240,
    roi: 12.4,
    volume: 48200,
    tradeCount: 18,
    winRate: 61,
    maxDrawdown: 4.2,
    lastTrade: 'BTCUSDT buy',
  },
  {
    user: 'Practice You',
    equity: metrics.value.equity,
    pnl: metrics.value.pnl,
    roi: metrics.value.roi,
    volume: metrics.value.volume,
    tradeCount: metrics.value.tradeCount,
    winRate: 0,
    maxDrawdown: 0,
    lastTrade: portfolio.orders.at(-1)?.symbol ?? 'No trades',
  },
  {
    user: '0x2C...8AA0',
    equity: 9810,
    pnl: -190,
    roi: -1.9,
    volume: 13200,
    tradeCount: 6,
    winRate: 33,
    maxDrawdown: 6.8,
    lastTrade: 'SOLUSDT sell',
  },
]

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
