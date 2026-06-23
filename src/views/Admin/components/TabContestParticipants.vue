<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Participants</h2>
    <div class="mt-4 grid gap-3">
      <div
        v-for="participant in participants"
        :key="participant.wallet"
        class="grid gap-2 rounded-lg border border-gray-100 p-4 text-sm dark:border-gray-800 md:grid-cols-5"
      >
        <span class="font-medium text-gray-900 dark:text-white">{{ participant.wallet }}</span>
        <span class="text-gray-500 dark:text-gray-400">{{ participant.contest }}</span>
        <span class="text-gray-700 dark:text-gray-300">{{ formatCurrency(participant.equity) }}</span>
        <span :class="participant.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'">{{ participant.roi }}% ROI</span>
        <span class="text-gray-500 dark:text-gray-400">{{ participant.tradeCount }} trades</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
const participants = [
  { wallet: '0x7A...91F2', contest: 'Summer Crypto Cup', equity: 11240, roi: 12.4, tradeCount: 18 },
  { wallet: '0xF1...0C29', contest: 'Practice Arena', equity: 10410, roi: 4.1, tradeCount: 9 },
  { wallet: '0x2C...8AA0', contest: 'Practice Arena', equity: 9810, roi: -1.9, tradeCount: 6 },
]

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}
</script>
