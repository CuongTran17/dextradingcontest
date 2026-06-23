<template>
  <div class="overflow-hidden rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]">
    <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
      <thead class="bg-gray-50 text-left text-xs uppercase text-gray-500 dark:bg-gray-900 dark:text-gray-400">
        <tr>
          <th class="px-4 py-3">Rank</th>
          <th class="px-4 py-3">User / Wallet</th>
          <th class="px-4 py-3">Equity</th>
          <th class="px-4 py-3">PnL</th>
          <th class="px-4 py-3">ROI</th>
          <th class="px-4 py-3">Volume</th>
          <th class="px-4 py-3">Trades</th>
          <th class="px-4 py-3">Win Rate</th>
          <th class="px-4 py-3">Max DD</th>
          <th class="px-4 py-3">Last Trade</th>
        </tr>
      </thead>
      <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
        <tr v-for="(row, index) in sortedRows" :key="row.user">
          <td class="px-4 py-3 font-semibold text-gray-900 dark:text-white">#{{ index + 1 }}</td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ row.user }}</td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(row.equity) }}</td>
          <td class="px-4 py-3" :class="row.pnl >= 0 ? 'text-emerald-600' : 'text-rose-600'">
            {{ formatCurrency(row.pnl) }}
          </td>
          <td class="px-4 py-3 font-semibold" :class="row.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'">
            {{ row.roi.toFixed(2) }}%
          </td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(row.volume) }}</td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ row.tradeCount }}</td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ row.winRate }}%</td>
          <td class="px-4 py-3 text-gray-700 dark:text-gray-300">{{ row.maxDrawdown }}%</td>
          <td class="px-4 py-3 text-gray-500 dark:text-gray-400">{{ row.lastTrade }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

export interface LeaderboardRow {
  user: string
  equity: number
  pnl: number
  roi: number
  volume: number
  tradeCount: number
  winRate: number
  maxDrawdown: number
  lastTrade: string
}

const props = defineProps<{ rows: LeaderboardRow[] }>()
const sortedRows = computed(() => [...props.rows].sort((a, b) => b.roi - a.roi))

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
