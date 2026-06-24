<template>
  <main class="space-y-6">
    <SimulationDisclaimer />

    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Trade Simulator</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ currentSymbol }}</p>
      </div>
      <div class="inline-flex w-fit rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
        <button
          v-for="option in timeframeOptions"
          :key="option"
          type="button"
          class="rounded-md px-3 py-1.5 text-sm font-medium"
          :class="timeframe === option ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white' : 'text-gray-500 dark:text-gray-400'"
          @click="timeframe = option"
        >
          {{ option }}
        </button>
      </div>
    </div>

    <section class="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
      <div class="space-y-6">
        <CryptoChart :symbol="currentSymbol" :timeframe="timeframe" />
        <OrderBook :symbol="currentSymbol" :limit="100" />
      </div>
      <div class="space-y-6">
        <OrderTicket
          :symbol="currentSymbol"
          :latest-price="latestPrice"
          :error="orderError"
          @submit="submitOrder"
        />
      </div>
    </section>

    <PortfolioSummary :portfolio="portfolio" :metrics="metrics" />
  </main>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import CryptoChart from '@/components/crypto/CryptoChart.vue'
import OrderBook from '@/components/crypto/OrderBook.vue'
import OrderTicket from '@/components/crypto/OrderTicket.vue'
import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { CRYPTO_ASSETS, DEFAULT_CRYPTO_SYMBOL } from '@/constants/cryptoAssets'
import { CRYPTO_CONTESTS, DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { fetchLatestCryptoPrices, getLatestCryptoPrice } from '@/services/cryptoMarketData'
import { calculatePortfolioMetrics, executeMarketOrder } from '@/services/tradingSimulator'
import {
  createInitialPortfolio,
  loadContestState,
  saveContestState,
  type CryptoContestState,
} from '@/stores/cryptoContestStore'
import type { CryptoSymbol, Timeframe, VirtualPortfolio } from '@/types/crypto'

const route = useRoute()
const timeframeOptions: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1D']
const timeframe = ref<Timeframe>('1h')
const orderError = ref('')
const livePrices = ref<Record<CryptoSymbol, number>>({
  BTCUSDT: getLatestCryptoPrice('BTCUSDT'),
  ETHUSDT: getLatestCryptoPrice('ETHUSDT'),
  SOLUSDT: getLatestCryptoPrice('SOLUSDT'),
  XRPUSDT: getLatestCryptoPrice('XRPUSDT'),
  BNBUSDT: getLatestCryptoPrice('BNBUSDT'),
})
let priceTimer: number | undefined

const currentSymbol = computed<CryptoSymbol>(() => {
  const routeSymbol = typeof route.params.symbol === 'string' ? route.params.symbol : DEFAULT_CRYPTO_SYMBOL
  return CRYPTO_ASSETS.some((asset) => asset.symbol === routeSymbol)
    ? (routeSymbol as CryptoSymbol)
    : DEFAULT_CRYPTO_SYMBOL
})

const latestPrice = computed(() => livePrices.value[currentSymbol.value])
const contest = CRYPTO_CONTESTS.find((item) => item.id === DEFAULT_CONTEST_ID)!
const state = ref<CryptoContestState>(loadContestState())
const portfolio = ref<VirtualPortfolio>(
  state.value.portfolios[DEFAULT_CONTEST_ID] ??
    createInitialPortfolio(DEFAULT_CONTEST_ID, contest.initialCapital),
)

const metrics = computed(() => calculatePortfolioMetrics(portfolio.value, livePrices.value))

function persistPortfolio() {
  state.value = {
    joinedContestIds: Array.from(new Set([...state.value.joinedContestIds, DEFAULT_CONTEST_ID])),
    portfolios: {
      ...state.value.portfolios,
      [DEFAULT_CONTEST_ID]: portfolio.value,
    },
  }
  saveContestState(state.value)
}

function submitOrder(order: { side: 'buy' | 'sell'; quantity: number }) {
  orderError.value = ''
  try {
    portfolio.value = executeMarketOrder(portfolio.value, {
      contestId: DEFAULT_CONTEST_ID,
      symbol: currentSymbol.value,
      side: order.side,
      quantity: order.quantity,
      latestPrice: latestPrice.value,
    })
    persistPortfolio()
  } catch (error) {
    orderError.value = error instanceof Error ? error.message : 'Unable to execute order'
  }
}

async function refreshLatestPrices() {
  const prices = await fetchLatestCryptoPrices([
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'XRPUSDT',
    'BNBUSDT',
  ])
  livePrices.value = {
    BTCUSDT: prices.BTCUSDT ?? getLatestCryptoPrice('BTCUSDT'),
    ETHUSDT: prices.ETHUSDT ?? getLatestCryptoPrice('ETHUSDT'),
    SOLUSDT: prices.SOLUSDT ?? getLatestCryptoPrice('SOLUSDT'),
    XRPUSDT: prices.XRPUSDT ?? getLatestCryptoPrice('XRPUSDT'),
    BNBUSDT: prices.BNBUSDT ?? getLatestCryptoPrice('BNBUSDT'),
  }
}

onMounted(() => {
  void refreshLatestPrices()
  priceTimer = window.setInterval(() => void refreshLatestPrices(), 5000)
})

watch(currentSymbol, () => {
  void refreshLatestPrices()
})

onBeforeUnmount(() => {
  if (priceTimer) window.clearInterval(priceTimer)
})
</script>
