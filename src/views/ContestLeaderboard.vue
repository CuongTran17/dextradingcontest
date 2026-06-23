<template>
  <main class="space-y-4">
    <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Leaderboard</h1>
    <p class="text-sm text-gray-500 dark:text-gray-400">{{ contestId }}</p>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const contestId = computed(() => route.params.contestId)
</script>
