<template>
  <ThemeProvider>
    <SidebarProvider>
      <RouterView v-if="isFullscreenLayout" />
      <AdminLayout v-else>
        <RouterView />
      </AdminLayout>
    </SidebarProvider>
  </ThemeProvider>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'

import ThemeProvider from './components/layout/ThemeProvider.vue'
import SidebarProvider from './components/layout/SidebarProvider.vue'
import AdminLayout from './components/layout/AdminLayout.vue'

const route = useRoute()
const isFullscreenLayout = computed(() => route.meta.layout === 'fullscreen')
</script>
