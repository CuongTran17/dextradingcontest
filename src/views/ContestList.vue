<template>
  <main class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Trading Contests</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
        Practice and contest arenas use virtual USDT_TEST only.
      </p>
    </div>

    <p v-if="loading" class="text-sm text-gray-500 dark:text-gray-400">Loading contests...</p>
    <p v-else-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>
    <template v-else>
    <section v-for="group in groupedContests" :key="group.status" class="space-y-3">
      <h2 class="text-sm font-semibold uppercase text-gray-500 dark:text-gray-400">
        {{ group.status }}
      </h2>
      <div class="grid gap-4 md:grid-cols-2">
        <router-link
          v-for="contest in group.contests"
          :key="contest.id"
          :to="`/contests/${contest.id}`"
          class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
        >
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white">{{ contest.title }}</h3>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
            {{ contest.symbols.join(', ') }} · {{ contest.participantCount }} participants
          </p>
          <p class="mt-4 text-sm font-medium text-blue-600">
            {{ formatCurrency(contest.initialCapital) }} initial capital
          </p>
        </router-link>
      </div>
    </section>
    </template>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchContests } from '@/services/cryptoContestApi'
import type { Contest, ContestStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const loading = ref(true)
const loadError = ref('')

onMounted(async () => {
  try {
    contests.value = await fetchContests()
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load contests'
  } finally {
    loading.value = false
  }
})

const statuses: ContestStatus[] = ['practice', 'upcoming', 'active', 'ended']
const groupedContests = computed(() =>
  statuses
    .map((status) => ({
      status,
      contests: contests.value.filter((contest) => contest.status === status),
    }))
    .filter((group) => group.contests.length > 0),
)

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
