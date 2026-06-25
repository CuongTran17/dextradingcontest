<template>
  <div class="flex items-center gap-2">
    <div
      :class="[
        'w-2 h-2 rounded-full',
        indicatorClass,
      ]"
    ></div>
    <span class="text-xs text-gray-500 dark:text-gray-400">
      {{ statusLabel }}
    </span>
    <span v-if="lastUpdate" class="text-xs text-gray-400 dark:text-gray-500">
      {{ formatTime(lastUpdate) }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps<{
  connected: boolean
  backendAvailable?: boolean
  lastUpdate?: Date
}>()

const now = ref(Date.now())
let staleTimer: number | null = null

const isStale = computed(() => {
  if (!props.lastUpdate) return false
  return now.value - props.lastUpdate.getTime() > 120000
})

const statusLabel = computed(() => {
  if (isStale.value) return 'Dữ liệu cũ'
  if (props.connected) return 'Trực tiếp'
  if (props.backendAvailable) return 'Polling'
  return 'Ngoại tuyến'
})

const indicatorClass = computed(() => {
  if (isStale.value) return 'bg-warning-500'
  if (props.connected) return 'bg-success-500 animate-pulse'
  if (props.backendAvailable) return 'bg-brand-500'
  return 'bg-gray-400'
})

function formatTime(date: Date): string {
  return date.toLocaleTimeString('vi-VN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}

onMounted(() => {
  staleTimer = window.setInterval(() => {
    now.value = Date.now()
  }, 30000)
})

onUnmounted(() => {
  if (staleTimer) {
    window.clearInterval(staleTimer)
  }
})
</script>
