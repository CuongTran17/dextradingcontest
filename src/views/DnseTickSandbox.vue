<template>
  <main class="min-h-screen bg-slate-950 px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
    <section class="mx-auto max-w-7xl space-y-5">
      <header class="flex flex-col gap-3 border-b border-slate-800 pb-5 md:flex-row md:items-end md:justify-between">
        <div>
          <p class="text-sm font-medium text-cyan-300">DNSE Tick Sandbox</p>
          <h1 class="mt-1 text-2xl font-semibold text-white">Realtime latest trades</h1>
        </div>
        <div class="flex items-center gap-2 text-sm text-slate-300">
          <span class="h-2.5 w-2.5 rounded-full" :class="marketSessionDotClass" />
          {{ marketSessionLabel }}
        </div>
      </header>

      <section class="grid gap-4 lg:grid-cols-[minmax(0,1fr)_360px]">
        <div class="space-y-4">
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <label class="text-sm font-medium text-slate-200" for="symbols">Symbols</label>
            <div class="mt-2 flex flex-col gap-2 sm:flex-row">
              <input
                id="symbols"
                v-model="symbolsInput"
                class="min-h-11 flex-1 rounded-md border border-slate-700 bg-slate-950 px-3 text-sm text-white outline-none focus:border-cyan-400"
                placeholder="FPT,VCB,VIC"
              />
              <button class="btn-primary" type="button" @click="refreshOnce">Refresh once</button>
              <button v-if="!isPolling" class="btn-secondary" type="button" @click="startPolling">Start</button>
              <button v-else class="btn-danger" type="button" @click="stopPolling">Stop</button>
            </div>
            <p class="mt-2 text-xs text-slate-400">
              Poll interval: {{ effectivePollIntervalMs }}ms. Route nay chi de test, khong dat lenh.
            </p>
          </div>

          <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <div class="flex items-center justify-between gap-3">
              <div>
                <h2 class="text-sm font-semibold text-white">Tick chart</h2>
                <p class="mt-1 text-xs text-slate-400">
                  Showing {{ chartSymbol || 'first symbol' }} latest price points from this sandbox session.
                </p>
              </div>
              <div class="text-xs text-slate-400">{{ chartPointCount }} points</div>
            </div>
            <div ref="chartContainer" class="mt-4 h-[320px] w-full overflow-hidden rounded-md bg-slate-950"></div>
          </div>

          <div class="overflow-hidden rounded-lg border border-slate-800 bg-slate-900">
            <div class="grid grid-cols-7 border-b border-slate-800 px-4 py-3 text-xs font-semibold uppercase text-slate-400">
              <span>Symbol</span>
              <span>Price</span>
              <span>Volume</span>
              <span class="col-span-2">Trade time</span>
              <span>Source</span>
              <span>Latency</span>
            </div>
            <div v-if="ticks.length === 0" class="px-4 py-10 text-center text-sm text-slate-400">
              {{ emptyTickMessage }}
            </div>
            <div
              v-for="tick in ticks"
              :key="tick.symbol"
              class="grid grid-cols-7 items-center border-b border-slate-800 px-4 py-3 text-sm last:border-b-0"
            >
              <span class="font-semibold text-white">{{ tick.symbol }}</span>
              <span class="tabular-nums text-emerald-300">{{ formatNumber(tick.price) }}</span>
              <span class="tabular-nums">{{ formatNumber(tick.volume) }}</span>
              <span class="col-span-2 truncate text-slate-300">{{ formatTradeTime(tick) }}</span>
              <span class="text-xs uppercase text-amber-300">{{ tick.storage_source || latestResponse?.data_source || '-' }}</span>
              <span class="tabular-nums text-slate-300">{{ tick.latency_ms ?? '-' }}ms</span>
            </div>
          </div>
        </div>

        <aside class="space-y-4">
          <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 class="text-sm font-semibold text-white">Status</h2>
            <dl class="mt-3 space-y-2 text-sm">
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">DNSE config</dt>
                <dd :class="status?.configured ? 'text-emerald-300' : 'text-amber-300'">
                  {{ status?.status || 'loading' }}
                </dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Board</dt>
                <dd>{{ status?.board_id || '-' }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Market</dt>
                <dd>{{ marketSessionLabel }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Next open</dt>
                <dd>{{ formatSessionTime(status?.market_session?.next_open_at) }}</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Backend latency</dt>
                <dd>{{ latestResponse?.latency_ms ?? '-' }}ms</dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt class="text-slate-400">Last refresh</dt>
                <dd>{{ lastRefresh || '-' }}</dd>
              </div>
            </dl>
          </div>

          <div v-if="staleNotice" class="rounded-lg border border-amber-700 bg-amber-950/50 p-4 text-sm text-amber-100">
            {{ staleNotice }}
          </div>

          <div v-if="errorMessage" class="rounded-lg border border-red-800 bg-red-950/60 p-4 text-sm text-red-100">
            {{ errorMessage }}
          </div>

          <div class="rounded-lg border border-slate-800 bg-slate-900 p-4">
            <h2 class="text-sm font-semibold text-white">Raw JSON</h2>
            <pre class="mt-3 max-h-[460px] overflow-auto rounded-md bg-slate-950 p-3 text-xs text-slate-300">{{ rawJson }}</pre>
          </div>
        </aside>
      </section>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import {
  ColorType,
  LineSeries,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import {
  getDnseTickStatus,
  getLatestTicks,
  type DnseTick,
  type DnseTickResponse,
  type DnseTickStatus,
} from '@/services/dnseTickSandboxApi'

const symbolsInput = ref('FPT,VCB,VIC')
const ticks = ref<DnseTick[]>([])
const status = ref<DnseTickStatus | null>(null)
const latestResponse = ref<DnseTickResponse | null>(null)
const errorMessage = ref('')
const isPolling = ref(false)
const lastRefresh = ref('')
const chartContainer = ref<HTMLElement | null>(null)
const tickHistory = ref<LineData<Time>[]>([])
const chartSymbol = ref('')
let pollingTimer: number | null = null
let chart: IChartApi | null = null
let lineSeries: ISeriesApi<'Line', Time> | null = null
let resizeObserver: ResizeObserver | null = null

const pollIntervalMs = computed(() => status.value?.poll_interval_ms || 2000)
const effectivePollIntervalMs = computed(() => {
  if (status.value?.market_session?.is_polling_allowed === false) {
    return (status.value.closed_heartbeat_seconds || 300) * 1000
  }
  return pollIntervalMs.value
})
const rawJson = computed(() => JSON.stringify(latestResponse.value || status.value || {}, null, 2))
const chartPointCount = computed(() => tickHistory.value.length)
const marketSession = computed(() => latestResponse.value?.market_session || status.value?.market_session || null)
const missingSymbolsLabel = computed(() => (latestResponse.value?.missing_symbols || []).join(', '))
const emptyTickMessage = computed(() => {
  if (latestResponse.value?.status === 'market_closed') {
    return 'Chua co tick da luu cho cac ma duoc chon.'
  }
  return 'Chua co tick. Bam Refresh once hoac Start de test DNSE.'
})
const staleNotice = computed(() => {
  if (!latestResponse.value?.is_stale || ticks.value.length === 0) return ''
  const latest = [...ticks.value].sort(
    (a, b) => Date.parse(b.trade_time_local || b.trade_time || '') - Date.parse(a.trade_time_local || a.trade_time || ''),
  )[0]
  const missing = missingSymbolsLabel.value ? ` Thieu du lieu da luu cho: ${missingSymbolsLabel.value}.` : ''
  return `Thi truong da dong cua. Dang hien thi tick gan nhat luc ${formatTradeTime(latest)}.${missing}`
})
const marketSessionLabel = computed(() => {
  const session = marketSession.value
  if (!session) return isPolling.value ? 'Polling' : 'Stopped'
  const labels: Record<string, string> = {
    pre_open: 'Pre-open',
    open: isPolling.value ? 'Live polling' : 'Market open',
    lunch_break: 'Lunch break',
    closing: isPolling.value ? 'Closing polling' : 'Closing window',
    closed: 'Market closed',
    weekend: 'Weekend',
    holiday: 'Holiday',
    unknown: 'Unknown session',
  }
  return labels[session.status] || session.status
})
const marketSessionDotClass = computed(() => {
  const session = marketSession.value
  if (session?.is_polling_allowed) return isPolling.value ? 'bg-emerald-400' : 'bg-cyan-400'
  if (session) return 'bg-amber-400'
  return isPolling.value ? 'bg-emerald-400' : 'bg-slate-500'
})

function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('vi-VN').format(value)
}

function formatSessionTime(value: string | null | undefined): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('vi-VN')
}

function formatTradeTime(tick: DnseTick): string {
  const value = tick.trade_time_local || tick.trade_time
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
}

async function loadStatus(): Promise<void> {
  status.value = await getDnseTickStatus()
}

function toUtcTimestamp(input: string | null | undefined): UTCTimestamp {
  const parsedMs = input ? Date.parse(input) : Number.NaN
  if (!Number.isNaN(parsedMs)) {
    return Math.floor(parsedMs / 1000) as UTCTimestamp
  }
  return Math.floor(Date.now() / 1000) as UTCTimestamp
}

function createTickChart(): void {
  const host = chartContainer.value
  if (!host) return

  chart = createChart(host, {
    width: host.clientWidth,
    height: host.clientHeight || 320,
    layout: {
      background: { type: ColorType.Solid, color: '#020617' },
      textColor: '#cbd5e1',
    },
    grid: {
      vertLines: { color: 'rgba(148,163,184,0.12)' },
      horzLines: { color: 'rgba(148,163,184,0.12)' },
    },
    rightPriceScale: {
      borderColor: '#334155',
    },
    timeScale: {
      borderColor: '#334155',
      timeVisible: true,
      secondsVisible: true,
    },
    crosshair: {
      mode: 1,
    },
  })

  lineSeries = chart.addSeries(LineSeries, {
    color: '#22d3ee',
    lineWidth: 2,
    priceLineVisible: true,
  })
  lineSeries.setData(tickHistory.value)

  resizeObserver = new ResizeObserver(([entry]) => {
    if (!chart) return
    chart.applyOptions({ width: Math.floor(entry.contentRect.width) })
  })
  resizeObserver.observe(host)
}

function updateChartFromTicks(nextTicks: DnseTick[]): void {
  const firstTick = nextTicks.find((tick) => typeof tick.price === 'number')
  if (!firstTick || firstTick.price === null) return

  if (!chartSymbol.value) {
    chartSymbol.value = firstTick.symbol
  }

  const selectedTick = nextTicks.find((tick) => tick.symbol === chartSymbol.value) || firstTick
  if (selectedTick.price === null) return

  const point: LineData<Time> = {
    time: toUtcTimestamp(selectedTick.trade_time_local || selectedTick.trade_time),
    value: selectedTick.price,
  }
  const withoutSameTime = tickHistory.value.filter((item) => Number(item.time) !== Number(point.time))
  tickHistory.value = [...withoutSameTime, point]
    .sort((a, b) => Number(a.time) - Number(b.time))
    .slice(-240)

  if (lineSeries) {
    lineSeries.setData(tickHistory.value)
    chart?.timeScale().fitContent()
  }
}

async function refreshOnce(): Promise<void> {
  errorMessage.value = ''
  try {
    const response = await getLatestTicks(symbolsInput.value)
    latestResponse.value = response
    ticks.value = response.ticks
    updateChartFromTicks(response.ticks)
    lastRefresh.value = new Date().toLocaleTimeString('vi-VN')
    if (response.status === 'market_closed' && response.ticks.length === 0) {
      errorMessage.value = response.errors.market_session || 'market_closed'
    } else if (response.status === 'not_configured') {
      errorMessage.value = response.errors.config || 'DNSE credentials are not configured.'
    } else if (Object.keys(response.errors || {}).length > 0) {
      errorMessage.value = Object.entries(response.errors)
        .map(([symbol, message]) => `${symbol}: ${message}`)
        .join('\n')
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Could not fetch DNSE ticks'
  }
}

function scheduleNextPoll(): void {
  if (!isPolling.value) return
  pollingTimer = window.setTimeout(async () => {
    await refreshOnce()
    scheduleNextPoll()
  }, effectivePollIntervalMs.value)
}

async function startPolling(): Promise<void> {
  if (isPolling.value) return
  isPolling.value = true
  await refreshOnce()
  scheduleNextPoll()
}

function stopPolling(): void {
  isPolling.value = false
  if (pollingTimer !== null) {
    window.clearTimeout(pollingTimer)
    pollingTimer = null
  }
}

onMounted(async () => {
  await loadStatus()
  await nextTick()
  createTickChart()
})

onUnmounted(() => {
  stopPolling()
  resizeObserver?.disconnect()
  resizeObserver = null
  chart?.remove()
  chart = null
  lineSeries = null
})
</script>

<style scoped>
.btn-primary,
.btn-secondary,
.btn-danger {
  min-height: 44px;
  border-radius: 6px;
  padding: 0 14px;
  font-size: 14px;
  font-weight: 600;
}

.btn-primary {
  background: #06b6d4;
  color: #082f49;
}

.btn-secondary {
  border: 1px solid #334155;
  color: #e2e8f0;
}

.btn-danger {
  background: #dc2626;
  color: white;
}
</style>
