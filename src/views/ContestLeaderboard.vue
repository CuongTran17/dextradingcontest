<template>
  <main class="space-y-6">
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-gray-200 pb-5 dark:border-gray-800 gap-4">
      <div>
        <h1 class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white flex items-center gap-3">
          Leaderboard
          <span
            v-if="status === 'connected'"
            class="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 ring-1 ring-inset ring-emerald-600/20 dark:bg-emerald-500/10 dark:text-emerald-400 dark:ring-emerald-500/20"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
            LIVE
          </span>
          <span
            v-else-if="status === 'connecting'"
            class="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-600/20 dark:bg-amber-500/10 dark:text-amber-400 dark:ring-amber-500/20"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-amber-500 animate-pulse"></span>
            Connecting
          </span>
          <span
            v-else
            class="inline-flex items-center gap-1.5 rounded-full bg-rose-50 px-2.5 py-1 text-xs font-medium text-rose-700 ring-1 ring-inset ring-rose-600/20 dark:bg-rose-500/10 dark:text-rose-400 dark:ring-rose-500/20"
          >
            <span class="h-1.5 w-1.5 rounded-full bg-rose-500"></span>
            Cached (15s TTL)
          </span>
        </h1>
        <div class="mt-1 flex flex-wrap items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
          <span>Contest: {{ contestId }}</span>
          <span>•</span>
          <span data-test="last-updated-text">Cập nhật lần cuối: {{ formattedLastUpdated }}</span>
        </div>
      </div>

      <div class="flex items-center gap-3 self-start sm:self-center">
        <button
          type="button"
          data-test="refresh-button"
          :disabled="isRefreshing"
          @click="handleRefresh"
          class="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700 transition-colors"
        >
          <svg
            class="h-3.5 w-3.5"
            :class="{ 'animate-spin': isRefreshing }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
          {{ isRefreshing ? 'Đang tải...' : 'Tải lại' }}
        </button>

        <div class="flex space-x-1 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-800/80">
          <button
            v-for="sortOption in (['equity', 'pnl', 'roi'] as const)"
            :key="sortOption"
            type="button"
            @click="setSortBy(sortOption)"
            class="rounded-md px-3 py-1.5 text-xs font-semibold uppercase tracking-wider transition-all duration-200 cursor-pointer"
            :class="sortBy === sortOption
              ? 'bg-white text-gray-900 shadow-sm dark:bg-gray-700 dark:text-white'
              : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200'"
          >
            {{ sortOption === 'equity' ? 'Equity' : sortOption === 'pnl' ? 'PnL' : 'ROI' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="rows.length === 0 && status === 'connecting'" class="flex h-32 items-center justify-center">
      <p class="text-sm text-gray-500 dark:text-gray-400">Connecting to live leaderboard feed...</p>
    </div>
    <LeaderboardTable v-else :rows="rows" :sortBy="sortBy" />
  </main>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import LeaderboardTable from '@/components/crypto/LeaderboardTable.vue'
import { useLeaderboardRealtime } from '@/composables/useLeaderboardRealtime'
import { DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'

const route = useRoute()
const contestId = computed(() => String(route.params.contestId || DEFAULT_CONTEST_ID))
const isRefreshing = ref(false)

const { rows, sortBy, status, lastUpdated, setSortBy, refresh } = useLeaderboardRealtime(contestId)

const formattedLastUpdated = computed(() => {
  if (!lastUpdated?.value) return 'vừa xong'
  return lastUpdated.value.toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})

async function handleRefresh() {
  isRefreshing.value = true
  try {
    await refresh()
  } finally {
    isRefreshing.value = false
  }
}
</script>
