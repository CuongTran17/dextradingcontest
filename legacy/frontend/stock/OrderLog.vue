<template>
  <div class="flex h-full flex-col">
    <div class="mb-3 flex items-center justify-between">
      <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Sổ lệnh</h2>
      <div class="flex items-center gap-2">
        <span
          v-if="isInSession"
          class="inline-flex items-center gap-1 rounded-full bg-success-100 px-2 py-0.5 text-xs font-medium text-success-700 dark:bg-success-500/15 dark:text-success-300"
        >
          <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-success-500"></span>
          Đang giao dịch
        </span>
        <span
          v-else
          class="inline-flex items-center rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-500 dark:bg-gray-800 dark:text-gray-400"
        >
          Ngoài giờ
        </span>
        <button
          class="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 disabled:opacity-50 dark:hover:bg-gray-800 dark:hover:text-gray-300"
          :disabled="loading"
          :title="'Tải lại sổ lệnh'"
          @click="$emit('refresh')"
        >
          <svg
            class="h-4 w-4"
            :class="{ 'animate-spin': loading }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>

    <!-- Loading skeleton -->
    <div v-if="loading && ticks.length === 0" class="space-y-2">
      <div
        v-for="i in 8"
        :key="i"
        class="h-8 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800"
      ></div>
    </div>

    <!-- Empty state -->
    <div
      v-else-if="!loading && ticks.length === 0"
      class="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-gray-200 py-8 text-center dark:border-gray-700"
    >
      <svg class="mb-2 h-8 w-8 text-gray-300 dark:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
        <path stroke-linecap="round" stroke-linejoin="round" d="M3 7.5L7.5 3m0 0L12 7.5M7.5 3v13.5m13.5 0L16.5 21m0 0L12 16.5m4.5 4.5V7.5" />
      </svg>
      <p class="text-sm text-gray-400 dark:text-gray-500">Chưa có dữ liệu lệnh khớp</p>
      <p class="mt-1 text-xs text-gray-400 dark:text-gray-500">Dữ liệu chỉ có trong giờ giao dịch</p>
    </div>

    <!-- Order log table -->
    <div v-else class="min-h-0 flex-1 overflow-auto">
      <table class="w-full text-xs">
        <thead class="sticky top-0 z-10 bg-white dark:bg-gray-900">
          <tr class="border-b border-gray-100 dark:border-gray-800">
            <th class="pb-2 text-left font-medium text-gray-500 dark:text-gray-400">Giờ</th>
            <th class="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">Giá</th>
            <th class="pb-2 text-right font-medium text-gray-500 dark:text-gray-400">KL</th>
            <th class="pb-2 text-center font-medium text-gray-500 dark:text-gray-400">Loại</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-50 dark:divide-gray-800/60">
          <tr
            v-for="tick in ticks"
            :key="tick.id"
            class="transition-colors hover:bg-gray-50 dark:hover:bg-white/[0.03]"
          >
            <td class="py-1.5 pr-2 font-mono text-gray-500 dark:text-gray-400">
              {{ formatTime(tick.time) }}
            </td>
            <td
              class="py-1.5 pr-2 text-right font-semibold tabular-nums"
              :class="priceClass(tick.match_type)"
            >
              {{ formatPrice(tick.price) }}
            </td>
            <td class="py-1.5 pr-2 text-right tabular-nums text-gray-600 dark:text-gray-400">
              {{ formatVolume(tick.volume) }}
            </td>
            <td class="py-1.5 text-center">
              <span
                class="inline-block min-w-[42px] rounded-full px-2 py-0.5 text-[10px] font-semibold"
                :class="badgeClass(tick)"
                :title="sideTitle(tick)"
              >
                {{ sideLabel(tick.match_type) }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>

      <p
        v-if="totalCount > ticks.length"
        class="mt-2 text-center text-[10px] text-gray-400 dark:text-gray-600"
      >
        Hiển thị {{ ticks.length }} / {{ totalCount }} lệnh gần nhất
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
export interface OrderTick {
  id: string
  symbol: string
  time: string
  price: number
  volume: number
  match_type: string
  side_source?: string
  side_confidence?: string
}

const props = defineProps<{
  ticks: OrderTick[]
  totalCount?: number
  isInSession?: boolean
  loading?: boolean
}>()

defineEmits<{ (e: 'refresh'): void }>()

const totalCount = computed(() => props.totalCount ?? props.ticks.length)

function formatTime(isoStr: string): string {
  try {
    const d = new Date(isoStr)
    return d.toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
  } catch {
    return isoStr
  }
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)
}

function formatVolume(value: number): string {
  if (value >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (value >= 1_000) return `${(value / 1_000).toFixed(1)}K`
  return String(value)
}

function sideLabel(matchType: string): string {
  const mt = matchType.trim().toLowerCase()
  if (mt === 'buy') return 'Mua'
  if (mt === 'sell') return 'Bán'
  if (mt === 'atc') return 'ATC'
  if (mt === 'ato') return 'ATO'
  if (mt === 'lo') return 'LO'
  if (mt === 'unknown' || mt === 'manual') return '?'
  return matchType || '?'
}

function isBuy(matchType: string): boolean {
  const mt = matchType.trim().toLowerCase()
  return mt === 'buy' || mt === 'ato'
}

function isSell(matchType: string): boolean {
  const mt = matchType.trim().toLowerCase()
  return mt === 'sell'
}

function priceClass(matchType: string): string {
  if (isBuy(matchType)) return 'text-success-600 dark:text-success-400'
  if (isSell(matchType)) return 'text-error-600 dark:text-error-400'
  return 'text-gray-800 dark:text-white/80'
}

function sideTitle(tick: OrderTick): string {
  if (tick.side_confidence === 'source') return 'Phân loại từ DNSE'
  if (tick.side_confidence === 'inferred') return 'Suy luận theo biến động giá tick trước'
  return 'Nguồn không cung cấp chiều mua/bán'
}

function badgeClass(tick: OrderTick): string {
  const matchType = tick.match_type
  const confidence = tick.side_confidence || 'unknown'
  if (isBuy(matchType) && confidence === 'inferred') return 'bg-success-50 text-success-700 dark:bg-success-500/10 dark:text-success-300'
  if (isBuy(matchType)) return 'bg-success-100 text-success-700 dark:bg-success-500/20 dark:text-success-300'
  if (isSell(matchType) && confidence === 'inferred') return 'bg-error-50 text-error-700 dark:bg-error-500/10 dark:text-error-300'
  if (isSell(matchType)) return 'bg-error-100 text-error-700 dark:bg-error-500/20 dark:text-error-300'
  return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
}

import { computed } from 'vue'
</script>
