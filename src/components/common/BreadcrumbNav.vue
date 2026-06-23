<template>
  <div class="flex items-center gap-2 px-4 py-2 text-sm text-gray-600 dark:text-gray-400">
    <!-- Back Button -->
    <button
      v-if="showBackButton"
      @click="goBack"
      class="flex items-center gap-1 px-2 py-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
      title="Quay lại trang trước"
    >
      <svg
        class="w-4 h-4"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="2"
          d="M15 19l-7-7 7-7"
        />
      </svg>
      <span class="text-xs">Quay lại</span>
    </button>

    <!-- Breadcrumb Trail -->
    <div class="flex items-center gap-2">
      <router-link
        to="/"
        class="hover:text-gray-900 dark:hover:text-white transition-colors"
      >
        <svg
          class="w-4 h-4"
          fill="currentColor"
          viewBox="0 0 20 20"
        >
          <path
            d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.707.707a1 1 0 001.414-1.414l-7-7z"
          />
        </svg>
      </router-link>

      <span class="text-gray-400">/</span>

      <!-- Current Page Title -->
      <span class="text-gray-900 dark:text-gray-200 font-medium">
        {{ currentPageTitle }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()
const canGoBack = ref(false)

const currentPageTitle = computed(() => {
  return route.meta.title as string || 'Trang không xác định'
})

const showBackButton = computed(() => {
  // Show back button on specific routes, not on home page
  const hideBackOn = ['/', '/welcome', '/signin', '/signup']
  return !hideBackOn.includes(route.path) && canGoBack.value
})

const goBack = () => {
  if (window.history.length > 1) {
    router.back()
  } else {
    // Fallback to home if no history
    router.push('/')
  }
}

onMounted(() => {
  // Check if there's browser history to go back to
  canGoBack.value = window.history.length > 1
})
</script>

<style scoped>
svg {
  display: inline;
}
</style>
