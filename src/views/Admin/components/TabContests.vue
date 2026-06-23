<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Contest Management</h2>
    <div class="mt-4 overflow-x-auto">
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
          <tr v-for="contest in CRYPTO_CONTESTS" :key="contest.id">
            <td class="px-3 py-3 font-medium text-gray-900 dark:text-white">{{ contest.title }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.status }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ formatCurrency(contest.initialCapital) }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.symbols.join(', ') }}</td>
            <td class="px-3 py-3 text-gray-500 dark:text-gray-400">{{ contest.startsAt }} / {{ contest.endsAt }}</td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">{{ contest.participantCount }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup lang="ts">
import { CRYPTO_CONTESTS } from '@/constants/cryptoContests'

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(value)
}
</script>
