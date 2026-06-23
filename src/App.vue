<template>
  <ThemeProvider>
    <SidebarProvider>
      <RouterView />
    </SidebarProvider>
  </ThemeProvider>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import ThemeProvider from './components/layout/ThemeProvider.vue'
import SidebarProvider from './components/layout/SidebarProvider.vue'
import { realtimeManager } from '@/realtime/realtimeManager'

onMounted(() => {
  void realtimeManager.start()
})

onUnmounted(() => {
  realtimeManager.stop()
})
</script>
