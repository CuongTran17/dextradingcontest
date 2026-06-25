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
          :submitting="orderSubmitting"
          :disabled="accountLoading || priceLoading || latestPrice <= 0 || !account"
          @submit="submitOrder"
        />
      </div>
    </section>

    <PortfolioSummary v-if="account" :account="account" :metrics="metrics" />
    <p v-else class="text-sm text-gray-500 dark:text-gray-400">
      {{ accountLoading ? 'Loading trading account...' : accountError }}
    </p>
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
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { ApiError } from '@/services/httpClient'
import { fetchLatestCryptoPrices } from '@/services/cryptoMarketData'
import {
  getCryptoAccount,
  joinCryptoContest,
  placeCryptoMarketOrder,
} from '@/services/cryptoTradingApi'
import type { CryptoSymbol, Timeframe, TradingAccount } from '@/types/crypto'

const route = useRoute()
const timeframeOptions: Timeframe[] = ['1m', '5m', '15m', '1h', '4h', '1D']
const timeframe = ref<Timeframe>('1h')
const orderError = ref('')
const accountError = ref('')
const accountLoading = ref(true)
const priceLoading = ref(true)
const orderSubmitting = ref(false)
const account = ref<TradingAccount | null>(null)
const livePrices = ref<Record<CryptoSymbol, number>>({
  BTCUSDT: 0,
  ETHUSDT: 0,
  SOLUSDT: 0,
  XRPUSDT: 0,
  BNBUSDT: 0,
})
let priceTimer: number | undefined

const currentSymbol = computed<CryptoSymbol>(() => {
  const routeSymbol = typeof route.params.symbol === 'string' ? route.params.symbol : DEFAULT_CRYPTO_SYMBOL
  return CRYPTO_ASSETS.some((asset) => asset.symbol === routeSymbol)
    ? (routeSymbol as CryptoSymbol)
    : DEFAULT_CRYPTO_SYMBOL
})

const latestPrice = computed(() => livePrices.value[currentSymbol.value])
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

async function submitOrder(order: { side: 'buy' | 'sell'; quantity: number }) {
  if (!account.value || orderSubmitting.value) return

  orderError.value = ''
  orderSubmitting.value = true
  try {
    await placeCryptoMarketOrder({
      contestId: DEFAULT_CONTEST_ID,
      clientOrderId: crypto.randomUUID(),
      symbol: currentSymbol.value,
      side: order.side,
      quantity: order.quantity,
    })
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    orderError.value = error instanceof Error ? error.message : 'Unable to execute order'
  } finally {
    orderSubmitting.value = false
  }
}

async function loadAccount() {
  accountLoading.value = true
  accountError.value = ''
  try {
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      account.value = await joinCryptoContest(DEFAULT_CONTEST_ID)
    } else {
      accountError.value = error instanceof Error ? error.message : 'Unable to load trading account'
    }
  } finally {
    accountLoading.value = false
  }
}

async function refreshLatestPrices() {
  priceLoading.value = true
  const prices = await fetchLatestCryptoPrices([
    'BTCUSDT',
    'ETHUSDT',
    'SOLUSDT',
    'XRPUSDT',
    'BNBUSDT',
  ])
  livePrices.value = {
    BTCUSDT: prices.BTCUSDT ?? livePrices.value.BTCUSDT,
    ETHUSDT: prices.ETHUSDT ?? livePrices.value.ETHUSDT,
    SOLUSDT: prices.SOLUSDT ?? livePrices.value.SOLUSDT,
    XRPUSDT: prices.XRPUSDT ?? livePrices.value.XRPUSDT,
    BNBUSDT: prices.BNBUSDT ?? livePrices.value.BNBUSDT,
  }
  priceLoading.value = false
}

onMounted(() => {
  void loadAccount()
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
