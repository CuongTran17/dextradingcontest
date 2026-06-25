<template>
  <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4 md:gap-6">
    <div
      v-for="stock in stocks"
      :key="stock.symbol"
      class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6 transition-all hover:shadow-lg cursor-pointer"
      @click="$emit('select', stock.symbol)"
    >
      <!-- Logo + Info -->
      <div class="flex items-center gap-3">
        <div
          class="flex items-center justify-center w-12 h-12 rounded-xl text-white font-bold text-lg"
          :style="{ backgroundColor: stock.logoColor || '#465FFF' }"
        >
          {{ stock.symbol.charAt(0) }}
        </div>
        <div>
          <h4 class="font-semibold text-gray-800 dark:text-white/90">
            {{ stock.symbol }}
          </h4>
          <p class="text-xs text-gray-500 dark:text-gray-400 truncate max-w-[120px]">
            {{ stock.companyName }}
          </p>
        </div>
      </div>

      <!-- Price + Change -->
      <div class="flex items-end justify-between mt-5">
        <div>
          <h4 class="font-bold text-gray-800 text-title-sm dark:text-white/90">
            {{ formatStockPrice(stock) }}
          </h4>
        </div>

        <!-- Change badge -->
        <span
          :class="[
            'flex items-center gap-1 rounded-full py-0.5 pl-2 pr-2.5 text-sm font-medium',
            stock.changePercent >= 0
              ? 'bg-success-50 text-success-600 dark:bg-success-500/15 dark:text-success-500'
              : 'bg-error-50 text-error-600 dark:bg-error-500/15 dark:text-error-500',
          ]"
        >
          <!-- Arrow up -->
          <svg
            v-if="stock.changePercent >= 0"
            class="fill-current"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M5.56462 1.62393C5.70193 1.47072 5.90135 1.37432 6.12329 1.37432C6.31631 1.37415 6.50845 1.44731 6.65505 1.59381L9.65514 4.5918C9.94814 4.88459 9.94831 5.35947 9.65552 5.65246C9.36273 5.94546 8.88785 5.94562 8.59486 5.65283L6.87329 3.93247V10.125C6.87329 10.5392 6.53751 10.875 6.12329 10.875C5.70908 10.875 5.37329 10.5392 5.37329 10.125V3.93578L3.65516 5.65282C3.36218 5.94562 2.8873 5.94547 2.5945 5.65248C2.3017 5.35949 2.30185 4.88462 2.59484 4.59182L5.56462 1.62393Z"
              fill=""
            />
          </svg>
          <!-- Arrow down -->
          <svg
            v-else
            class="fill-current"
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
          >
            <path
              fill-rule="evenodd"
              clip-rule="evenodd"
              d="M5.31462 10.3761C5.45194 10.5293 5.65136 10.6257 5.87329 10.6257C6.0663 10.6259 6.25845 10.5527 6.40505 10.4062L9.40514 7.4082C9.69814 7.11541 9.69831 6.64054 9.40552 6.34754C9.11273 6.05454 8.63785 6.05438 8.34486 6.34717L6.62329 8.06753V1.875C6.62329 1.46079 6.28751 1.125 5.87329 1.125C5.45908 1.125 5.12329 1.46079 5.12329 1.875V8.06422L3.40516 6.34719C3.11218 6.05439 2.6373 6.05454 2.3445 6.34752C2.0517 6.64051 2.05185 7.11538 2.34484 7.40818L5.31462 10.3761Z"
              fill=""
            />
          </svg>

          {{ stock.changePercent >= 0 ? '↑' : '↓' }}
          {{ Math.abs(stock.changePercent).toFixed(2) }}%
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { StockState } from '@/composables/useStockData'

defineProps<{
  stocks: StockState[]
}>()

defineEmits<{
  (e: 'select', symbol: string): void
}>()

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
