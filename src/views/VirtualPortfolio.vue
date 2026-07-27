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

    <!-- Equity Curve Section -->
    <section v-if="account" class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="mb-4 flex items-center justify-between">
        <div>
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Equity Growth Curve</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400">Historical account value trajectory across filled trades</p>
        </div>
        <span class="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-500/10 px-2.5 py-1 rounded-full">
          Current Equity: {{ formatCurrency(metrics.equity) }}
        </span>
      </div>

      <!-- SVG Equity Chart -->
      <div class="h-44 w-full relative">
        <svg v-if="equityPoints.length > 1" class="h-full w-full overflow-visible" viewBox="0 0 500 120" preserveAspectRatio="none">
          <defs>
            <linearGradient id="equityGrad" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stop-color="#10b981" stop-opacity="0.25" />
              <stop offset="100%" stop-color="#10b981" stop-opacity="0.0" />
            </linearGradient>
          </defs>
          <polygon :points="polygonPoints" fill="url(#equityGrad)" />
          <polyline :points="polylinePoints" fill="none" stroke="#10b981" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <div v-else class="flex h-full items-center justify-center text-xs text-gray-400">
          Execute trades to visualize your equity growth trajectory over time.
        </div>
      </div>
    </section>

    <PortfolioSummary v-if="account" :account="account" :metrics="metrics" @cancel-order="handleCancelOrder" />
    <p v-else class="text-sm text-gray-500 dark:text-gray-400">{{ accountMessage }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import PortfolioSummary from '@/components/crypto/PortfolioSummary.vue'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import { cancelCryptoOrder, getCryptoAccount } from '@/services/cryptoTradingApi'
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

const equityPoints = computed(() => {
  if (!account.value) return []
  const initial = account.value.initialEquity || 10000
  const points = [initial]
  let running = initial
  const filledOrders = account.value.orders.filter((o) => o.status === 'filled').slice().reverse()
  for (const order of filledOrders) {
    const pnlDelta = order.side === 'sell' ? order.notional - order.fee : -order.fee
    running += pnlDelta
    points.push(running)
  }
  if (points.length === 1) {
    points.push(account.value.equity)
  }
  return points
})

const polylinePoints = computed(() => {
  const pts = equityPoints.value
  if (pts.length <= 1) return ''
  const min = Math.min(...pts)
  const max = Math.max(...pts)
  const range = max - min || 1
  return pts
    .map((val, index) => {
      const x = (index / (pts.length - 1)) * 500
      const y = 110 - ((val - min) / range) * 100
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
})

const polygonPoints = computed(() => {
  const line = polylinePoints.value
  if (!line) return ''
  return `0,120 ${line} 500,120`
})

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

async function handleCancelOrder(orderId: string) {
  try {
    await cancelCryptoOrder(DEFAULT_CONTEST_ID, orderId)
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    console.error('Failed to cancel order:', error)
  }
}

onMounted(async () => {
  try {
    account.value = await getCryptoAccount(DEFAULT_CONTEST_ID)
  } catch (error) {
    accountMessage.value = error instanceof Error ? error.message : 'Unable to load practice account'
  }
})
</script>
