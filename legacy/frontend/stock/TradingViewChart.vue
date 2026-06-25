<template>
  <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">TradingView Lightweight Chart</h2>
        <p class="text-xs text-gray-500 dark:text-gray-400">{{ chartCaption }} for {{ tradingViewSymbol }}</p>
      </div>
      <div class="flex flex-wrap items-center justify-end gap-1.5">
        <slot />
        <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300">
          {{ historyCount }} bars
        </span>
      </div>
    </div>

    <div class="h-[520px] w-full overflow-hidden rounded-xl border border-gray-100 dark:border-gray-800">
      <div ref="chartContainer" class="h-full w-full"></div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import {
  CandlestickSeries,
  ColorType,
  HistogramSeries,
  LineSeries,
  TickMarkType,
  createChart,
  type CandlestickData,
  type HistogramData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'

interface OhlcvPoint {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const VIETNAM_TIME_ZONE = 'Asia/Ho_Chi_Minh'
const vietnamTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  timeZone: VIETNAM_TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})
const vietnamDateFormatter = new Intl.DateTimeFormat('vi-VN', {
  timeZone: VIETNAM_TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
})
const vietnamDateTimeFormatter = new Intl.DateTimeFormat('vi-VN', {
  timeZone: VIETNAM_TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

const props = withDefaults(
  defineProps<{
    symbol: string
    historicalData?: OhlcvPoint[]
    chartKind?: 'candlestick' | 'line'
    theme?: 'light' | 'dark'
  }>(),
  {
    historicalData: () => [],
    chartKind: 'candlestick',
    theme: 'light',
  },
)

const chartContainer = ref<HTMLElement | null>(null)

const tradingViewSymbol = computed(() => `HOSE:${props.symbol.toUpperCase()}`)
const historyCount = computed(() => props.historicalData.length)
const chartCaption = computed(() => props.chartKind === 'line' ? 'Line chart' : 'Candlestick chart')

let chart: IChartApi | null = null
let candleSeries: ISeriesApi<'Candlestick', Time> | null = null
let lineSeries: ISeriesApi<'Line', Time> | null = null
let volumeSeries: ISeriesApi<'Histogram', Time> | null = null
let resizeObserver: ResizeObserver | null = null

function toUtcTimestamp(input: string): UTCTimestamp | null {
  const parsedMs = Date.parse(input)
  if (Number.isNaN(parsedMs)) {
    return null
  }
  return Math.floor(parsedMs / 1000) as UTCTimestamp
}

function chartTimeToDate(time: Time): Date | null {
  if (typeof time === 'number') {
    return new Date(time * 1000)
  }

  if (typeof time === 'string') {
    const parsedMs = Date.parse(time.length === 10 ? `${time}T00:00:00+07:00` : time)
    return Number.isNaN(parsedMs) ? null : new Date(parsedMs)
  }

  const parsedMs = Date.parse(`${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}T00:00:00+07:00`)
  return Number.isNaN(parsedMs) ? null : new Date(parsedMs)
}

function formatChartTickMark(time: Time, tickMarkType: TickMarkType): string | null {
  const date = chartTimeToDate(time)
  if (!date) {
    return null
  }

  if (tickMarkType === TickMarkType.Time || tickMarkType === TickMarkType.TimeWithSeconds) {
    return vietnamTimeFormatter.format(date)
  }

  if (tickMarkType === TickMarkType.DayOfMonth) {
    return vietnamDateFormatter.format(date)
  }

  if (tickMarkType === TickMarkType.Month) {
    const month = Number(new Intl.DateTimeFormat('en-US', {
      timeZone: VIETNAM_TIME_ZONE,
      month: 'numeric',
    }).format(date))
    return Number.isFinite(month) ? `T${month}` : null
  }

  return new Intl.DateTimeFormat('vi-VN', {
    timeZone: VIETNAM_TIME_ZONE,
    year: 'numeric',
  }).format(date)
}

function formatChartTime(time: Time): string {
  const date = chartTimeToDate(time)
  return date ? vietnamDateTimeFormatter.format(date) : String(time)
}

function toChartData(source: OhlcvPoint[]): {
  candles: CandlestickData<Time>[]
  line: LineData<Time>[]
  volumes: HistogramData<Time>[]
} {
  const merged: Array<
    { time: Time; open: number; high: number; low: number; close: number; volume: number }
  > = []

  source.forEach((item) => {
    const time = toUtcTimestamp(item.time)
    if (!time) {
      return
    }
    merged.push({
      time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
    })
  })

  merged.sort((a, b) => Number(a.time) - Number(b.time))

  const candles: CandlestickData<Time>[] = merged.map((item) => ({
    time: item.time,
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
  }))

  const line: LineData<Time>[] = merged.map((item) => ({
    time: item.time,
    value: item.close,
  }))

  const volumes: HistogramData<Time>[] = merged.map((item) => ({
    time: item.time,
    value: item.volume,
    color: item.close >= item.open ? 'rgba(22,163,74,0.55)' : 'rgba(220,38,38,0.55)',
  }))

  return { candles, line, volumes }
}

function clearChart(): void {
  if (resizeObserver) {
    resizeObserver.disconnect()
    resizeObserver = null
  }

  if (chart) {
    chart.remove()
    chart = null
  }

  candleSeries = null
  lineSeries = null
  volumeSeries = null
}

function applyData(): void {
  if ((!candleSeries && !lineSeries) || !volumeSeries) {
    return
  }

  const { candles, line, volumes } = toChartData(props.historicalData)
  if (candleSeries) {
    candleSeries.setData(candles)
  }
  if (lineSeries) {
    lineSeries.setData(line)
  }
  volumeSeries.setData(volumes)

  if (chart && candles.length > 0) {
    chart.timeScale().fitContent()
  }
}

function createLightweightChart(): void {
  const host = chartContainer.value
  if (!host) {
    return
  }

  clearChart()

  const isDark = props.theme === 'dark'
  chart = createChart(host, {
    width: host.clientWidth,
    height: host.clientHeight || 520,
    layout: {
      background: {
        type: ColorType.Solid,
        color: isDark ? '#0f172a' : '#ffffff',
      },
      textColor: isDark ? '#cbd5e1' : '#334155',
    },
    grid: {
      vertLines: {
        color: isDark ? 'rgba(148,163,184,0.1)' : 'rgba(148,163,184,0.25)',
      },
      horzLines: {
        color: isDark ? 'rgba(148,163,184,0.1)' : 'rgba(148,163,184,0.25)',
      },
    },
    rightPriceScale: {
      borderColor: isDark ? '#334155' : '#cbd5e1',
    },
    localization: {
      locale: 'vi-VN',
      timeFormatter: formatChartTime,
    },
    timeScale: {
      borderColor: isDark ? '#334155' : '#cbd5e1',
      timeVisible: true,
      secondsVisible: false,
      tickMarkFormatter: formatChartTickMark,
    },
  })

  if (props.chartKind === 'line') {
    lineSeries = chart.addSeries(LineSeries, {
      color: '#2563eb',
      lineWidth: 2,
      priceLineVisible: true,
      lastValueVisible: true,
    })
  } else {
    candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: '#16a34a',
      downColor: '#dc2626',
      borderVisible: false,
      wickUpColor: '#16a34a',
      wickDownColor: '#dc2626',
    })
  }

  volumeSeries = chart.addSeries(HistogramSeries, {
    color: 'rgba(71,85,105,0.45)',
    priceFormat: {
      type: 'volume',
    },
    priceScaleId: '',
    priceLineVisible: false,
    lastValueVisible: false,
  })

  chart.priceScale('').applyOptions({
    scaleMargins: {
      top: 0.72,
      bottom: 0,
    },
  })

  chart.priceScale('right').applyOptions({
    scaleMargins: {
      top: 0.1,
      bottom: 0.32,
    },
  })

  applyData()

  resizeObserver = new ResizeObserver(() => {
    if (!chart || !host) {
      return
    }
    chart.applyOptions({ width: host.clientWidth, height: host.clientHeight || 520 })
  })
  resizeObserver.observe(host)
}

watch(
  () => props.historicalData,
  () => {
    applyData()
  },
  { deep: true },
)

watch(
  () => [props.symbol, props.theme, props.chartKind],
  async () => {
    await nextTick()
    createLightweightChart()
  },
)

onMounted(() => {
  createLightweightChart()
})

onUnmounted(() => {
  clearChart()
})
</script>
