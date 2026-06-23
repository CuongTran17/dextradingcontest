<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Virtual Portfolio</h2>
      <span :class="metrics.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'" class="text-sm font-semibold">
        {{ metrics.roi.toFixed(2) }}% ROI
      </span>
    </div>

    <dl class="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
      <div v-for="item in summaryItems" :key="item.label" class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
        <dt class="text-xs text-gray-500 dark:text-gray-400">{{ item.label }}</dt>
        <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ item.value }}</dd>
      </div>
    </dl>

    <div class="mt-5 grid gap-4 lg:grid-cols-2">
      <div>
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Positions</h3>
        <div class="mt-2 space-y-2">
          <p v-if="portfolio.positions.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
            No open positions.
          </p>
          <div
            v-for="position in portfolio.positions"
            :key="position.symbol"
            class="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800"
          >
            <span class="font-medium text-gray-900 dark:text-white">{{ position.symbol }}</span>
            <span class="text-gray-500 dark:text-gray-400">
              {{ position.quantity }} @ {{ formatCurrency(position.averageEntry) }}
            </span>
          </div>
        </div>
      </div>

      <div>
        <h3 class="text-sm font-semibold text-gray-700 dark:text-gray-300">Recent Orders</h3>
        <div class="mt-2 space-y-2">
          <p v-if="portfolio.orders.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
            No orders yet.
          </p>
          <div
            v-for="order in recentOrders"
            :key="order.id"
            class="flex items-center justify-between rounded-lg border border-gray-100 px-3 py-2 text-sm dark:border-gray-800"
          >
            <span :class="order.side === 'buy' ? 'text-emerald-600' : 'text-rose-600'" class="font-semibold">
              {{ order.side.toUpperCase() }} {{ order.symbol }}
            </span>
            <span class="text-gray-500 dark:text-gray-400">{{ formatCurrency(order.notional) }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'

import type { VirtualPortfolio } from '@/types/crypto'

const props = defineProps<{
  portfolio: VirtualPortfolio
  metrics: {
    cash: number
    positionsValue: number
    equity: number
    pnl: number
    roi: number
    volume: number
    tradeCount: number
  }
}>()

const recentOrders = computed(() => props.portfolio.orders.slice(-5).reverse())
const summaryItems = computed(() => [
  { label: 'Cash', value: formatCurrency(props.metrics.cash) },
  { label: 'Equity', value: formatCurrency(props.metrics.equity) },
  { label: 'PnL', value: formatCurrency(props.metrics.pnl) },
  { label: 'Trades', value: props.metrics.tradeCount.toString() },
])

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
