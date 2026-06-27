<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{{ symbol }} Chart</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ timeframe }} {{ statusText }}
        </p>
      </div>
      <div class="relative">
        <button
          data-test="indicator-picker-button"
          type="button"
          class="inline-flex items-center gap-2 rounded-md border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 dark:border-gray-700 dark:text-gray-200 dark:hover:bg-white/[0.05]"
          @click="indicatorMenuOpen = !indicatorMenuOpen"
        >
          Indicators
        </button>
        <div
          v-if="indicatorMenuOpen"
          class="absolute right-0 z-20 mt-2 w-64 rounded-lg border border-gray-200 bg-white p-3 shadow-lg dark:border-gray-800 dark:bg-gray-950"
        >
          <input
            v-model="indicatorSearch"
            data-test="indicator-search"
            type="search"
            class="mb-2 w-full rounded-md border border-gray-200 px-3 py-2 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-white"
            placeholder="Search indicators"
          />
          <button
            v-for="option in filteredIndicators"
            :key="option.id"
            :data-test="`indicator-option-${option.id}`"
            type="button"
            :disabled="!option.enabled"
            class="flex w-full items-center justify-between rounded-md px-3 py-2 text-left text-sm hover:bg-gray-50 dark:hover:bg-white/[0.05]"
            :class="!option.enabled ? 'cursor-not-allowed opacity-50' : ''"
            @click="selectIndicator(option.id)"
          >
            <span class="font-medium text-gray-800 dark:text-gray-100">{{ option.label }}</span>
            <span class="text-xs text-gray-400">{{ option.description }}</span>
          </button>
        </div>
      </div>
    </div>
    <div ref="chartEl" class="h-80 w-full"></div>
    <div
      v-if="selectedIndicator === 'MACD'"
      data-test="indicator-panel-MACD"
      class="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/70"
    >
      <div class="flex items-center justify-between gap-3 text-xs">
        <span class="font-medium text-gray-600 dark:text-gray-300">MACD 12 26 close 9 EMA EMA</span>
        <span v-if="macdLatest" class="flex gap-2 font-medium">
          <span class="text-rose-500">{{ formatIndicatorValue(macdLatest.histogram) }}</span>
          <span class="text-sky-500">{{ formatIndicatorValue(macdLatest.macd) }}</span>
          <span class="text-amber-500">{{ formatIndicatorValue(macdLatest.signal) }}</span>
        </span>
      </div>
      <div ref="macdChartEl" class="mt-3 h-28 w-full"></div>
    </div>
  </section>
</template>

<script setup lang="ts">
import {
  CandlestickSeries,
  HistogramSeries,
  LineSeries,
  createChart,
  type IChartApi,
  type LogicalRange,
  type MouseEventHandler,
  type Time,
} from 'lightweight-charts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchCryptoCandlesWithSource, fetchCryptoIndicator } from '@/services/cryptoMarketData'
import { onCryptoRealtimeCandle } from '@/services/cryptoRealtime'
import type { Candle, CryptoIndicator, CryptoIndicatorResponse, CryptoSymbol, Timeframe } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  timeframe: Timeframe
}>()

const chartEl = ref<HTMLElement | null>(null)
const macdChartEl = ref<HTMLElement | null>(null)
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const indicatorMenuOpen = ref(false)
const indicatorSearch = ref('')
const selectedIndicator = ref<CryptoIndicator | null>(null)
const macdData = ref<CryptoIndicatorResponse | null>(null)
const statusText = computed(() => {
  if (status.value === 'loading') return 'Loading market candles'
  if (status.value === 'unavailable') return 'Market candles unavailable'
  return 'Binance Spot / warehouse candles'
})
type IndicatorOption = {
  id: CryptoIndicator | 'RSI' | 'EMA' | 'SMA' | 'Volume'
  label: string
  description: string
  enabled: boolean
}

const indicatorOptions: IndicatorOption[] = [
  { id: 'MACD', label: 'MACD', description: 'DuckDB cache', enabled: true },
  { id: 'RSI', label: 'RSI', description: 'soon', enabled: false },
  { id: 'EMA', label: 'EMA', description: 'soon', enabled: false },
  { id: 'SMA', label: 'SMA', description: 'soon', enabled: false },
  { id: 'Volume', label: 'Volume', description: 'soon', enabled: false },
]
const filteredIndicators = computed(() => {
  const query = indicatorSearch.value.trim().toLowerCase()
  if (!query) return indicatorOptions
  return indicatorOptions.filter((option) => option.label.toLowerCase().includes(query))
})
const indicatorTimeframe = computed<Exclude<Timeframe, '1D'>>(() => (
  props.timeframe === '1D' ? '4h' : props.timeframe
))
const macdLatest = computed(() => macdData.value?.points.at(-1))
let chart: IChartApi | null = null
let series: ReturnType<IChartApi['addSeries']> | null = null
let macdChart: IChartApi | null = null
let macdHistogramSeries: ReturnType<IChartApi['addSeries']> | null = null
let macdLineSeries: ReturnType<IChartApi['addSeries']> | null = null
let macdSignalSeries: ReturnType<IChartApi['addSeries']> | null = null
let priceCrosshairHandler: MouseEventHandler<Time> | null = null
let macdCrosshairHandler: MouseEventHandler<Time> | null = null
let priceLogicalRangeHandler: ((range: LogicalRange | null) => void) | null = null
let macdLogicalRangeHandler: ((range: LogicalRange | null) => void) | null = null
let unsubscribeCandle: (() => void) | undefined
const candles = ref<Candle[]>([])
let syncingCrosshair = false
let syncingLogicalRange = false

function setChartData(candles: Candle[]) {
  candles.sort((left, right) => left.time - right.time)
  series?.setData(
    candles.map((candle) => ({
      ...candle,
      time: candle.time as never,
    })),
  )
  chart?.timeScale().fitContent()
}

async function renderChart() {
  if (!chartEl.value) return
  if (!chart) {
    chart = createChart(chartEl.value, {
      height: 320,
      layout: { background: { color: 'transparent' }, textColor: '#6b7280' },
      grid: { vertLines: { color: '#e5e7eb' }, horzLines: { color: '#e5e7eb' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
    })
    series = chart.addSeries(CandlestickSeries, {
      upColor: '#059669',
      downColor: '#dc2626',
      borderVisible: false,
      wickUpColor: '#059669',
      wickDownColor: '#dc2626',
    })
  }

  status.value = 'loading'
  try {
    const result = await fetchCryptoCandlesWithSource(props.symbol, props.timeframe, 80)
    candles.value = result.candles
    setChartData(candles.value)
    status.value = 'ready'
  } catch {
    series?.setData([])
    status.value = 'unavailable'
  }
}

async function loadSelectedIndicator() {
  if (selectedIndicator.value !== 'MACD') return
  macdData.value = await fetchCryptoIndicator(props.symbol, indicatorTimeframe.value, 'MACD', 120)
  renderMacdChart()
}

function selectIndicator(indicator: IndicatorOption['id']) {
  if (indicator !== 'MACD') return
  selectedIndicator.value = indicator
  indicatorMenuOpen.value = false
  void loadSelectedIndicator()
}

function formatIndicatorValue(value: number): string {
  return new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)
}

function ensureMacdChart() {
  if (!macdChartEl.value || macdChart) return

  macdChart = createChart(macdChartEl.value, {
    height: 112,
    layout: { background: { color: 'transparent' }, textColor: '#6b7280' },
    grid: { vertLines: { color: '#e5e7eb' }, horzLines: { color: '#e5e7eb' } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false },
  })
  macdHistogramSeries = macdChart.addSeries(HistogramSeries, {
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
  })
  macdLineSeries = macdChart.addSeries(LineSeries, {
    color: '#0ea5e9',
    lineWidth: 1,
    priceLineVisible: false,
  })
  macdSignalSeries = macdChart.addSeries(LineSeries, {
    color: '#f59e0b',
    lineWidth: 1,
    priceLineVisible: false,
  })
}

function timeKey(time: Time | undefined): string {
  return typeof time === 'object' ? JSON.stringify(time) : String(time)
}

function candleCloseAt(time: Time | undefined): number | null {
  if (time === undefined) return null
  const key = timeKey(time)
  return candles.value.find((candle) => timeKey(candle.time as never) === key)?.close ?? null
}

function macdValueAt(time: Time | undefined): number | null {
  if (time === undefined) return null
  const key = timeKey(time)
  return macdData.value?.points.find((point) => timeKey(point.time as never) === key)?.macd ?? null
}

function syncCrosshairToTarget(
  targetChart: IChartApi | null,
  targetSeries: ReturnType<IChartApi['addSeries']> | null,
  time: Time | undefined,
  value: number | null,
) {
  if (!targetChart || !targetSeries || syncingCrosshair) return

  syncingCrosshair = true
  if (time === undefined || value === null) {
    targetChart.clearCrosshairPosition()
  } else {
    targetChart.setCrosshairPosition(value, time, targetSeries)
  }
  syncingCrosshair = false
}

function syncLogicalRangeToTarget(targetChart: IChartApi | null, range: LogicalRange | null) {
  if (!targetChart || !range || syncingLogicalRange) return

  syncingLogicalRange = true
  targetChart.timeScale().setVisibleLogicalRange(range)
  syncingLogicalRange = false
}

function cleanupChartSync() {
  if (chart && priceCrosshairHandler) chart.unsubscribeCrosshairMove(priceCrosshairHandler)
  if (macdChart && macdCrosshairHandler) macdChart.unsubscribeCrosshairMove(macdCrosshairHandler)
  if (chart && priceLogicalRangeHandler) {
    chart.timeScale().unsubscribeVisibleLogicalRangeChange(priceLogicalRangeHandler)
  }
  if (macdChart && macdLogicalRangeHandler) {
    macdChart.timeScale().unsubscribeVisibleLogicalRangeChange(macdLogicalRangeHandler)
  }
  priceCrosshairHandler = null
  macdCrosshairHandler = null
  priceLogicalRangeHandler = null
  macdLogicalRangeHandler = null
}

function wireChartSync() {
  if (!chart || !series || !macdChart || !macdLineSeries) return

  cleanupChartSync()

  priceCrosshairHandler = (param) => {
    syncCrosshairToTarget(macdChart, macdLineSeries, param.time, macdValueAt(param.time))
  }
  macdCrosshairHandler = (param) => {
    syncCrosshairToTarget(chart, series, param.time, candleCloseAt(param.time))
  }
  priceLogicalRangeHandler = (range) => syncLogicalRangeToTarget(macdChart, range)
  macdLogicalRangeHandler = (range) => syncLogicalRangeToTarget(chart, range)

  chart.subscribeCrosshairMove(priceCrosshairHandler)
  macdChart.subscribeCrosshairMove(macdCrosshairHandler)
  chart.timeScale().subscribeVisibleLogicalRangeChange(priceLogicalRangeHandler)
  macdChart.timeScale().subscribeVisibleLogicalRangeChange(macdLogicalRangeHandler)
}

function renderMacdChart() {
  if (selectedIndicator.value !== 'MACD' || !macdData.value) return
  ensureMacdChart()
  const points = macdData.value.points
  macdHistogramSeries?.setData(
    points.map((point) => ({
      time: point.time as never,
      value: point.histogram,
      color: point.histogram >= 0 ? '#10b981' : '#f43f5e',
    })),
  )
  macdLineSeries?.setData(points.map((point) => ({ time: point.time as never, value: point.macd })))
  macdSignalSeries?.setData(points.map((point) => ({ time: point.time as never, value: point.signal })))
  macdChart?.timeScale().fitContent()
  wireChartSync()
}

function applyRealtimeCandle(candle: Candle) {
  const next = candles.value.filter((item) => item.time !== candle.time)
  next.push(candle)
  candles.value = next.slice(-80)
  series?.update({ ...candle, time: candle.time as never })
}

onMounted(() => {
  unsubscribeCandle = onCryptoRealtimeCandle((event) => {
    if (event.symbol === props.symbol && props.timeframe === '1m') {
      applyRealtimeCandle(event.candle)
      status.value = 'ready'
    }
  })
  void renderChart()
})
watch(() => [props.symbol, props.timeframe], () => {
  void renderChart()
  void loadSelectedIndicator()
})

onBeforeUnmount(() => {
  unsubscribeCandle?.()
  cleanupChartSync()
  chart?.remove()
  macdChart?.remove()
  chart = null
  series = null
  macdChart = null
  macdHistogramSeries = null
  macdLineSeries = null
  macdSignalSeries = null
})
</script>
