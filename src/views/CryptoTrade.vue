<template>
  <main class="space-y-6">
    <SimulationDisclaimer />

    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Trade Simulator</h1>
        <div class="mt-1 flex flex-wrap items-center gap-2 text-sm">
          <span class="text-gray-500 dark:text-gray-400">{{ currentSymbol }}</span>
          <span
            data-test="realtime-status"
            class="inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium"
            :class="realtimeStatusClass"
          >
            <span class="h-1.5 w-1.5 rounded-full" :class="realtimeDotClass"></span>
            {{ realtimeStatusText }}
          </span>
        </div>
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
import { computed, onMounted, ref, watch } from 'vue'
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
  connectCryptoRealtime,
  cryptoRealtimeState,
  subscribeCryptoRealtimeSymbol,
} from '@/services/cryptoRealtime'
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
const fallbackPrices = ref<Record<CryptoSymbol, number>>({
  BTCUSDT: 0,
  ETHUSDT: 0,
  SOLUSDT: 0,
  XRPUSDT: 0,
  BNBUSDT: 0,
})

const currentSymbol = computed<CryptoSymbol>(() => {
  const routeSymbol = typeof route.params.symbol === 'string' ? route.params.symbol : DEFAULT_CRYPTO_SYMBOL
  return CRYPTO_ASSETS.some((asset) => asset.symbol === routeSymbol)
    ? (routeSymbol as CryptoSymbol)
    : DEFAULT_CRYPTO_SYMBOL
})

const latestPrice = computed(
  () => cryptoRealtimeState.prices[currentSymbol.value] ?? fallbackPrices.value[currentSymbol.value],
)
const realtimeStatusText = computed(() => {
  if (cryptoRealtimeState.status === 'connected') return 'Live'
  if (cryptoRealtimeState.status === 'connecting') return 'Connecting'
  if (cryptoRealtimeState.status === 'reconnecting') return 'Reconnecting'
  return 'REST fallback'
})
const realtimeStatusClass = computed(() => {
  if (cryptoRealtimeState.status === 'connected') {
    return 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300'
  }
  if (cryptoRealtimeState.status === 'connecting' || cryptoRealtimeState.status === 'reconnecting') {
    return 'bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300'
  }
  return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
})
const realtimeDotClass = computed(() => {
  if (cryptoRealtimeState.status === 'connected') return 'bg-emerald-500'
  if (cryptoRealtimeState.status === 'connecting' || cryptoRealtimeState.status === 'reconnecting') {
    return 'bg-amber-500'
  }
  return 'bg-gray-400'
})
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
  fallbackPrices.value = {
    BTCUSDT: prices.BTCUSDT ?? fallbackPrices.value.BTCUSDT,
    ETHUSDT: prices.ETHUSDT ?? fallbackPrices.value.ETHUSDT,
    SOLUSDT: prices.SOLUSDT ?? fallbackPrices.value.SOLUSDT,
    XRPUSDT: prices.XRPUSDT ?? fallbackPrices.value.XRPUSDT,
    BNBUSDT: prices.BNBUSDT ?? fallbackPrices.value.BNBUSDT,
  }
  priceLoading.value = false
}

onMounted(() => {
  void loadAccount()
  connectCryptoRealtime()
  subscribeCryptoRealtimeSymbol(currentSymbol.value)
  void refreshLatestPrices()
})

watch(currentSymbol, () => {
  subscribeCryptoRealtimeSymbol(currentSymbol.value)
  void refreshLatestPrices()
})
</script>
