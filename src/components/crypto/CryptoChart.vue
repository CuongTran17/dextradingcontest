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

    <!-- SMA Indicator Value Bar -->
    <div
      v-if="activeIndicators.includes('SMA')"
      class="mt-2 flex items-center justify-between rounded bg-gray-50 px-3 py-1.5 text-xs dark:bg-gray-900/50"
    >
      <div class="flex items-center gap-2">
        <span class="font-medium text-blue-500">SMA (20):</span>
        <span class="text-gray-700 dark:text-gray-300 font-mono">{{ formatPrice(latestSmaValue) }}</span>
      </div>
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          @click="toggleMinimize('SMA')"
        >
          {{ isMinimized('SMA') ? 'Show line' : 'Hide line' }}
        </button>
        <button
          type="button"
          class="text-gray-400 hover:text-red-500 font-semibold"
          @click="closeIndicator('SMA')"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- EMA Indicator Value Bar -->
    <div
      v-if="activeIndicators.includes('EMA')"
      class="mt-2 flex items-center justify-between rounded bg-gray-50 px-3 py-1.5 text-xs dark:bg-gray-900/50"
    >
      <div class="flex items-center gap-2">
        <span class="font-medium text-rose-500">EMA (9):</span>
        <span class="text-gray-700 dark:text-gray-300 font-mono">{{ formatPrice(latestEmaValue) }}</span>
      </div>
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
          @click="toggleMinimize('EMA')"
        >
          {{ isMinimized('EMA') ? 'Show line' : 'Hide line' }}
        </button>
        <button
          type="button"
          class="text-gray-400 hover:text-red-500 font-semibold"
          @click="closeIndicator('EMA')"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- MACD Panel -->
    <div
      v-if="activeIndicators.includes('MACD')"
      data-test="indicator-panel-MACD"
      class="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/70"
    >
      <div class="flex items-center justify-between gap-3 text-xs">
        <div class="flex items-center gap-2">
          <span class="font-semibold text-gray-700 dark:text-gray-200">MACD 12 26 close 9 EMA EMA</span>
          <span v-if="macdLatest && !isMinimized('MACD')" class="flex gap-2 font-medium">
            <span class="text-rose-500">{{ formatIndicatorValue(macdLatest.histogram ?? 0) }}</span>
            <span class="text-sky-500">{{ formatIndicatorValue(macdLatest.macd ?? 0) }}</span>
            <span class="text-amber-500">{{ formatIndicatorValue(macdLatest.signal ?? 0) }}</span>
          </span>
        </div>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            @click="toggleMinimize('MACD')"
          >
            {{ isMinimized('MACD') ? 'Expand' : 'Collapse' }}
          </button>
          <button
            type="button"
            class="text-gray-400 hover:text-red-500 font-semibold"
            @click="closeIndicator('MACD')"
          >
            ✕
          </button>
        </div>
      </div>
      <div v-show="!isMinimized('MACD')" ref="macdChartEl" class="mt-3 h-28 w-full"></div>
    </div>

    <!-- RSI Panel -->
    <div
      v-if="activeIndicators.includes('RSI')"
      class="mt-3 rounded-md border border-gray-200 bg-gray-50 p-3 dark:border-gray-800 dark:bg-gray-900/70"
    >
      <div class="flex items-center justify-between gap-3 text-xs">
        <div class="flex items-center gap-2">
          <span class="font-medium text-gray-600 dark:text-gray-300">RSI (14)</span>
          <span v-if="latestRsiValue !== null && !isMinimized('RSI')" class="font-mono text-purple-600 dark:text-purple-400">
            {{ formatIndicatorValue(latestRsiValue) }}
          </span>
        </div>
        <div class="flex items-center gap-3">
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200"
            @click="toggleMinimize('RSI')"
          >
            {{ isMinimized('RSI') ? 'Expand' : 'Collapse' }}
          </button>
          <button
            type="button"
            class="text-gray-400 hover:text-red-500 font-semibold"
            @click="closeIndicator('RSI')"
          >
            ✕
          </button>
        </div>
      </div>
      <div v-show="!isMinimized('RSI')" ref="rsiChartEl" class="mt-3 h-28 w-full"></div>
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
import { computed, onBeforeUnmount, onMounted, ref, watch, nextTick } from 'vue'

import { fetchCryptoCandlesWithSource, fetchCryptoIndicator } from '@/services/cryptoMarketData'
import { onCryptoRealtimeCandle } from '@/services/cryptoRealtime'
import type { Candle, CryptoIndicator, CryptoIndicatorResponse, CryptoSymbol, Timeframe } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  timeframe: Timeframe
}>()

const chartEl = ref<HTMLElement | null>(null)
const macdChartEl = ref<HTMLElement | null>(null)
const rsiChartEl = ref<HTMLElement | null>(null)

const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const indicatorMenuOpen = ref(false)
const indicatorSearch = ref('')
const activeIndicators = ref<string[]>([])
const minimizedIndicators = ref<Set<string>>(new Set())

const selectedIndicator = computed(() => activeIndicators.value.includes('MACD') ? 'MACD' as const : null)
const macdData = ref<CryptoIndicatorResponse | null>(null)
const rsiData = ref<CryptoIndicatorResponse | null>(null)
const emaData = ref<CryptoIndicatorResponse | null>(null)
const smaData = ref<CryptoIndicatorResponse | null>(null)

const statusText = computed(() => {
  if (status.value === 'loading') return 'Loading market candles'
  if (status.value === 'unavailable') return 'Market candles unavailable'
  return 'Binance Spot / warehouse candles'
})

type IndicatorOption = {
  id: 'MACD' | 'RSI' | 'EMA' | 'SMA' | 'Volume'
  label: string
  description: string
  enabled: boolean
}

const indicatorOptions: IndicatorOption[] = [
  { id: 'MACD', label: 'MACD', description: 'Moving Average Convergence Divergence', enabled: true },
  { id: 'RSI', label: 'RSI', description: 'Relative Strength Index (14)', enabled: true },
  { id: 'EMA', label: 'EMA', description: 'Exponential Moving Average (9)', enabled: true },
  { id: 'SMA', label: 'SMA', description: 'Simple Moving Average (20)', enabled: true },
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
let emaSeries: ReturnType<IChartApi['addSeries']> | null = null
let smaSeries: ReturnType<IChartApi['addSeries']> | null = null

let macdChart: IChartApi | null = null
let macdHistogramSeries: ReturnType<IChartApi['addSeries']> | null = null
let macdLineSeries: ReturnType<IChartApi['addSeries']> | null = null
let macdSignalSeries: ReturnType<IChartApi['addSeries']> | null = null

let rsiChart: IChartApi | null = null
let rsiLineSeries: ReturnType<IChartApi['addSeries']> | null = null

let priceCrosshairHandler: MouseEventHandler<Time> | null = null
let macdCrosshairHandler: MouseEventHandler<Time> | null = null
let priceLogicalRangeHandler: ((range: LogicalRange | null) => void) | null = null
let macdLogicalRangeHandler: ((range: LogicalRange | null) => void) | null = null
let unsubscribeCandle: (() => void) | undefined
const candles = ref<Candle[]>([])
let syncingCrosshair = false
let syncingLogicalRange = false

// Legends current values from loaded backend data
const latestEmaValue = computed(() => {
  const points = emaData.value?.points
  return points && points.length > 0 ? points.at(-1)?.value ?? null : null
})

const latestSmaValue = computed(() => {
  const points = smaData.value?.points
  return points && points.length > 0 ? points.at(-1)?.value ?? null : null
})

const latestRsiValue = computed(() => {
  const points = rsiData.value?.points
  return points && points.length > 0 ? points.at(-1)?.value ?? null : null
})

function formatPrice(value?: number | null): string {
  if (typeof value !== 'number') return '--'
  return new Intl.NumberFormat('en-US', { maximumFractionDigits: 4 }).format(value)
}

function selectIndicator(id: 'MACD' | 'RSI' | 'EMA' | 'SMA' | 'Volume') {
  if (!activeIndicators.value.includes(id)) {
    activeIndicators.value = [...activeIndicators.value, id]
  }
  indicatorMenuOpen.value = false
}

function closeIndicator(id: string) {
  activeIndicators.value = activeIndicators.value.filter((item) => item !== id)
  minimizedIndicators.value.delete(id)

  if (id === 'MACD') {
    if (macdChart) {
      macdChart.remove()
      macdChart = null
      macdHistogramSeries = null
      macdLineSeries = null
      macdSignalSeries = null
    }
  } else if (id === 'RSI') {
    if (rsiChart) {
      rsiChart.remove()
      rsiChart = null
      rsiLineSeries = null
    }
  }
}

function toggleMinimize(id: string) {
  if (minimizedIndicators.value.has(id)) {
    minimizedIndicators.value.delete(id)
  } else {
    minimizedIndicators.value.add(id)
  }
}

function isMinimized(id: string): boolean {
  return minimizedIndicators.value.has(id)
}

function setChartData(candlesData: Candle[]) {
  candlesData.sort((left, right) => left.time - right.time)
  series?.setData(
    candlesData.map((candle) => ({
      ...candle,
      time: candle.time as never,
    })),
  )
  chart?.timeScale().fitContent()

  renderOverlays()
  void loadActiveIndicators()
  renderRsiChart()
}

async function renderChart() {
  if (!chartEl.value) return
  if (!chart) {
    chart = createChart(chartEl.value, {
      height: 320,
      layout: { background: { color: 'transparent' }, textColor: '#6b7280' },
      grid: { vertLines: { color: '#e5e7eb' }, horzLines: { color: '#e5e7eb' } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, timeVisible: true },
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
    const result = await fetchCryptoCandlesWithSource(props.symbol, props.timeframe, 1000)
    candles.value = result.candles
    setChartData(candles.value)
    status.value = 'ready'
  } catch {
    series?.setData([])
    status.value = 'unavailable'
  }
}

async function loadIndicatorData(indicator: 'MACD' | 'RSI' | 'EMA' | 'SMA') {
  try {
    const data = await fetchCryptoIndicator(props.symbol, indicatorTimeframe.value, indicator, 1000)
    if (indicator === 'MACD') {
      macdData.value = data
      renderMacdChart()
    } else if (indicator === 'RSI') {
      rsiData.value = data
      renderRsiChart()
    } else if (indicator === 'EMA') {
      emaData.value = data
      renderOverlays()
    } else if (indicator === 'SMA') {
      smaData.value = data
      renderOverlays()
    }
  } catch (error) {
    console.error(`Failed to load indicator ${indicator}:`, error)
  }
}

async function loadActiveIndicators() {
  const promises = activeIndicators.value.map((indicator) => {
    if (['MACD', 'RSI', 'EMA', 'SMA'].includes(indicator)) {
      return loadIndicatorData(indicator as 'MACD' | 'RSI' | 'EMA' | 'SMA')
    }
    return Promise.resolve()
  })
  await Promise.all(promises)
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
    timeScale: { borderVisible: false, timeVisible: true },
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

function ensureRsiChart() {
  if (!rsiChartEl.value || rsiChart) return

  rsiChart = createChart(rsiChartEl.value, {
    height: 112,
    layout: { background: { color: 'transparent' }, textColor: '#6b7280' },
    grid: { vertLines: { color: '#e5e7eb' }, horzLines: { color: '#e5e7eb' } },
    rightPriceScale: { borderVisible: false },
    timeScale: { borderVisible: false, timeVisible: true },
  })
  rsiLineSeries = rsiChart.addSeries(LineSeries, {
    color: '#8b5cf6',
    lineWidth: 2,
  })
  
  rsiLineSeries.createPriceLine({
    price: 70,
    color: '#f43f5e',
    lineWidth: 1,
    lineStyle: 2,
    axisLabelVisible: true,
  })
  rsiLineSeries.createPriceLine({
    price: 30,
    color: '#10b981',
    lineWidth: 1,
    lineStyle: 2,
    axisLabelVisible: true,
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

function rsiValueAt(time: Time | undefined): number | null {
  if (time === undefined) return null
  const key = timeKey(time)
  const points = rsiData.value?.points
  return points ? points.find((point) => timeKey(point.time as never) === key)?.value ?? null : null
}

function renderOverlays() {
  if (!chart) return

  // EMA Overlay
  if (activeIndicators.value.includes('EMA') && !minimizedIndicators.value.has('EMA') && emaData.value) {
    if (!emaSeries) {
      emaSeries = chart.addSeries(LineSeries, {
        color: '#ef4444',
        lineWidth: 2,
      })
    }
    const points = emaData.value.points
    emaSeries.setData(
      points.map((pt) => ({
        time: pt.time as never,
        value: pt.value ?? 0,
      }))
    )
  } else {
    if (emaSeries) {
      chart.removeSeries(emaSeries)
      emaSeries = null
    }
  }

  // SMA Overlay
  if (activeIndicators.value.includes('SMA') && !minimizedIndicators.value.has('SMA') && smaData.value) {
    if (!smaSeries) {
      smaSeries = chart.addSeries(LineSeries, {
        color: '#3b82f6',
        lineWidth: 2,
      })
    }
    const points = smaData.value.points
    smaSeries.setData(
      points.map((pt) => ({
        time: pt.time as never,
        value: pt.value ?? 0,
      }))
    )
  } else {
    if (smaSeries) {
      chart.removeSeries(smaSeries)
      smaSeries = null
    }
  }
}

function renderMacdChart() {
  if (!activeIndicators.value.includes('MACD') || minimizedIndicators.value.has('MACD') || !macdData.value) {
    if (macdChart) {
      macdChart.remove()
      macdChart = null
      macdHistogramSeries = null
      macdLineSeries = null
      macdSignalSeries = null
    }
    return
  }
  ensureMacdChart()
  const points = macdData.value.points
  macdHistogramSeries?.setData(
    points.map((point) => ({
      time: point.time as never,
      value: point.histogram ?? 0,
      color: (point.histogram ?? 0) >= 0 ? '#10b981' : '#f43f5e',
    })),
  )
  macdLineSeries?.setData(points.map((point) => ({ time: point.time as never, value: point.macd ?? 0 })))
  macdSignalSeries?.setData(points.map((point) => ({ time: point.time as never, value: point.signal ?? 0 })))
  macdChart?.timeScale().fitContent()
}

function renderRsiChart() {
  if (!activeIndicators.value.includes('RSI') || minimizedIndicators.value.has('RSI') || !rsiData.value) {
    if (rsiChart) {
      rsiChart.remove()
      rsiChart = null
      rsiLineSeries = null
    }
    return
  }
  ensureRsiChart()
  const points = rsiData.value.points
  rsiLineSeries?.setData(
    points.map((pt) => ({
      time: pt.time as never,
      value: pt.value ?? 0,
    }))
  )
  rsiChart?.timeScale().fitContent()
}

function getActiveCharts() {
  const list: IChartApi[] = []
  if (chart) list.push(chart)
  if (macdChart && activeIndicators.value.includes('MACD') && !minimizedIndicators.value.has('MACD')) {
    list.push(macdChart)
  }
  if (rsiChart && activeIndicators.value.includes('RSI') && !minimizedIndicators.value.has('RSI')) {
    list.push(rsiChart)
  }
  return list
}

let activeSyncHandlers: { chart: IChartApi; crosshairMove?: any; logicalRangeChange?: any }[] = []

function cleanupChartSync() {
  activeSyncHandlers.forEach(({ chart: c, crosshairMove, logicalRangeChange }) => {
    if (crosshairMove) c.unsubscribeCrosshairMove(crosshairMove)
    if (logicalRangeChange) c.timeScale().unsubscribeVisibleLogicalRangeChange(logicalRangeChange)
  })
  activeSyncHandlers = []
}

function wireChartSync() {
  cleanupChartSync()

  const active = getActiveCharts()
  if (active.length <= 1) return

  let isSyncing = false

  active.forEach((currentChart) => {
    const crosshairMove = (param: any) => {
      if (isSyncing || !param.time) return
      isSyncing = true
      
      active.forEach((otherChart) => {
        if (otherChart === currentChart) return
        
        let targetSeries: any = null
        let value: number | null = null
        
        if (otherChart === chart) {
          targetSeries = series
          value = candleCloseAt(param.time)
        } else if (otherChart === macdChart) {
          targetSeries = macdLineSeries
          value = macdValueAt(param.time)
        } else if (otherChart === rsiChart) {
          targetSeries = rsiLineSeries
          value = rsiValueAt(param.time)
        }
        
        if (value === null || !targetSeries) {
          otherChart.clearCrosshairPosition()
        } else {
          otherChart.setCrosshairPosition(value, param.time, targetSeries)
        }
      })
      isSyncing = false
    }

    const logicalRangeChange = (range: LogicalRange | null) => {
      if (isSyncing || !range) return
      isSyncing = true
      active.forEach((otherChart) => {
        if (otherChart === currentChart) return
        otherChart.timeScale().setVisibleLogicalRange(range)
      })
      isSyncing = false
    }

    currentChart.subscribeCrosshairMove(crosshairMove)
    currentChart.timeScale().subscribeVisibleLogicalRangeChange(logicalRangeChange)

    activeSyncHandlers.push({
      chart: currentChart,
      crosshairMove,
      logicalRangeChange,
    })
  })
}

const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '1h': 3600,
  '4h': 14400,
  '1D': 86400,
}

function applyRealtimeCandle(candle1m: Candle) {
  const bucketSize = TIMEFRAME_SECONDS[props.timeframe] || 60
  const bucketTime = Math.floor(candle1m.time / bucketSize) * bucketSize

  const existingIndex = candles.value.findIndex((item) => item.time === bucketTime)

  if (existingIndex !== -1) {
    const existing = candles.value[existingIndex]
    const updated = {
      ...existing,
      high: Math.max(existing.high, candle1m.close, candle1m.high),
      low: Math.min(existing.low, candle1m.close, candle1m.low),
      close: candle1m.close,
    }
    candles.value[existingIndex] = updated
    series?.update({ ...updated, time: updated.time as never })
  } else {
    const newCandle = {
      time: bucketTime,
      open: candle1m.open,
      high: candle1m.high,
      low: candle1m.low,
      close: candle1m.close,
      volume: candle1m.volume,
    }
    candles.value = [...candles.value, newCandle].slice(-1000)
    series?.update({ ...newCandle, time: newCandle.time as never })
  }

  renderOverlays()
  renderRsiChart()
  renderMacdChart()
}

onMounted(() => {
  unsubscribeCandle = onCryptoRealtimeCandle((event) => {
    if (event.symbol === props.symbol) {
      applyRealtimeCandle(event.candle)
      status.value = 'ready'
    }
  })
  void renderChart()
})

watch(() => [props.symbol, props.timeframe], () => {
  void renderChart()
})

watch(
  () => [...activeIndicators.value],
  async () => {
    await loadActiveIndicators()
    await nextTick()
    wireChartSync()
  },
  { deep: true }
)

watch(
  () => [...minimizedIndicators.value],
  async () => {
    renderOverlays()
    renderRsiChart()
    renderMacdChart()
    await nextTick()
    wireChartSync()
  },
  { deep: true }
)

onBeforeUnmount(() => {
  unsubscribeCandle?.()
  cleanupChartSync()
  chart?.remove()
  macdChart?.remove()
  rsiChart?.remove()
  chart = null
  series = null
  emaSeries = null
  smaSeries = null
  macdChart = null
  macdHistogramSeries = null
  macdLineSeries = null
  macdSignalSeries = null
  rsiChart = null
  rsiLineSeries = null
})
</script>
