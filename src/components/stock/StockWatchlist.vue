<template>
  <div
    class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
  >
    <div class="mb-5 flex items-center justify-between">
      <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">Danh mục theo dõi</h3>

      <div class="relative h-fit">
        <DropdownMenu :menu-items="menuItems">
          <template #icon>
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                fill-rule="evenodd"
                clip-rule="evenodd"
                d="M10.2441 6C10.2441 5.0335 11.0276 4.25 11.9941 4.25H12.0041C12.9706 4.25 13.7541 5.0335 13.7541 6C13.7541 6.9665 12.9706 7.75 12.0041 7.75H11.9941C11.0276 7.75 10.2441 6.9665 10.2441 6ZM10.2441 18C10.2441 17.0335 11.0276 16.25 11.9941 16.25H12.0041C12.9706 16.25 13.7541 17.0335 13.7541 18C13.7541 18.9665 12.9706 19.75 12.0041 19.75H11.9941C11.0276 19.75 10.2441 18.9665 10.2441 18ZM11.9941 10.25C11.0276 10.25 10.2441 11.0335 10.2441 12C10.2441 12.9665 11.0276 13.75 11.9941 13.75H12.0041C12.9706 13.75 13.7541 12.9665 13.7541 12C13.7541 11.0335 12.9706 10.25 12.0041 10.25H11.9941Z"
                fill="currentColor"
              />
            </svg>
          </template>
        </DropdownMenu>
      </div>
    </div>

    <div class="max-h-[400px] space-y-2 overflow-y-auto custom-scrollbar">
      <div
        v-for="stock in sortedStocks"
        :key="stock.symbol"
        class="group flex w-full items-center justify-between rounded-lg p-3 text-left transition-colors hover:bg-gray-50 dark:hover:bg-white/5"
        @click="$emit('select', stock.symbol)"
      >
        <div class="flex min-w-0 items-center gap-3">
          <div
            class="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg text-sm font-bold text-white"
            :style="{ backgroundColor: stock.logoColor || '#465FFF' }"
          >
            {{ stock.symbol.substring(0, 2) }}
          </div>

          <div class="min-w-0">
            <h4 class="text-sm font-semibold text-gray-800 dark:text-white/90">
              {{ stock.symbol }}
            </h4>
            <p class="max-w-[120px] truncate text-xs text-gray-500 dark:text-gray-400">
              {{ stock.companyName }}
            </p>
          </div>
        </div>

        <div class="ml-3 flex shrink-0 items-center gap-3">
          <div class="text-right">
            <p class="text-sm font-semibold text-gray-800 dark:text-white/90">
              {{ formatStockPrice(stock) }}
            </p>
            <span
              :class="[
                'text-xs font-medium',
                stock.changePercent >= 0
                  ? 'text-success-600 dark:text-success-500'
                  : 'text-error-600 dark:text-error-500',
              ]"
            >
              {{ stock.changePercent >= 0 ? '↑' : '↓' }}
              {{ Math.abs(stock.changePercent).toFixed(2) }}%
            </span>
          </div>
          <button
            class="rounded-md p-1 text-gray-400 opacity-0 transition hover:bg-gray-100 hover:text-error-600 group-hover:opacity-100 dark:hover:bg-white/10"
            type="button"
            aria-label="Xóa khỏi danh mục theo dõi"
            @click.stop="$emit('remove', stock.symbol)"
          >
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18 18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      <div
        v-if="!stocks || stocks.length === 0"
        class="rounded-lg border border-dashed border-gray-200 py-8 text-center text-gray-400 dark:border-gray-700 dark:text-gray-500"
      >
        <p class="text-sm">Chưa có mã nào trong danh mục theo dõi</p>
        <p class="mt-1 text-xs">Thêm mã cổ phiếu để theo dõi</p>
      </div>
    </div>

    <div class="mt-4 border-t border-gray-200 pt-4 dark:border-gray-700">
      <div class="flex gap-2">
        <input
          v-model="newSymbol"
          type="text"
          placeholder="Thêm mã CK (VD: FPT)"
          class="min-w-0 flex-1 rounded-lg border border-gray-300 bg-transparent px-3 py-2 text-sm text-gray-800 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none dark:border-gray-700 dark:text-white/90"
          maxlength="10"
          @keyup.enter="addSymbol"
        />
        <button
          class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-brand-600"
          @click="addSymbol"
        >
          Thêm
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import DropdownMenu from '@/components/common/DropdownMenu.vue'
import type { StockState } from '@/composables/useStockData'

const props = defineProps<{
  stocks: StockState[]
}>()

const emit = defineEmits<{
  (e: 'select', symbol: string): void
  (e: 'add', symbol: string): void
  (e: 'remove', symbol: string): void
  (e: 'clear'): void
}>()

const menuItems = [
  { label: 'Sắp xếp theo giá', onClick: () => { sortMode.value = 'price' } },
  { label: 'Sắp xếp theo % thay đổi', onClick: () => { sortMode.value = 'changePercent' } },
  { label: 'Xóa toàn bộ', onClick: () => { emit('clear') } },
]

const newSymbol = ref('')
const sortMode = ref<'default' | 'price' | 'changePercent'>('default')

const sortedStocks = computed(() => {
  const items = [...props.stocks]
  if (sortMode.value === 'price') {
    return items.sort((a, b) => b.price - a.price)
  }
  if (sortMode.value === 'changePercent') {
    return items.sort((a, b) => b.changePercent - a.changePercent)
  }
  return items
})

function addSymbol() {
  const symbol = newSymbol.value.trim().toUpperCase()
  if (symbol && symbol.length >= 2) {
    emit('add', symbol)
    newSymbol.value = ''
  }
}

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
</script>
