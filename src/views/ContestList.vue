<template>
  <main class="space-y-4">
    <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Trading Contests</h1>
    <ul class="grid gap-4 md:grid-cols-2">
      <li
        v-for="contest in CRYPTO_CONTESTS"
        :key="contest.id"
        class="rounded-lg border border-gray-200 p-4 dark:border-gray-800"
      >
        <h2 class="font-semibold text-gray-900 dark:text-white">{{ contest.title }}</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">{{ contest.status }}</p>
      </li>
    </ul>
  </main>
</template>

<script setup lang="ts">
import { CRYPTO_CONTESTS } from '@/constants/cryptoContests'
</script>
