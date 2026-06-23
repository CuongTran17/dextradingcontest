<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{{ symbol }} Chart</h2>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {{ timeframe }} {{ dataSource === 'binance' ? 'Live Binance Spot' : 'mock fallback' }} candles
        </p>
      </div>
    </div>
    <div ref="chartEl" class="h-80 w-full"></div>
  </section>
</template>

<script setup lang="ts">
import { CandlestickSeries, createChart, type IChartApi } from 'lightweight-charts'
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchCryptoCandlesWithSource, getCryptoCandles } from '@/services/cryptoMarketData'
import type { CryptoSymbol, MarketDataSource, Timeframe } from '@/types/crypto'

const props = defineProps<{
  symbol: CryptoSymbol
  timeframe: Timeframe
}>()

const chartEl = ref<HTMLElement | null>(null)
const dataSource = ref<MarketDataSource>('mock')
let chart: IChartApi | null = null
let series: ReturnType<IChartApi['addSeries']> | null = null

function setChartData(candles = getCryptoCandles(props.symbol, props.timeframe, 80)) {
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

  setChartData()
  const result = await fetchCryptoCandlesWithSource(props.symbol, props.timeframe, 80)
  dataSource.value = result.source
  setChartData(result.candles)
}

onMounted(() => void renderChart())
watch(() => [props.symbol, props.timeframe], () => void renderChart())

onBeforeUnmount(() => {
  chart?.remove()
  chart = null
  series = null
})
</script>
