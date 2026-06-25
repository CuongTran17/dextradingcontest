<template>
  <div
    class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
  >
    <div class="mb-5 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
      <div class="w-full">
        <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">
          Hiệu suất danh mục
        </h3>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Thống kê hiệu suất theo {{ selectedLabel.toLowerCase() }}
        </p>
      </div>

      <div class="relative">
        <div class="inline-flex items-center gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-900">
          <button
            v-for="option in periodOptions"
            :key="option.value"
            :class="[
              selectedPeriod === option.value
                ? 'bg-white text-gray-900 shadow-theme-xs dark:bg-gray-800 dark:text-white'
                : 'text-gray-500 dark:text-gray-400',
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors hover:text-gray-900 dark:hover:bg-gray-800 dark:hover:text-white',
            ]"
            @click="selectPeriod(option.value)"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="hasHistoricalData" class="max-w-full overflow-x-auto custom-scrollbar">
      <div class="-ml-4 min-w-[700px] pl-2 xl:min-w-full">
        <VueApexCharts type="area" height="310" :options="chartOptions" :series="chartSeries" />
      </div>
    </div>

    <div
      v-else
      class="flex items-center justify-center rounded-lg border border-dashed border-gray-200 py-10 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"
    >
      Chưa có dữ liệu lịch sử để hiển thị biểu đồ.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import VueApexCharts from 'vue3-apexcharts'

const props = defineProps<{
  symbol?: string
  historicalData?: { time: string; close: number }[]
}>()

const periodOptions = [
  { value: 'monthly', label: 'Tháng' },
  { value: 'quarterly', label: 'Quý' },
  { value: 'annually', label: 'Năm' },
]

const selectedPeriod = ref('monthly')

const selectedLabel = computed(() => {
  const opt = periodOptions.find((o) => o.value === selectedPeriod.value)
  return opt?.label || 'tháng'
})

function selectPeriod(period: string) {
  selectedPeriod.value = period
}

const PERIOD_WINDOW: Record<string, number> = {
  monthly: 30,
  quarterly: 90,
  annually: 365,
}

const hasHistoricalData = computed(() =>
  Boolean(props.historicalData && props.historicalData.length > 0),
)

const filteredHistory = computed(() => {
  const source = props.historicalData || []
  if (source.length === 0) return []

  const windowSize = PERIOD_WINDOW[selectedPeriod.value] || source.length
  return source.slice(-Math.min(windowSize, source.length))
})

const chartSeries = computed(() => {
  if (filteredHistory.value.length > 0) {
    return [{
      name: props.symbol || 'Danh mục',
      data: filteredHistory.value.map((d) => d.close),
    }]
  }
  return []
})

const chartOptions = computed(() => ({
  legend: {
    show: false,
  },
  colors: ['#465FFF'],
  chart: {
    fontFamily: 'Outfit, sans-serif',
    type: 'area' as const,
    toolbar: { show: false },
    zoom: { enabled: true },
  },
  fill: {
    gradient: {
      enabled: true,
      opacityFrom: 0.55,
      opacityTo: 0,
    },
  },
  stroke: {
    curve: 'straight' as const,
    width: 2,
  },
  markers: { size: 0 },
  grid: {
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
  },
  dataLabels: { enabled: false },
  tooltip: {
    x: { format: 'dd MMM yyyy' },
    y: {
      formatter: (val: number) => new Intl.NumberFormat('vi-VN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(val) + ' đ',
    },
  },
  xaxis: {
    type: 'category' as const,
    categories: filteredHistory.value.map((d) => d.time),
    axisBorder: { show: false },
    axisTicks: { show: false },
    labels: {
      rotate: -45,
      rotateAlways: false,
      style: { fontSize: '12px' },
    },
    tooltip: { enabled: false },
  },
  yaxis: {
    title: { style: { fontSize: '0px' } },
    labels: {
      formatter: (val: number) => val.toFixed(2),
    },
  },
}))
</script>
