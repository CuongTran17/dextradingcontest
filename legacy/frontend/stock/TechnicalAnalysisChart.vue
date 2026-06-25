<template>
  <div
    class="rounded-2xl border border-gray-200 bg-white px-5 pb-5 pt-5 dark:border-gray-800 dark:bg-white/[0.03] sm:px-6 sm:pt-6"
  >
    <!-- Header -->
    <div class="flex flex-col gap-3 mb-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">
          Phân Tích Kỹ Thuật — {{ symbol }}
        </h3>
        <p v-if="signals" class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          RSI: {{ signals.rsi }} · MACD: {{ signals.macd }}
          · SMA200: {{ signals.price_vs_sma200 }}
          <span v-if="signals.golden_cross" class="text-amber-500 font-medium"> · Giao cắt vàng ✦</span>
        </p>
      </div>

      <div class="flex items-center gap-3">
        <!-- Signal badge -->
        <span
          v-if="signals"
          :class="signalBadgeClass"
          class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold uppercase"
        >
          {{ signalLabel }}
        </span>

        <!-- Period selector -->
        <div class="inline-flex items-center gap-0.5 rounded-lg bg-gray-100 p-0.5 dark:bg-gray-900">
          <button
            v-for="opt in periodOptions"
            :key="opt.value"
            @click="selectedPeriod = opt.value; loadData()"
            :class="[
              selectedPeriod === opt.value
                ? 'shadow-theme-xs text-gray-900 dark:text-white bg-white dark:bg-gray-800'
                : 'text-gray-500 dark:text-gray-400',
              'px-3 py-1.5 font-medium rounded-md text-theme-sm',
            ]"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="flex items-center justify-center py-20">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
      <span class="ml-3 text-gray-500">Đang tải dữ liệu...</span>
    </div>

    <!-- No backend -->
    <div
      v-else-if="!hasData"
      class="flex flex-col items-center justify-center py-16 text-gray-400"
    >
      <svg class="w-12 h-12 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5"
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <p class="text-sm">Khởi động Python backend để hiển thị phân tích kỹ thuật</p>
      <code class="mt-2 text-xs bg-gray-100 dark:bg-gray-800 px-3 py-1 rounded">
        cd backend_v2 && python -m uvicorn src.main:app --reload
      </code>
    </div>

    <!-- Charts -->
    <div v-else class="space-y-6">
      <!-- Main Price Chart with Bollinger Bands + SMA -->
      <div class="rounded-xl border border-gray-100 bg-gray-50/20 p-4 dark:border-gray-800/60 dark:bg-gray-900/10 max-w-full overflow-x-auto custom-scrollbar">
        <div class="mb-3 flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Biểu đồ giá & các đường trung bình (SMA / Bollinger Bands)
          </span>
        </div>
        <div class="min-w-[700px] xl:min-w-full pl-3 pr-2">
          <VueApexCharts
            type="line"
            height="320"
            :options="priceChartOptions"
            :series="priceChartSeries"
          />
        </div>
      </div>

      <!-- RSI Chart -->
      <div class="rounded-xl border border-gray-100 bg-gray-50/20 p-4 dark:border-gray-800/60 dark:bg-gray-900/10 max-w-full overflow-x-auto custom-scrollbar">
        <div class="mb-3 flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Chỉ báo sức mạnh tương đối (RSI 14)
          </span>
        </div>
        <div class="min-w-[700px] xl:min-w-full pl-3 pr-2">
          <VueApexCharts
            type="line"
            height="160"
            :options="rsiChartOptions"
            :series="rsiChartSeries"
          />
        </div>
      </div>

      <!-- MACD Chart -->
      <div class="rounded-xl border border-gray-100 bg-gray-50/20 p-4 dark:border-gray-800/60 dark:bg-gray-900/10 max-w-full overflow-x-auto custom-scrollbar">
        <div class="mb-3 flex items-center justify-between">
          <span class="text-[11px] font-bold uppercase tracking-wider text-gray-400 dark:text-gray-500">
            Chỉ báo xu hướng (MACD)
          </span>
        </div>
        <div class="min-w-[700px] xl:min-w-full pl-3 pr-2">
          <VueApexCharts
            type="line"
            height="180"
            :options="macdChartOptions"
            :series="macdChartSeries"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import VueApexCharts from 'vue3-apexcharts'
import type { TechnicalResponse } from '@/services/stockBackendApi'

const props = defineProps<{
  symbol: string
  fetchTechnical: (symbol: string, limit: number) => Promise<TechnicalResponse | null>
  refreshToken?: number
  valueUnit?: string
  yAxisTitle?: string
}>()

const periodOptions = [
  { value: 90, label: '3M' },
  { value: 180, label: '6M' },
  { value: 365, label: '1Y' },
]

const selectedPeriod = ref(180)
const loading = ref(false)
const taData = ref<TechnicalResponse | null>(null)

const signals = computed(() => taData.value?.signals || null)
const hasData = computed(() => taData.value !== null && taData.value.count > 0)
const valueUnit = computed(() => props.valueUnit ?? 'đ')
const yAxisTitle = computed(() => props.yAxisTitle ?? 'Giá (VNĐ)')

const signalLabel = computed(() => {
  const map: Record<string, string> = {
    strong_buy: 'MUA MẠNH',
    buy: 'MUA',
    neutral: 'TRUNG LẬP',
    sell: 'BÁN',
    strong_sell: 'BÁN MẠNH',
  }
  return map[signals.value?.summary || 'neutral'] || 'TRUNG LẬP'
})

const signalBadgeClass = computed(() => {
  const s = signals.value?.summary
  if (s === 'strong_buy' || s === 'buy') return 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
  if (s === 'strong_sell' || s === 'sell') return 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
  return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
})

// Dates for x-axis (sampled for readability)
const xLabels = computed(() => {
  if (!taData.value) return []
  const times = taData.value.ohlcv.time
  const step = Math.max(1, Math.floor(times.length / 30))
  return times.map((t, i) => (i % step === 0 ? t.slice(5) : ''))
})

// ======== Price Chart: Close + SMA20/50 + Bollinger Bands ========
const priceChartSeries = computed(() => {
  if (!taData.value) return []
  const { close } = taData.value.ohlcv
  const { sma_20, sma_50, bb_upper, bb_lower } = taData.value.indicators
  return [
    { name: 'Giá đóng cửa', data: close },
    { name: 'SMA 20', data: sma_20 },
    { name: 'SMA 50', data: sma_50 },
    { name: 'BB Upper', data: bb_upper },
    { name: 'BB Lower', data: bb_lower },
  ]
})

const priceChartOptions = computed(() => ({
  chart: {
    id: 'price-ta',
    group: 'ta-sync',
    fontFamily: 'Outfit, sans-serif',
    toolbar: { show: false },
    zoom: { enabled: true },
  },
  colors: ['#465FFF', '#F59E0B', '#10B981', '#E879F9', '#E879F9'],
  stroke: {
    width: [2.5, 1.5, 1.5, 1, 1],
    dashArray: [0, 4, 4, 5, 5],
  },
  fill: { opacity: 1 },
  legend: { position: 'top' as const, horizontalAlign: 'left' as const, fontSize: '12px' },
  grid: {
    borderColor: '#e5e7eb',
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
  },
  dataLabels: { enabled: false },
  markers: { size: 0 },
  tooltip: {
    shared: true,
    y: {
      formatter: (val: number) =>
        val != null ? new Intl.NumberFormat('vi-VN', {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }).format(val) + ` ${valueUnit.value}` : '-',
    },
  },
  xaxis: {
    categories: xLabels.value,
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { rotate: -45, style: { fontSize: '10px' } },
    tooltip: { enabled: false },
  },
  yaxis: {
    title: { text: yAxisTitle.value, style: { fontSize: '11px' } },
    labels: {
      formatter: (val: number) => new Intl.NumberFormat('vi-VN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(val),
    },
  },
}))

// ======== RSI Chart ========
const rsiChartSeries = computed(() => {
  if (!taData.value) return []
  return [{ name: 'RSI 14', data: taData.value.indicators.rsi_14 }]
})

const rsiChartOptions = computed(() => ({
  chart: {
    id: 'rsi-ta',
    group: 'ta-sync',
    fontFamily: 'Outfit, sans-serif',
    toolbar: { show: false },
    zoom: { enabled: true },
  },
  colors: ['#8B5CF6'],
  stroke: { width: 2 },
  legend: { show: false },
  grid: {
    borderColor: '#e5e7eb',
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
  },
  dataLabels: { enabled: false },
  markers: { size: 0 },
  annotations: {
    yaxis: [
      { y: 70, borderColor: '#EF4444', strokeDashArray: 4, label: { text: 'Quá mua (70)', style: { fontSize: '10px', color: '#EF4444' } } },
      { y: 30, borderColor: '#22C55E', strokeDashArray: 4, label: { text: 'Quá bán (30)', style: { fontSize: '10px', color: '#22C55E' } } },
    ],
  },
  tooltip: {
    y: { formatter: (val: number) => (val != null ? val.toFixed(2) : '-') },
  },
  xaxis: {
    categories: xLabels.value,
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { show: false },
  },
  yaxis: {
    min: 0,
    max: 100,
    title: { text: 'RSI', style: { fontSize: '11px' } },
    labels: { formatter: (val: number) => val.toFixed(0) },
  },
}))

// ======== MACD Chart ========
const macdChartSeries = computed(() => {
  if (!taData.value) return []
  const { macd_line, macd_signal, macd_histogram } = taData.value.indicators
  return [
    { name: 'MACD', type: 'line', data: macd_line },
    { name: 'Đường tín hiệu', type: 'line', data: macd_signal },
    { name: 'Cột dao động', type: 'bar', data: macd_histogram },
  ]
})

const macdChartOptions = computed(() => ({
  chart: {
    id: 'macd-ta',
    group: 'ta-sync',
    fontFamily: 'Outfit, sans-serif',
    toolbar: { show: false },
    zoom: { enabled: true },
  },
  colors: ['#3B82F6', '#F97316', '#94A3B8'],
  stroke: { width: [2, 2, 0] },
  plotOptions: {
    bar: {
      columnWidth: '60%',
      colors: {
        ranges: [
          { from: -999999, to: 0, color: '#EF4444' },
          { from: 0, to: 999999, color: '#22C55E' },
        ],
      },
    },
  },
  legend: { position: 'top' as const, horizontalAlign: 'left' as const, fontSize: '12px' },
  grid: {
    borderColor: '#e5e7eb',
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
  },
  dataLabels: { enabled: false },
  markers: { size: 0 },
  tooltip: {
    shared: true,
    y: { formatter: (val: number) => (val != null ? val.toFixed(2) : '-') },
  },
  xaxis: {
    categories: xLabels.value,
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: { rotate: -45, style: { fontSize: '10px' } },
    tooltip: { enabled: false },
  },
  yaxis: {
    title: { text: 'MACD', style: { fontSize: '11px' } },
    labels: { formatter: (val: number) => val.toFixed(0) },
  },
}))

// ======== Data Loading ========
async function loadData() {
  loading.value = true
  try {
    taData.value = await props.fetchTechnical(props.symbol, selectedPeriod.value)
  } catch {
    taData.value = null
  } finally {
    loading.value = false
  }
}

watch(() => props.symbol, () => loadData())
watch(() => props.refreshToken, () => loadData())
onMounted(() => loadData())
</script>
