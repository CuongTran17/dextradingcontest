<template>
  <main class="space-y-6">
    <div>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Leaderboard</h1>
      <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ contestId }}</p>
    </div>
    <p v-if="loading" class="text-sm text-gray-500 dark:text-gray-400">Loading leaderboard...</p>
    <p v-else-if="loadError" class="text-sm text-rose-600">{{ loadError }}</p>
    <LeaderboardTable v-else :rows="rows" />
  </main>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import LeaderboardTable from '@/components/crypto/LeaderboardTable.vue'
import { fetchContestLeaderboard } from '@/services/cryptoContestApi'
import type { LeaderboardRow } from '@/types/crypto'

const route = useRoute()
const contestId = computed(() => String(route.params.contestId || 'practice-arena'))
const rows = ref<LeaderboardRow[]>([])
const loading = ref(true)
const loadError = ref('')

onMounted(async () => {
  try {
    rows.value = await fetchContestLeaderboard(contestId.value)
  } catch (error) {
    loadError.value = error instanceof Error ? error.message : 'Unable to load leaderboard'
  } finally {
    loading.value = false
  }
})
</script>
