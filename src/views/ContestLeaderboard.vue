<template>
  <main class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Leaderboard</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ contestId }}</p>
    </div>
    <LeaderboardTable :rows="rows" />
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import LeaderboardTable, { type LeaderboardRow } from '@/components/crypto/LeaderboardTable.vue'

const route = useRoute()
const contestId = computed(() => route.params.contestId)
const rows: LeaderboardRow[] = [
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
    user: '0xF1...0C29',
    equity: 10410,
    pnl: 410,
    roi: 4.1,
    volume: 23500,
    tradeCount: 9,
    winRate: 55,
    maxDrawdown: 3.1,
    lastTrade: 'ETHUSDT buy',
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
</script>
