<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div class="flex flex-col gap-2">
          <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Market Overview</h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">
            Chỉ số thị trường, biểu đồ index, heatmap và top movers từ dữ liệu thật vnstock.
          </p>
        </div>

        <button
          class="inline-flex items-center justify-center rounded-xl border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
          :disabled="isRefreshing"
          @click="refreshAll(true)"
        >
          {{ isRefreshing ? 'Đang làm mới...' : 'Tải Dữ Liệu Thật' }}
        </button>
      </div>

      <p
        v-if="refreshError"
        class="rounded-xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-500/40 dark:bg-error-500/10 dark:text-error-300"
      >
        {{ refreshError }}
      </p>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <button
          v-for="item in indexCards"
          :key="item.symbol"
          class="rounded-2xl border bg-white p-5 text-left transition-all hover:-translate-y-0.5 dark:bg-white/[0.03]"
          :class="activeIndexSymbol === item.symbol
            ? 'border-brand-400 ring-2 ring-brand-200 dark:border-brand-500 dark:ring-brand-500/30'
            : 'border-gray-200 dark:border-gray-800'"
          @click="selectIndex(item.symbol)"
        >
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{{ item.name }}</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">
            {{ formatNumber(item.price) }}
          </p>
          <p
            class="mt-1 text-sm font-medium"
            :class="item.changePercent >= 0 ? 'text-success-600' : 'text-error-600'"
          >
            {{ item.changePercent >= 0 ? '+' : '' }}{{ item.changePercent.toFixed(2) }}%
          </p>
        </button>

        <div
          v-if="indicesLoading && indexCards.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 bg-white p-5 text-sm text-gray-500 dark:border-gray-700 dark:bg-white/[0.03] dark:text-gray-400 sm:col-span-2 xl:col-span-4"
        >
          Đang tải dữ liệu chỉ số thị trường từ vnstock...
        </div>

        <div
          v-else-if="indexCards.length === 0"
          class="rounded-2xl border border-dashed border-gray-200 bg-white p-5 text-sm text-gray-500 dark:border-gray-700 dark:bg-white/[0.03] dark:text-gray-400 sm:col-span-2 xl:col-span-4"
        >
          Chưa có dữ liệu chỉ số thị trường từ backend.
        </div>
      </div>

      <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Biểu đồ {{ activeIndexName }}</h2>
            <p class="text-xs text-gray-500 dark:text-gray-400">
              Nhấn vào VN-Index, VN30, HNX hoặc UPCoM để đổi biểu đồ.
            </p>
          </div>

          <div class="flex flex-wrap items-center gap-1.5">
            <button
              v-for="tf in CHART_TIMEFRAMES"
              :key="tf.value"
              class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
              :class="
                chartTimeframe === tf.value
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
              "
              @click="chartTimeframe = tf.value"
            >
              {{ tf.label }}
            </button>
            <button
              class="inline-flex items-center justify-center rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200 dark:hover:bg-gray-800"
              :disabled="chartLoading || !activeIndexSymbol"
              @click="loadActiveIndexHistory(true)"
            >
              {{ chartLoading ? 'Đang tải...' : 'Làm mới' }}
            </button>
          </div>
        </div>

        <div
          v-if="chartLoading && activeIndexHistory.length === 0"
          class="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"
        >
          Đang tải dữ liệu lịch sử chỉ số...
        </div>

        <div
          v-else-if="activeIndexHistory.length === 0"
          class="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400"
        >
          Chưa có dữ liệu lịch sử cho chỉ số này.
        </div>

        <TradingViewChart
          v-else
          :symbol="activeIndexSymbol"
          chart-kind="line"
          :historical-data="activeIndexHistory"
        />
      </section>

      <TechnicalAnalysisChart
        :symbol="activeIndexSymbol"
        value-unit="điểm"
        y-axis-title="Điểm"
        :fetch-technical="getActiveIndexTechnicalAnalysis"
      />

      <div class="grid grid-cols-12 gap-4 md:gap-6">
        <section
          class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] xl:col-span-8"
        >
          <div class="mb-4 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">VN30 Heatmap</h2>
            <p class="text-xs text-gray-500 dark:text-gray-400">Color intensity reflects % change</p>
          </div>

          <div class="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            <button
              v-for="stock in heatmapStocks"
              :key="stock.symbol"
              class="rounded-xl p-3 text-left transition-transform hover:-translate-y-0.5"
              :style="{ backgroundColor: heatColor(stock.changePercent) }"
              @click="goToStock(stock.symbol)"
            >
              <p class="text-sm font-semibold text-gray-900">{{ stock.symbol }}</p>
              <p class="text-xs text-gray-700 truncate">{{ stock.companyName }}</p>
              <p class="mt-2 text-sm font-medium text-gray-900">
                {{ stock.changePercent >= 0 ? '+' : '' }}{{ stock.changePercent.toFixed(2) }}%
              </p>
            </button>
          </div>

          <p
            v-if="stocksLoading && heatmapStocks.length === 0"
            class="mt-3 text-sm text-gray-500 dark:text-gray-400"
          >
            Đang tải heatmap thực tế...
          </p>
        </section>

        <!-- Cột phải: Top Gainers & Top Losers tách biệt -->
        <div class="col-span-12 xl:col-span-4 flex flex-col gap-4 md:gap-6">
          <!-- Thẻ Top Gainers -->
          <section
            class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] flex-1 flex flex-col"
          >
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Top Tăng Giá (Gainers)</h2>
            <ul class="space-y-2 flex-1 flex flex-col">
              <li
                v-for="(stock, index) in topGainers"
                :key="`g-${stock.symbol}`"
                class="flex flex-1 items-center justify-between rounded-lg px-3 py-2 transition-all"
                :class="[
                  index === 0
                    ? 'bg-success-500 text-white shadow-sm dark:bg-success-600'
                    : 'bg-success-50 dark:bg-success-500/10'
                ]"
              >
                <button
                  class="font-semibold transition-colors"
                  :class="index === 0 ? 'text-white hover:text-white/80' : 'text-gray-800 dark:text-white/90 hover:text-brand-500'"
                  @click="goToStock(stock.symbol)"
                >
                  {{ stock.symbol }}
                </button>
                <span
                  class="text-sm font-bold"
                  :class="index === 0 ? 'text-white' : 'text-success-600 dark:text-success-400'"
                >
                  +{{ stock.changePercent.toFixed(2) }}%
                </span>
              </li>
            </ul>
            <p
              v-if="stocksLoading && topGainers.length === 0"
              class="mt-3 text-sm text-gray-500 dark:text-gray-400"
            >
              Đang tải top movers...
            </p>
          </section>

          <!-- Thẻ Top Losers -->
          <section
            class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] flex-1 flex flex-col"
          >
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Top Giảm Giá (Losers)</h2>
            <ul class="space-y-2 flex-1 flex flex-col">
              <li
                v-for="(stock, index) in topLosers"
                :key="`l-${stock.symbol}`"
                class="flex flex-1 items-center justify-between rounded-lg px-3 py-2 transition-all"
                :class="[
                  index === 0
                    ? 'bg-error-500 text-white shadow-sm dark:bg-error-600'
                    : 'bg-error-50 dark:bg-error-500/10'
                ]"
              >
                <button
                  class="font-semibold transition-colors"
                  :class="index === 0 ? 'text-white hover:text-white/80' : 'text-gray-800 dark:text-white/90 hover:text-brand-500'"
                  @click="goToStock(stock.symbol)"
                >
                  {{ stock.symbol }}
                </button>
                <span
                  class="text-sm font-bold"
                  :class="index === 0 ? 'text-white' : 'text-error-600 dark:text-error-400'"
                >
                  {{ stock.changePercent.toFixed(2) }}%
                </span>
              </li>
            </ul>
            <p
              v-if="stocksLoading && topLosers.length === 0"
              class="mt-3 text-sm text-gray-500 dark:text-gray-400"
            >
              Đang tải top movers...
            </p>
          </section>
        </div>
      </div>

      <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Sector Performance</h2>

        <div class="space-y-3">
          <div
            v-for="sector in sectorPerformance"
            :key="sector.name"
            class="grid grid-cols-12 items-center gap-3"
          >
            <p class="col-span-4 text-sm font-medium text-gray-700 dark:text-gray-300 sm:col-span-3">
              {{ sector.name }}
            </p>
            <div class="col-span-6 h-2 rounded-full bg-gray-100 dark:bg-gray-800 sm:col-span-7">
              <div
                class="h-2 rounded-full"
                :class="sector.avgChange >= 0 ? 'bg-success-500' : 'bg-error-500'"
                :style="{ width: `${Math.min(100, Math.abs(sector.avgChange) * 10)}%` }"
              ></div>
            </div>
            <p
              class="col-span-2 text-right text-sm font-semibold sm:col-span-2"
              :class="sector.avgChange >= 0 ? 'text-success-600' : 'text-error-600'"
            >
              {{ sector.avgChange >= 0 ? '+' : '' }}{{ sector.avgChange.toFixed(2) }}%
            </p>
          </div>
        </div>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import TechnicalAnalysisChart from '@/components/stock/TechnicalAnalysisChart.vue'
import TradingViewChart from '@/components/stock/TradingViewChart.vue'
import { VN30_TICKERS } from '@/composables/useStockData'
import { MARKET_SECTORS, type SectorDefinition } from '@/constants/marketSectors'
import { fetchMarketIndexTechnicalAnalysis } from '@/services/marketIndexTechnical'
import {
  stockBackendApi,
  type HistoricalRecord,
  type MarketIndexQuote,
  type StockSnapshot,
  type TechnicalResponse,
} from '@/services/stockBackendApi'

interface IndexCard {
  symbol: string
  name: string
  price: number
  change: number
  changePercent: number
}

interface MarketStock {
  symbol: string
  companyName: string
  price: number
  changePercent: number
  dataStatus?: string
}

const CHART_TIMEFRAMES = [
  { label: '1T', value: '1m' },
  { label: '3T', value: '3m' },
  { label: '6T', value: '6m' },
  { label: '1N', value: '1y' },
] as const

function timeframeToLimit(tf: string): number {
  if (tf === '1m') return 30
  if (tf === '3m') return 90
  if (tf === '6m') return 180
  return 365
}

const router = useRouter()
const route = useRoute()
const marketIndices = ref<MarketIndexQuote[]>([])
const marketStocks = ref<MarketStock[]>([])
const activeIndexSymbol = ref<string>('VNINDEX')
const activeIndexHistory = ref<HistoricalRecord[]>([])
const indicesLoading = ref(false)
const stocksLoading = ref(false)
const chartLoading = ref(false)
const chartTimeframe = ref<string>('1y')
const isRefreshing = ref(false)
const refreshError = ref<string | null>(null)
let autoRefreshTimer: ReturnType<typeof setInterval> | null = null

const sectors: SectorDefinition[] = MARKET_SECTORS

const allStocks = computed<MarketStock[]>(() =>
  marketStocks.value
    .filter((item) => hasUsableSnapshotPrice(item))
    .sort((a, b) => b.changePercent - a.changePercent),
)

const heatmapStocks = computed(() =>
  [...allStocks.value]
    .sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))
    .slice(0, 24),
)
const topGainers = computed(() =>
  allStocks.value
    .filter((item) => item.changePercent >= 0)
    .slice(0, 5),
)
const topLosers = computed(() =>
  allStocks.value
    .filter((item) => item.changePercent < 0)
    .sort((a, b) => a.changePercent - b.changePercent)
    .slice(0, 5),
)

const indexCards = computed<IndexCard[]>(() =>
  marketIndices.value.map(normalizeIndexQuote).slice(0, 4),
)

const activeIndexName = computed(() => {
  const card = indexCards.value.find((item) => item.symbol === activeIndexSymbol.value)
  return card?.name || activeIndexSymbol.value
})

const stockBySymbol = computed(() => {
  const mapping: Record<string, MarketStock> = {}
  allStocks.value.forEach((item) => {
    mapping[item.symbol] = item
  })
  return mapping
})

const sectorPerformance = computed(() =>
  sectors
    .map((sector) => {
      const members = sector.symbols
        .map((symbol) => stockBySymbol.value[symbol])
        .filter((item): item is MarketStock => hasUsableSnapshotPrice(item))

      if (members.length === 0) {
        return {
          name: sector.name,
          avgChange: 0,
        }
      }

      const avgChange = members.reduce((sum, member) => sum + member.changePercent, 0) / members.length
      return {
        name: sector.name,
        avgChange,
      }
    })
    .sort((a, b) => b.avgChange - a.avgChange),
)

function toNumber(value: unknown): number {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/,/g, ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return 0
}

function hasUsableSnapshotPrice(item: { price?: number; dataStatus?: string } | null | undefined): boolean {
  return Boolean(item && Number(item.price) > 0 && item.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}

function normalizeIndexQuote(record: MarketIndexQuote): IndexCard {
  return {
    symbol: String(record.symbol || '').toUpperCase(),
    name: String(record.name || record.symbol || '').trim(),
    price: toNumber(record.price),
    change: toNumber(record.change),
    changePercent: toNumber(record.changePercent),
  }
}

function normalizeSnapshot(item: StockSnapshot): MarketStock {
  const symbol = String(item.symbol || '').toUpperCase()
  return {
    symbol,
    companyName: (item.companyName || symbol || 'VN30').trim(),
    price: toNumber(item.price),
    changePercent: toNumber(item.changePercent),
    dataStatus: item.dataStatus,
  }
}

function heatColor(changePercent: number): string {
  const intensity = Math.min(1, Math.abs(changePercent) / 4)
  if (changePercent >= 0) {
    return `rgba(18, 183, 106, ${0.12 + intensity * 0.28})`
  }
  return `rgba(240, 68, 56, ${0.12 + intensity * 0.28})`
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function goToStock(symbol: string): void {
  void router.push(`/stocks/${symbol}`)
}

async function loadMarketIndices(refresh: boolean = false): Promise<void> {
  indicesLoading.value = true
  try {
    const response = await stockBackendApi.getMarketIndices(undefined, undefined, 4, refresh)
    marketIndices.value = response.data

    if (!marketIndices.value.find((item) => item.symbol === activeIndexSymbol.value) && marketIndices.value.length > 0) {
      activeIndexSymbol.value = marketIndices.value[0].symbol
    }
  } catch {
    marketIndices.value = []
  } finally {
    indicesLoading.value = false
  }
}

async function loadMarketSnapshots(refresh: boolean = false): Promise<void> {
  stocksLoading.value = true
  try {
    const response = await stockBackendApi.getSnapshots(VN30_TICKERS, refresh)
    marketStocks.value = response.data.map(normalizeSnapshot)
  } catch {
    marketStocks.value = []
  } finally {
    stocksLoading.value = false
  }
}

async function loadActiveIndexHistory(refresh: boolean = false): Promise<void> {
  const target = activeIndexSymbol.value
  if (!target) {
    activeIndexHistory.value = []
    return
  }

  chartLoading.value = true
  try {
    const response = await stockBackendApi.getMarketIndexHistory(target, undefined, undefined, timeframeToLimit(chartTimeframe.value), refresh)
    activeIndexHistory.value = response.data
  } catch {
    activeIndexHistory.value = []
  } finally {
    chartLoading.value = false
  }
}

async function getActiveIndexTechnicalAnalysis(symbol: string, limit: number): Promise<TechnicalResponse | null> {
  return fetchMarketIndexTechnicalAnalysis(symbol, limit, false)
}

function selectIndex(symbol: string): void {
  if (activeIndexSymbol.value === symbol) {
    return
  }

  activeIndexSymbol.value = symbol
  void loadActiveIndexHistory(false)
}

watch(chartTimeframe, () => {
  void loadActiveIndexHistory(false)
})

async function refreshAll(forceRefresh: boolean): Promise<void> {
  if (isRefreshing.value) {
    return
  }

  isRefreshing.value = true
  refreshError.value = null
  try {
    await loadMarketIndices(forceRefresh)
    await Promise.all([
      loadMarketSnapshots(forceRefresh),
      loadActiveIndexHistory(forceRefresh),
    ])
  } catch {
    refreshError.value = 'Không thể đồng bộ dữ liệu thị trường thực tế từ backend.'
  } finally {
    isRefreshing.value = false
  }
}

onMounted(async () => {
  const requestedIndex = String(route.query.index || '').toUpperCase()
  if (requestedIndex) {
    activeIndexSymbol.value = requestedIndex
  }

  await refreshAll(false)
  autoRefreshTimer = setInterval(() => {
    void refreshAll(false)
  }, 60000)
})

onUnmounted(() => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
    autoRefreshTimer = null
  }
})
</script>
