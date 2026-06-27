<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Contest Management</h2>
      <button
        class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
        :disabled="loading"
        @click="loadContests"
      >
        Refresh
      </button>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading contests...</p>

    <div v-else class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
        <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th class="px-3 py-2">Title</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Initial Capital</th>
            <th class="px-3 py-2">Symbols</th>
            <th class="px-3 py-2">Start / End</th>
            <th class="px-3 py-2">Participants</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <tr v-for="contest in contests" :key="contest.id">
            <td class="px-3 py-3 font-medium text-gray-900 dark:text-white">{{ contest.title }}</td>
            <td class="px-3 py-3">
              <select
                class="rounded border border-gray-300 bg-white px-2 py-1 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                :value="contest.rawStatus ?? contest.status"
                @change="changeStatus(contest, ($event.target as HTMLSelectElement).value as RawContestStatus)"
              >
                <option value="draft">draft</option>
                <option value="scheduled">scheduled</option>
                <option value="active">active</option>
                <option value="settling">settling</option>
                <option value="completed">completed</option>
                <option value="cancelled">cancelled</option>
              </select>
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(contest.initialCapital) }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.symbols.join(', ') }}</td>
            <td class="px-3 py-3 text-gray-500 dark:text-gray-400">{{ contest.startsAt || '-' }} / {{ contest.endsAt || '-' }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.participantCount }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <form class="mt-5 grid gap-3 border-t border-gray-100 pt-4 dark:border-gray-800 md:grid-cols-3" @submit.prevent="createContest">
      <input
        v-model="form.slug"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        placeholder="contest-slug"
        required
      >
      <input
        v-model="form.title"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        placeholder="Contest title"
        required
      >
      <input
        v-model.number="form.initialBalance"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        min="1"
        type="number"
      >
      <input
        v-model="form.symbolsText"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white md:col-span-2"
        placeholder="BTCUSDT,ETHUSDT"
      >
      <button class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white" type="submit">
        Create Contest
      </button>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  createAdminCryptoContest,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
} from '@/services/cryptoContestApi'
import type { Contest, CryptoSymbol, RawContestStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const loading = ref(false)
const error = ref('')
const form = ref({
  slug: '',
  title: '',
  mode: 'contest' as const,
  status: 'draft' as const,
  initialBalance: 10000,
  symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
})

async function loadContests() {
  loading.value = true
  error.value = ''
  try {
    contests.value = await fetchAdminCryptoContests()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contests'
  } finally {
    loading.value = false
  }
}

async function createContest() {
  error.value = ''
  try {
    const symbols = form.value.symbolsText
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean) as CryptoSymbol[]
    const created = await createAdminCryptoContest({
      slug: form.value.slug,
      title: form.value.title,
      mode: form.value.mode,
      status: form.value.status,
      initialBalance: form.value.initialBalance,
      symbols,
    })
    contests.value = [created, ...contests.value]
    form.value.slug = ''
    form.value.title = ''
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to create contest'
  }
}

async function changeStatus(contest: Contest, status: RawContestStatus) {
  error.value = ''
  try {
    const updated = await setAdminCryptoContestStatus(contest.id, status)
    contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to update contest status'
  }
}

onMounted(loadContests)

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
