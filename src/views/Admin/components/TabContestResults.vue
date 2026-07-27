<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Contest Results</h2>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Rankings from real participant equity and ROI.</p>
      </div>
      <select
        v-model="selectedContestId"
        class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
        @change="loadResults"
      >
        <option v-for="contest in contests" :key="contest.id" :value="contest.id">
          {{ contest.title }}
        </option>
      </select>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading results...</p>
    <p v-else-if="!selectedContestId" class="mt-4 text-sm text-gray-500 dark:text-gray-400">No contests available.</p>
    <div v-else class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
        <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th class="px-3 py-2">Rank</th>
            <th class="px-3 py-2">User</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Equity</th>
            <th class="px-3 py-2">PnL</th>
            <th class="px-3 py-2">ROI</th>
            <th class="px-3 py-2">Volume</th>
            <th class="px-3 py-2">Trades</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <tr v-for="result in rankedResults" :key="result.userId">
            <td class="px-3 py-3 font-semibold text-gray-900 dark:text-white">#{{ result.rank }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ result.user }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ result.status }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(result.equity) }}</td>
            <td
              class="px-3 py-3 font-medium"
              :class="result.pnl >= 0 ? 'text-emerald-600' : 'text-rose-600'"
            >
              {{ formatCurrency(result.pnl) }}
            </td>
            <td
              class="px-3 py-3 font-medium"
              :class="result.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'"
            >
              {{ result.roi.toFixed(2) }}%
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(result.volume) }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ result.tradeCount }}</td>
          </tr>
        </tbody>
      </table>
      <p v-if="rankedResults.length === 0" class="py-6 text-center text-sm text-gray-500">No participants found.</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  fetchAdminContestParticipants,
  fetchAdminCryptoContests,
} from '@/services/cryptoContestApi'
import type { AdminContestParticipant, Contest } from '@/types/crypto'

const contests = ref<Contest[]>([])
const results = ref<AdminContestParticipant[]>([])
const selectedContestId = ref('')
const loading = ref(false)
const error = ref('')

const rankedResults = computed(() =>
  results.value
    .slice()
    .sort((left, right) => right.equity - left.equity)
    .map((result, index) => ({ ...result, rank: index + 1 })),
)

onMounted(async () => {
  loading.value = true
  try {
    contests.value = await fetchAdminCryptoContests()
    selectedContestId.value = contests.value[0]?.id ?? ''
    if (selectedContestId.value) {
      results.value = await fetchAdminContestParticipants(selectedContestId.value)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contest results'
  } finally {
    loading.value = false
  }
})

async function loadResults() {
  if (!selectedContestId.value) return
  loading.value = true
  error.value = ''
  try {
    results.value = await fetchAdminContestParticipants(selectedContestId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contest results'
  } finally {
    loading.value = false
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
