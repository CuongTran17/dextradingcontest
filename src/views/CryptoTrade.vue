<template>
  <main class="space-y-6">
    <SimulationDisclaimer />
    <section>
      <h1 class="text-2xl font-semibold text-gray-900 dark:text-white">Trade Simulator</h1>
      <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ symbol }}</p>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import SimulationDisclaimer from '@/components/crypto/SimulationDisclaimer.vue'
import { DEFAULT_CRYPTO_SYMBOL } from '@/constants/cryptoAssets'

const route = useRoute()
const symbol = computed(() =>
  typeof route.params.symbol === 'string' ? route.params.symbol : DEFAULT_CRYPTO_SYMBOL,
)
</script>
