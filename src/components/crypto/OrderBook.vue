<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="mb-4 flex items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Order Book</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ symbol }} · {{ book.source === 'binance' ? 'Live Binance Spot' : 'Mock fallback' }}
        </p>
      </div>
      <div class="text-right text-xs text-gray-500 dark:text-gray-400">
        <p>Spread {{ formatPrice(book.spread) }}</p>
        <p>Mid {{ formatPrice(book.mid_price) }}</p>
      </div>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div>
        <div class="mb-2 grid grid-cols-3 text-xs font-medium uppercase text-gray-400">
          <span>Bid</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div class="space-y-1">
          <div
            v-for="level in visibleBids"
            :key="`bid-${level.price}`"
            class="grid grid-cols-3 rounded bg-emerald-50 px-2 py-1 text-xs dark:bg-emerald-500/10"
          >
            <span class="font-medium text-emerald-700 dark:text-emerald-300">{{ formatPrice(level.price) }}</span>
            <span class="text-right text-gray-700 dark:text-gray-300">{{ formatQuantity(level.quantity) }}</span>
            <span class="text-right text-gray-500 dark:text-gray-400">{{ formatCompact(level.total) }}</span>
          </div>
        </div>
      </div>

      <div>
        <div class="mb-2 grid grid-cols-3 text-xs font-medium uppercase text-gray-400">
          <span>Ask</span>
          <span class="text-right">Qty</span>
          <span class="text-right">Total</span>
        </div>
        <div class="space-y-1">
          <div
            v-for="level in visibleAsks"
            :key="`ask-${level.price}`"
            class="grid grid-cols-3 rounded bg-rose-50 px-2 py-1 text-xs dark:bg-rose-500/10"
          >
            <span class="font-medium text-rose-700 dark:text-rose-300">{{ formatPrice(level.price) }}</span>
            <span class="text-right text-gray-700 dark:text-gray-300">{{ formatQuantity(level.quantity) }}</span>
            <span class="text-right text-gray-500 dark:text-gray-400">{{ formatCompact(level.total) }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchCryptoOrderBook, getMockOrderBook } from '@/services/cryptoMarketData'
import type { CryptoOrderBook, CryptoSymbol } from '@/types/crypto'

const props = withDefaults(
  defineProps<{
    symbol: CryptoSymbol
    limit?: number
  }>(),
  { limit: 100 },
)

const book = ref<CryptoOrderBook>(getMockOrderBook(props.symbol, props.limit))
const visibleBids = computed(() => book.value.bids.slice(0, 12))
const visibleAsks = computed(() => book.value.asks.slice(0, 12))
let refreshTimer: number | undefined

async function refreshOrderBook() {
  book.value = await fetchCryptoOrderBook(props.symbol, props.limit)
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value)
}

function formatQuantity(value: number): string {
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 6 }).format(value)
}

function formatCompact(value: number): string {
  return new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 2 }).format(value)
}

onMounted(() => {
  void refreshOrderBook()
  refreshTimer = window.setInterval(() => void refreshOrderBook(), 3000)
})

watch(
  () => props.symbol,
  () => {
    book.value = getMockOrderBook(props.symbol, props.limit)
    void refreshOrderBook()
  },
)

onBeforeUnmount(() => {
  if (refreshTimer) window.clearInterval(refreshTimer)
})
</script>
