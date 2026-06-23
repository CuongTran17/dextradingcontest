<template>
  <div class="sticky top-0 z-50 flex items-center justify-between gap-4 px-6 py-4 bg-white border-b border-gray-200 dark:border-gray-800 dark:bg-gray-900">
    <!-- Logo & Back -->
    <div class="flex items-center gap-4">
      <router-link
        to="/"
        class="flex items-center justify-center w-10 h-10 text-gray-500 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
        title="Về trang chủ"
      >
        <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
          <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.707.707a1 1 0 001.414-1.414l-7-7z" />
        </svg>
      </router-link>
      <h1 class="text-lg font-semibold text-gray-900 dark:text-white">{{ title }}</h1>
    </div>

    <!-- Actions Slot -->
    <div class="flex items-center gap-2">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps({
  title: {
    type: String,
    required: true,
  },
})
</script>

<style scoped>
svg {
  display: inline;
}
</style>
