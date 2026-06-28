<template>
  <section class="space-y-5">
    <div class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Admin Overview</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Users, contests, accounts, and virtual equity.</p>
        </div>
        <button
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 disabled:opacity-60 dark:border-gray-700 dark:text-gray-200"
          :disabled="loading"
          @click="loadOverview"
        >
          Refresh
        </button>
      </div>

      <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
      <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading overview...</p>

      <div v-else class="mt-5 grid gap-4 md:grid-cols-3">
        <div
          v-for="card in cards"
          :key="card.label"
          class="rounded-lg border border-gray-100 p-4 dark:border-gray-800"
        >
          <p class="text-xs uppercase text-gray-500 dark:text-gray-400">{{ card.label }}</p>
          <p class="mt-2 text-2xl font-semibold text-gray-900 dark:text-white">{{ card.value }}</p>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ card.detail }}</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchAdminOverview } from '@/services/adminDashboardApi'
import type { AdminOverview } from '@/types/crypto'

const overview = ref<AdminOverview | null>(null)
const loading = ref(false)
const error = ref('')

const cards = computed(() => [
  {
    label: 'Users',
    value: overview.value ? overview.value.users.total.toLocaleString('en-US') : '-',
    detail: overview.value
      ? `${overview.value.users.admins} admins, ${overview.value.users.locked} locked`
      : 'No data',
  },
  {
    label: 'Contests',
    value: overview.value ? overview.value.contests.total.toLocaleString('en-US') : '-',
    detail: overview.value
      ? `${overview.value.contests.active} active, ${overview.value.contests.participants} participants`
      : 'No data',
  },
  {
    label: 'Virtual Equity',
    value: overview.value ? formatCurrency(overview.value.accounts.totalEquity) : '-',
    detail: overview.value
      ? `${overview.value.accounts.active} active accounts of ${overview.value.accounts.total}`
      : 'No data',
  },
])

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    overview.value = await fetchAdminOverview()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load admin overview'
  } finally {
    loading.value = false
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}

onMounted(loadOverview)
</script>
