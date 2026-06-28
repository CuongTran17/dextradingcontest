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
            <th class="px-3 py-2">Actions</th>
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
            <td class="px-3 py-3">
              <button
                class="rounded border border-gray-300 px-2 py-1 text-xs font-semibold text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-gray-800"
                type="button"
                :data-test="`edit-contest-${contest.id}`"
                @click="editContest(contest)"
              >
                Edit
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <form
      class="mt-5 grid gap-3 border-t border-gray-100 pt-4 dark:border-gray-800 md:grid-cols-3"
      data-test="contest-form"
      @submit.prevent="saveContest"
    >
      <input
        v-model="form.slug"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-slug"
        :disabled="Boolean(editingContestId)"
        placeholder="contest-slug"
        required
      >
      <input
        v-model="form.title"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-title"
        placeholder="Contest title"
        required
      >
      <input
        v-model.number="form.initialBalance"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-initial-balance"
        :disabled="Boolean(editingContestId)"
        min="1"
        type="number"
      >
      <input
        v-model="form.symbolsText"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white md:col-span-2"
        data-test="contest-symbols"
        placeholder="BTCUSDT,ETHUSDT"
      >
      <input
        v-model="form.startsAt"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-starts-at"
        type="datetime-local"
      >
      <input
        v-model="form.endsAt"
        class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        data-test="contest-ends-at"
        type="datetime-local"
      >
      <div class="flex gap-2">
        <button class="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white" type="submit">
          {{ editingContestId ? 'Update Contest' : 'Create Contest' }}
        </button>
        <button
          v-if="editingContestId"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
          type="button"
          @click="resetForm"
        >
          Cancel
        </button>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  createAdminCryptoContest,
  fetchAdminCryptoContests,
  setAdminCryptoContestStatus,
  updateAdminCryptoContest,
} from '@/services/cryptoContestApi'
import type { Contest, CryptoSymbol, RawContestStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const loading = ref(false)
const error = ref('')
const editingContestId = ref('')
const form = ref({
  slug: '',
  title: '',
  mode: 'contest' as const,
  status: 'draft' as const,
  initialBalance: 10000,
  symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
  startsAt: '',
  endsAt: '',
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

async function saveContest() {
  error.value = ''
  try {
    const symbols = form.value.symbolsText
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean) as CryptoSymbol[]
    const startsAt = toIsoDateTime(form.value.startsAt)
    const endsAt = toIsoDateTime(form.value.endsAt)

    if (editingContestId.value) {
      const updated = await updateAdminCryptoContest(editingContestId.value, {
        title: form.value.title,
        symbols,
        startsAt,
        endsAt,
      })
      contests.value = contests.value.map((item) => (item.id === updated.id ? updated : item))
      resetForm()
      return
    }

    const created = await createAdminCryptoContest({
      slug: form.value.slug,
      title: form.value.title,
      mode: form.value.mode,
      status: form.value.status,
      initialBalance: form.value.initialBalance,
      symbols,
      startsAt,
      endsAt,
    })
    contests.value = [created, ...contests.value]
    resetForm()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to save contest'
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

function editContest(contest: Contest) {
  editingContestId.value = contest.id
  form.value.slug = contest.id
  form.value.title = contest.title
  form.value.initialBalance = contest.initialCapital
  form.value.symbolsText = contest.symbols.join(',')
  form.value.startsAt = toDateTimeLocal(contest.startsAt)
  form.value.endsAt = toDateTimeLocal(contest.endsAt)
}

function resetForm() {
  editingContestId.value = ''
  form.value = {
    slug: '',
    title: '',
    mode: 'contest',
    status: 'draft',
    initialBalance: 10000,
    symbolsText: 'BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT',
    startsAt: '',
    endsAt: '',
  }
}

function toIsoDateTime(value: string): string | null {
  if (!value) return null
  return new Date(value).toISOString()
}

function toDateTimeLocal(value: string): string {
  if (!value) return ''
  const date = new Date(value)
  const offsetMs = date.getTimezoneOffset() * 60_000
  return new Date(date.getTime() - offsetMs).toISOString().slice(0, 16)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
