<template>
  <div
    class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
  >
    <h3 class="mb-5 text-lg font-semibold text-gray-800 dark:text-white/90">
      Tổng quan thị trường
    </h3>

    <div class="overflow-x-auto custom-scrollbar">
      <table class="w-full text-sm">
        <thead>
          <tr class="border-b border-gray-200 dark:border-gray-700">
            <th
              class="cursor-pointer select-none py-3 text-left font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('symbol')"
            >
              Mã CK
              <span v-if="sortKey === 'symbol'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('price')"
            >
              Giá
              <span v-if="sortKey === 'price'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('change')"
            >
              Thay đổi
              <span v-if="sortKey === 'change'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('changePercent')"
            >
              %
              <span v-if="sortKey === 'changePercent'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('volume')"
            >
              KL
              <span v-if="sortKey === 'volume'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('high')"
            >
              Cao
              <span v-if="sortKey === 'high'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
            <th
              class="cursor-pointer select-none py-3 text-right font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
              @click="toggleSort('low')"
            >
              Thấp
              <span v-if="sortKey === 'low'" class="inline-block ml-0.5 text-[10px]">
                {{ sortOrder === 'asc' ? '▲' : '▼' }}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="stock in sortedStocks"
            :key="stock.symbol"
            class="cursor-pointer border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/5"
            @click="$emit('select', stock.symbol)"
          >
            <td class="py-3">
              <div class="flex items-center gap-2">
                <div
                  class="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
                  :style="{ backgroundColor: stock.logoColor || '#465FFF' }"
                >
                  {{ stock.symbol.substring(0, 2) }}
                </div>
                <div>
                  <p class="font-semibold text-gray-800 dark:text-white/90">{{ stock.symbol }}</p>
                  <p class="max-w-[80px] truncate text-xs text-gray-400">{{ stock.companyName }}</p>
                </div>
              </div>
            </td>
            <td class="py-3 text-right font-medium text-gray-800 dark:text-white/90">
              {{ formatStockPrice(stock) }}
            </td>
            <td
              class="py-3 text-right font-medium"
              :class="stock.change >= 0 ? 'text-success-600' : 'text-error-600'"
            >
              {{ stock.change >= 0 ? '+' : '' }}{{ formatPrice(stock.change) }}
            </td>
            <td class="py-3 text-right">
              <span
                :class="[
                  'inline-flex items-center gap-0.5 rounded-full px-2 py-0.5 text-xs font-medium',
                  stock.changePercent >= 0
                    ? 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500'
                    : 'bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500',
                ]"
              >
                {{ stock.changePercent >= 0 ? '↑' : '↓' }}
                {{ Math.abs(stock.changePercent).toFixed(2) }}%
              </span>
            </td>
            <td class="py-3 text-right text-gray-600 dark:text-gray-300">
              {{ formatVolume(stock.volume) }}
            </td>
            <td class="py-3 text-right text-gray-600 dark:text-gray-300">
              {{ formatPrice(stock.high) }}
            </td>
            <td class="py-3 text-right text-gray-600 dark:text-gray-300">
              {{ formatPrice(stock.low) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { StockState } from '@/composables/useStockData'

const props = defineProps<{
  stocks: StockState[]
}>()

defineEmits<{
  (e: 'select', symbol: string): void
}>()

const sortKey = ref<string>('symbol')
const sortOrder = ref<'asc' | 'desc'>('asc')

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    sortOrder.value = 'asc'
  }
}

const sortedStocks = computed(() => {
  const result = [...props.stocks]
  if (!sortKey.value) return result

  return result.sort((a, b) => {
    let valA: any = a[sortKey.value as keyof StockState]
    let valB: any = b[sortKey.value as keyof StockState]

    // Handle string (like symbol) case-insensitive
    if (typeof valA === 'string' && typeof valB === 'string') {
      const cmp = valA.localeCompare(valB)
      return sortOrder.value === 'asc' ? cmp : -cmp
    }

    // Handle numbers
    const numA = Number(valA) || 0
    const numB = Number(valB) || 0

    if (numA < numB) return sortOrder.value === 'asc' ? -1 : 1
    if (numA > numB) return sortOrder.value === 'asc' ? 1 : -1
    return 0
  })
})

function formatPrice(price: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)
}

function hasUsableSnapshotPrice(stock: StockState): boolean {
  return stock.price > 0 && stock.dataStatus !== 'NO_DATA_IN_SNAPSHOT'
}

function formatStockPrice(stock: StockState): string {
  return hasUsableSnapshotPrice(stock) ? formatPrice(stock.price) : '--'
}

function formatVolume(volume: number): string {
  if (volume >= 1_000_000) {
    return (volume / 1_000_000).toFixed(1) + 'M'
  }
  if (volume >= 1_000) {
    return (volume / 1_000).toFixed(0) + 'K'
  }
  return volume.toString()
}
</script>
