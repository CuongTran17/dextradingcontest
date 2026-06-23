<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Contest Results</h2>
    <div class="mt-4 space-y-3">
      <div
        v-for="result in results"
        :key="result.rank"
        class="grid gap-2 rounded-lg border border-gray-100 p-4 text-sm dark:border-gray-800 md:grid-cols-5"
      >
        <span class="font-semibold text-gray-900 dark:text-white">#{{ result.rank }}</span>
        <span class="text-gray-700 dark:text-gray-300">{{ result.wallet }}</span>
        <span class="text-emerald-600">{{ result.roi }}% ROI</span>
        <span class="text-gray-500 dark:text-gray-400">Certificate: {{ result.certificate }}</span>
        <span class="text-gray-500 dark:text-gray-400">NFT: Phase B, not minted</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
const results = [
  { rank: 1, wallet: '0x7A...91F2', roi: 12.4, certificate: 'Ready' },
  { rank: 2, wallet: '0xF1...0C29', roi: 4.1, certificate: 'Ready' },
  { rank: 3, wallet: '0x2C...8AA0', roi: -1.9, certificate: 'Pending review' },
]
</script>
