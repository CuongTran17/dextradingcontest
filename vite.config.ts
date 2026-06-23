import { fileURLToPath, URL } from 'node:url'
/// <reference types="vitest/config" />

import vue from '@vitejs/plugin-vue'
import vueJsx from '@vitejs/plugin-vue-jsx'
import { defineConfig } from 'vitest/config'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  base: process.env.NODE_ENV === 'production' ? '/tailadmin-vuejs/' : '/',
  plugins: [vue(), vueJsx(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      // Proxy backend API calls to avoid CORS in dev.
      '/api': {
        target: process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000',
        changeOrigin: true,
        secure: false,
      },
      // Proxy DNSE REST API calls through Vite to avoid browser CORS in dev.
      '/dnse-proxy': {
        target: 'https://services.entrade.com.vn',
        changeOrigin: true,
        secure: true,
        rewrite: (path) => path.replace(/^\/dnse-proxy/, ''),
      },
    },
  },
  build: {
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router'],
          apexcharts: ['apexcharts', 'vue3-apexcharts'],
          lightweightCharts: ['lightweight-charts'],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    clearMocks: true,
    restoreMocks: true,
  },
})
