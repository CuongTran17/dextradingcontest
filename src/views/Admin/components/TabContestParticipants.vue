<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Participants</h2>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Lock, disqualify, or restore contest accounts.</p>
      </div>
      <select
        v-model="selectedContestId"
        class="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
        @change="loadParticipants"
      >
        <option v-for="contest in contests" :key="contest.id" :value="contest.id">
          {{ contest.title }}
        </option>
      </select>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading participants...</p>
    <p v-else-if="!selectedContestId" class="mt-4 text-sm text-gray-500 dark:text-gray-400">No contests available.</p>
    <div v-else class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
        <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th class="px-3 py-2">User</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Equity</th>
            <th class="px-3 py-2">ROI</th>
            <th class="px-3 py-2">Volume</th>
            <th class="px-3 py-2">Trades</th>
            <th class="px-3 py-2">Last Trade</th>
            <th class="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <tr v-for="participant in participants" :key="participant.userId">
            <td class="px-3 py-3 font-medium text-gray-900 dark:text-white">{{ participant.user }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">
              {{ participant.status }} / {{ participant.accountStatus }}
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(participant.equity) }}</td>
            <td
              class="px-3 py-3 font-medium"
              :class="participant.roi >= 0 ? 'text-emerald-600' : 'text-rose-600'"
            >
              {{ participant.roi.toFixed(2) }}%
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(participant.volume) }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ participant.tradeCount }}</td>
            <td class="px-3 py-3 text-gray-500 dark:text-gray-400">{{ participant.lastTrade ?? '-' }}</td>
            <td class="px-3 py-3">
              <div class="flex flex-wrap gap-2">
                <button
                  class="rounded border border-gray-300 px-2 py-1 text-xs font-medium text-gray-700 disabled:opacity-50 dark:border-gray-700 dark:text-gray-200"
                  :disabled="participant.status === 'active'"
                  @click="changeStatus(participant, 'active')"
                >
                  Restore
                </button>
                <button
                  class="rounded border border-amber-300 px-2 py-1 text-xs font-medium text-amber-700 disabled:opacity-50 dark:border-amber-700 dark:text-amber-300"
                  :disabled="participant.status === 'locked'"
                  @click="changeStatus(participant, 'locked')"
                >
                  Lock
                </button>
                <button
                  class="rounded border border-rose-300 px-2 py-1 text-xs font-medium text-rose-700 disabled:opacity-50 dark:border-rose-700 dark:text-rose-300"
                  :disabled="participant.status === 'disqualified'"
                  @click="changeStatus(participant, 'disqualified')"
                >
                  Disqualify
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import {
  fetchAdminContestParticipants,
  fetchAdminCryptoContests,
  setAdminContestParticipantStatus,
} from '@/services/cryptoContestApi'
import type { AdminContestParticipant, Contest, ParticipantStatus } from '@/types/crypto'

const contests = ref<Contest[]>([])
const participants = ref<AdminContestParticipant[]>([])
const selectedContestId = ref('')
const loading = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    contests.value = await fetchAdminCryptoContests()
    selectedContestId.value = contests.value[0]?.id ?? ''
    if (selectedContestId.value) {
      participants.value = await fetchAdminContestParticipants(selectedContestId.value)
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load participants'
  } finally {
    loading.value = false
  }
})

async function loadParticipants() {
  if (!selectedContestId.value) return
  loading.value = true
  error.value = ''
  try {
    participants.value = await fetchAdminContestParticipants(selectedContestId.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load participants'
  } finally {
    loading.value = false
  }
}

async function changeStatus(
  participant: AdminContestParticipant,
  status: ParticipantStatus,
) {
  if (!selectedContestId.value) return
  error.value = ''
  try {
    const updated = await setAdminContestParticipantStatus(
      selectedContestId.value,
      participant.userId,
      status,
    )
    participants.value = participants.value.map((item) =>
      item.userId === updated.userId ? updated : item,
    )
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to update participant'
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
