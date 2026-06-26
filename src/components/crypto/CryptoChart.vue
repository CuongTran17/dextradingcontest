<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{{ symbol }} Chart</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ timeframe }} {{ statusText }}
        </p>
      </div>
    </div>
    <div ref="chartEl" class="h-80 w-full"></div>
  </section>
</template>

<script setup lang="ts">
import { CandlestickSeries, createChart, type IChartApi } from 'lightweight-charts'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchCryptoCandlesWithSource } from '@/services/cryptoMarketData'
import { onCryptoRealtimeCandle } from '@/services/cryptoRealtime'
import type { Candle, CryptoSymbol, Timeframe } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  timeframe: Timeframe
}>()

const chartEl = ref<HTMLElement | null>(null)
const status = ref<'loading' | 'ready' | 'unavailable'>('loading')
const statusText = computed(() => {
  if (status.value === 'loading') return 'Loading market candles'
  if (status.value === 'unavailable') return 'Market candles unavailable'
  return 'Binance Spot / warehouse candles'
})
let chart: IChartApi | null = null
let series: ReturnType<IChartApi['addSeries']> | null = null
let unsubscribeCandle: (() => void) | undefined
const candles = ref<Candle[]>([])

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
watch(() => [props.symbol, props.timeframe], () => void renderChart())

onBeforeUnmount(() => {
  unsubscribeCandle?.()
  chart?.remove()
  chart = null
  series = null
})
</script>
