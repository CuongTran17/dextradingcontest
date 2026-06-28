<template>
  <section class="space-y-5">
    <div class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Accounts & Balances</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Read-only virtual account monitoring.</p>
        </div>
        <div class="grid gap-2 sm:grid-cols-5">
          <select
            v-model="contestId"
            class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="">All contests</option>
            <option v-for="contest in contests" :key="contest.id" :value="contest.id">
              {{ contest.title }}
            </option>
          </select>
          <input
            v-model="search"
            class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
            placeholder="Search user"
            @keyup.enter="loadAccounts"
          >
          <select
            v-model="status"
            class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          >
            <option value="">All accounts</option>
            <option value="active">active</option>
            <option value="frozen">frozen</option>
            <option value="closed">closed</option>
          </select>
          <button
            class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
            :disabled="loading"
            @click="loadAccounts"
          >
            Search
          </button>
          <button
            class="rounded-lg border border-gray-300 px-3 py-2 text-sm font-semibold text-gray-700 dark:border-gray-700 dark:text-gray-200"
            @click="refreshAll"
          >
            Refresh
          </button>
        </div>
      </div>

      <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
      <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading accounts...</p>

      <div v-else class="mt-4 overflow-x-auto">
        <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
          <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
            <tr>
              <th class="px-3 py-2">User</th>
              <th class="px-3 py-2">Contest</th>
              <th class="px-3 py-2">Status</th>
              <th class="px-3 py-2">Cash</th>
              <th class="px-3 py-2">Equity</th>
              <th class="px-3 py-2">ROI</th>
              <th class="px-3 py-2">Activity</th>
              <th class="px-3 py-2">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
            <tr v-for="account in accounts" :key="account.accountId">
              <td class="px-3 py-3">
                <p class="font-medium text-gray-900 dark:text-white">{{ account.user.fullname }}</p>
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ account.user.email }}</p>
              </td>
              <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ account.contest.title }}</td>
              <td class="px-3 py-3 text-gray-700 dark:text-gray-300">
                {{ account.participantStatus }} / {{ account.status }}
              </td>
              <td class="px-3 py-3 text-gray-700 dark:text-gray-300">
                {{ formatCurrency(account.cash) }}
                <span v-if="account.lockedCash" class="block text-xs text-amber-600">
                  locked {{ formatCurrency(account.lockedCash) }}
                </span>
              </td>
              <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(account.equity) }}</td>
              <td
                class="px-3 py-3 font-medium"
                :class="account.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'"
              >
                {{ account.roi.toFixed(2) }}%
              </td>
              <td class="px-3 py-3 text-gray-500 dark:text-gray-400">
                {{ account.positionCount }} positions / {{ account.orderCount }} orders
              </td>
              <td class="px-3 py-3">
                <button
                  class="rounded border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 dark:border-gray-700 dark:text-gray-200"
                  @click="selectAccount(account.accountId)"
                >
                  View
                </button>
              </td>
            </tr>
          </tbody>
        </table>
        <p v-if="accounts.length === 0" class="py-6 text-center text-sm text-gray-500">No accounts found.</p>
      </div>
    </div>

    <div
      v-if="selectedDetail"
      class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
    >
      <div class="flex items-start justify-between gap-3">
        <div>
          <h3 class="text-base font-semibold text-gray-900 dark:text-white">
            {{ selectedDetail.user.fullname }} account detail
          </h3>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            {{ selectedDetail.contest.title }} / {{ selectedDetail.status }}
          </p>
        </div>
        <button class="text-sm font-medium text-gray-500 hover:text-gray-700" @click="selectedDetail = null">
          Close
        </button>
      </div>

      <div class="mt-4 grid gap-4 lg:grid-cols-3">
        <div class="rounded-lg border border-gray-100 p-4 dark:border-gray-800">
          <p class="text-sm font-semibold text-gray-900 dark:text-white">Balances</p>
          <div class="mt-3 space-y-2 text-sm">
            <p v-for="balance in selectedDetail.balances" :key="balance.asset" class="flex justify-between gap-3">
              <span class="text-gray-500">{{ balance.asset }}</span>
              <span class="text-gray-800 dark:text-gray-200">
                {{ formatCurrency(balance.available) }} / {{ formatCurrency(balance.locked) }} locked
              </span>
            </p>
          </div>
        </div>

        <div class="rounded-lg border border-gray-100 p-4 dark:border-gray-800 lg:col-span-2">
          <p class="text-sm font-semibold text-gray-900 dark:text-white">Positions</p>
          <div class="mt-3 overflow-x-auto">
            <table class="min-w-full text-sm">
              <tbody>
                <tr v-for="position in selectedDetail.positions" :key="position.symbol">
                  <td class="py-2 font-medium text-gray-900 dark:text-white">{{ position.symbol }}</td>
                  <td class="py-2 text-gray-600 dark:text-gray-300">{{ position.quantity }}</td>
                  <td class="py-2 text-gray-600 dark:text-gray-300">{{ formatCurrency(position.averageEntryPrice) }}</td>
                  <td class="py-2 text-gray-600 dark:text-gray-300">{{ formatCurrency(position.costBasis) }}</td>
                </tr>
              </tbody>
            </table>
            <p v-if="selectedDetail.positions.length === 0" class="text-sm text-gray-500">No open positions.</p>
          </div>
        </div>
      </div>

      <div class="mt-4 rounded-lg border border-gray-100 p-4 dark:border-gray-800">
        <p class="text-sm font-semibold text-gray-900 dark:text-white">Recent Orders</p>
        <div class="mt-3 overflow-x-auto">
          <table class="min-w-full divide-y divide-gray-100 text-sm dark:divide-gray-800">
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-for="order in selectedDetail.orders" :key="order.orderId">
                <td class="py-2 font-medium text-gray-900 dark:text-white">{{ order.symbol }}</td>
                <td class="py-2 text-gray-600 dark:text-gray-300">{{ order.side }} / {{ order.status }}</td>
                <td class="py-2 text-gray-600 dark:text-gray-300">{{ order.filledQuantity }}</td>
                <td class="py-2 text-gray-600 dark:text-gray-300">{{ formatCurrency(order.executedNotional) }}</td>
                <td class="py-2 text-gray-500">{{ formatDate(order.submittedAt) }}</td>
              </tr>
            </tbody>
          </table>
          <p v-if="selectedDetail.orders.length === 0" class="text-sm text-gray-500">No orders yet.</p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  fetchAdminAccountDetail,
  fetchAdminAccounts,
} from '@/services/adminDashboardApi'
import { fetchAdminCryptoContests } from '@/services/cryptoContestApi'
import type { AdminAccountDetail, AdminAccountSummary, Contest, TradingAccountStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const accounts = ref<AdminAccountSummary[]>([])
const selectedDetail = ref<AdminAccountDetail | null>(null)
const contestId = ref('')
const search = ref('')
const status = ref<TradingAccountStatus | ''>('')
const loading = ref(false)
const error = ref('')

async function refreshAll() {
  await Promise.all([loadContests(), loadAccounts()])
}

async function loadContests() {
  try {
    contests.value = await fetchAdminCryptoContests()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load contests'
  }
}

async function loadAccounts() {
  loading.value = true
  error.value = ''
  try {
    const result = await fetchAdminAccounts({
      contestId: contestId.value || undefined,
      q: search.value || undefined,
      status: status.value,
      page: 1,
      perPage: 50,
    })
    accounts.value = result.accounts
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load accounts'
  } finally {
    loading.value = false
  }
}

async function selectAccount(accountId: number) {
  error.value = ''
  try {
    selectedDetail.value = await fetchAdminAccountDetail(accountId)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load account detail'
  }
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  }).format(value)
}

function formatDate(value: string | null): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

onMounted(refreshAll)
</script>
