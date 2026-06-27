<template>
  <main class="space-y-6">
    <SimulationDisclaimer />
    <p v-if="loading" class="text-sm text-gray-500 dark:text-gray-400">Loading contest...</p>
    <p v-else-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>
    <section
      v-else-if="contest"
      class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
    >
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
            :disabled="joining || joined"
            @click="joinContest"
          >
            {{ joined ? 'Joined' : joining ? 'Joining...' : 'Join Contest' }}
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
      <p v-if="joinError" class="mt-4 text-sm text-rose-600">{{ joinError }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { fetchContest } from '@/services/cryptoContestApi'
import { joinCryptoContest } from '@/services/cryptoTradingApi'
import type { Contest } from '@/types/crypto'

const route = useRoute()
const contest = ref<Contest | null>(null)
const loading = ref(true)
const loadError = ref('')
const joining = ref(false)
const joined = ref(false)
const joinError = ref('')
const contestId = computed(() => String(route.params.contestId || 'practice-arena'))

onMounted(async () => {
  try {
    contest.value = await fetchContest(contestId.value)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load contest'
  } finally {
    loading.value = false
  }
})

async function joinContest() {
  if (joining.value || joined.value || !contest.value) return

  joining.value = true
  joinError.value = ''
  try {
    await joinCryptoContest(contest.value.id)
    joined.value = true
  } catch (error) {
    joinError.value = error instanceof Error ? error.message : 'Unable to join contest'
  } finally {
    joining.value = false
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
