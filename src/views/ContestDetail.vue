<template>
  <main class="space-y-6">
    <SimulationDisclaimer />
    <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p class="text-sm uppercase text-gray-500 dark:text-gray-400">{{ contest.status }}</p>
          <h1 class="mt-1 text-2xl font-semibold text-gray-900 dark:text-white">{{ contest.title }}</h1>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Trade {{ contest.symbols.join(', ') }} with {{ formatCurrency(contest.initialCapital) }} virtual capital.
          </p>
        </div>
        <div class="flex gap-2">
          <button
            class="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white"
            @click="joinContest"
          >
            Join Contest
          </button>
          <router-link
            class="rounded-lg border border-gray-300 px-4 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
            :to="`/contests/${contest.id}/leaderboard`"
          >
            Leaderboard
          </router-link>
        </div>
      </div>

      <dl class="mt-6 grid gap-3 md:grid-cols-4">
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Starts</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.startsAt }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Ends</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.endsAt }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Participants</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.participantCount }}</dd>
        </div>
        <div class="rounded-lg bg-gray-50 p-3 dark:bg-gray-900">
          <dt class="text-xs text-gray-500 dark:text-gray-400">Mode</dt>
          <dd class="mt-1 text-sm font-semibold text-gray-900 dark:text-white">{{ contest.mode }}</dd>
        </div>
      </dl>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { CRYPTO_CONTESTS, DEFAULT_CONTEST_ID } from '@/constants/cryptoContests'
import {
  createInitialPortfolio,
  loadContestState,
  saveContestState,
} from '@/stores/cryptoContestStore'

const route = useRoute()
const contest = computed(
  () =>
    CRYPTO_CONTESTS.find((item) => item.id === route.params.contestId) ??
    CRYPTO_CONTESTS.find((item) => item.id === DEFAULT_CONTEST_ID)!,
)

function joinContest() {
  const state = loadContestState()
  const selectedContest = contest.value
  saveContestState({
    joinedContestIds: Array.from(new Set([...state.joinedContestIds, selectedContest.id])),
    portfolios: {
      ...state.portfolios,
      [selectedContest.id]:
        state.portfolios[selectedContest.id] ??
        createInitialPortfolio(selectedContest.id, selectedContest.initialCapital),
    },
  })
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
