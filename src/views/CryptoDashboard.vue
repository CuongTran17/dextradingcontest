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
          {{ formatAssetPrice(asset.symbol) }}
        </h2>
        <p class="mt-3 text-xs font-medium text-emerald-600">Binance Spot market feed</p>
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

      <PortfolioSummary v-if="account" :account="account" :metrics="metrics" />
      <div
        v-else
        class="border-l border-gray-200 px-5 py-4 text-sm text-gray-500 dark:border-gray-800 dark:text-gray-400"
      >
        {{ accountMessage }}
      </div>
    </section>

    <section>
      <LeaderboardTable :rows="leaderboardRows" />
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import LeaderboardTable from '@/components/crypto/LeaderboardTable.vue'
import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { CRYPTO_ASSETS } from '@/constants/cryptoAssets'
import { CRYPTO_CONTESTS, DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { isLoggedIn } from '@/services/authApi'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import { getCryptoAccount } from '@/services/cryptoTradingApi'
import type { CryptoSymbol, LeaderboardRow, TradingAccount } from '@/types/crypto'

const account = ref<TradingAccount | null>(null)
const assetPrices = ref<Record<CryptoSymbol, number>>({
  BTCUSDT: 0,
  ETHUSDT: 0,
  SOLUSDT: 0,
  XRPUSDT: 0,
  BNBUSDT: 0,
})
const accountMessage = ref(
  isLoggedIn()
    ? 'Loading your practice account...'
    : 'Sign in to view your persistent practice portfolio.',
)

const activeContests = computed(() =>
  CRYPTO_CONTESTS.filter((contest) => contest.status === 'practice' || contest.status === 'active'),
)
const metrics = computed(() => accountMetrics(account.value))
const leaderboardRows = computed<LeaderboardRow[]>(() => {
  const rows: LeaderboardRow[] = [
    {
      rank: 1,
      user: '0x7A...91F2',
      equity: 11240,
      pnl: 1240,
      roi: 12.4,
      volume: 48200,
      tradeCount: 18,
      lastTrade: 'BTCUSDT buy',
    },
  ]
  if (account.value) {
    rows.push({
      rank: rows.length + 1,
      user: 'Practice You',
      equity: metrics.value.equity,
      pnl: metrics.value.pnl,
      roi: metrics.value.roi,
      volume: metrics.value.volume,
      tradeCount: metrics.value.tradeCount,
      lastTrade: account.value.orders[0]?.symbol ?? 'No trades',
    })
  }
  return rows
})

onMounted(async () => {
  const prices = await fetchLatestCryptoPrices(CRYPTO_ASSETS.map((asset) => asset.symbol))
  for (const asset of CRYPTO_ASSETS) {
    const price = prices[asset.symbol]
    if (typeof price === 'number' && price > 0) {
      assetPrices.value[asset.symbol] = price
    }
  }

  if (!isLoggedIn()) return
  try {
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    accountMessage.value = error instanceof Error ? error.message : 'Unable to load practice account'
  }
})

function formatAssetPrice(symbol: CryptoSymbol): string {
  const price = assetPrices.value[symbol]
  return price > 0 ? formatCurrency(price) : '--'
}

function accountMetrics(current: TradingAccount | null) {
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
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
