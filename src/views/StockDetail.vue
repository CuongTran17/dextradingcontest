<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div class="w-full md:max-w-3xl">
          <div class="flex w-full flex-col gap-4 rounded-2xl border border-gray-200 bg-white px-5 py-4 shadow-sm md:flex-row md:items-center md:justify-between dark:border-gray-700 dark:bg-gray-900/40">
            <div class="min-w-0">
              <h1 class="truncate text-xl font-bold text-gray-800 dark:text-white/90 md:text-2xl">
                {{ symbol }} - {{ displayName }}
              </h1>
              <p class="mt-1 truncate text-xs text-gray-500 dark:text-gray-400 md:text-sm">
                Giá, định giá, sổ lệnh và báo cáo tài chính.
              </p>
            </div>

            <div
              class="w-full rounded-xl border px-4 py-3 md:w-[240px] md:text-right"
              :class="[
                selectedStock && selectedStock.changePercent >= 0
                  ? 'border-success-200 bg-success-50 dark:border-success-700 dark:bg-success-500/15'
                  : 'border-error-200 bg-error-50 dark:border-error-700 dark:bg-error-500/15',
                priceFlashDirection === 'up'
                  ? 'price-flash-up'
                  : priceFlashDirection === 'down'
                    ? 'price-flash-down'
                    : '',
              ]"
            >
              <p
                class="text-2xl font-extrabold leading-none"
                :class="selectedStock && selectedStock.changePercent >= 0 ? 'text-success-700 dark:text-success-300' : 'text-error-700 dark:text-error-300'"
              >
                {{ currentPriceDisplay }}
              </p>
              <p
                class="mt-2 text-sm font-semibold"
                :class="selectedStock && selectedStock.changePercent >= 0 ? 'text-success-700 dark:text-success-300' : 'text-error-700 dark:text-error-300'"
              >
                Biến động: {{ currentChangeDisplay }}
              </p>
            </div>
          </div>
        </div>

        <div class="flex flex-col gap-2 md:items-end">
          <div class="w-full md:w-[180px]">
            <label class="mb-1 block text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Mã VN30
            </label>
            <select
              v-model="symbolPicker"
              class="w-full rounded-xl border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
              @change="onSymbolPickerChange"
            >
              <option
                v-for="ticker in vn30Tickers"
                :key="ticker"
                :value="ticker"
              >
                {{ ticker }}
              </option>
            </select>
          </div>

          <button
            class="inline-flex items-center justify-center gap-2 rounded-xl border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-medium text-brand-700 transition hover:bg-brand-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-brand-700/50 dark:bg-brand-500/10 dark:text-brand-300"
            :disabled="manualRefreshing || loadingOverview || loadingFinancials"
            @click="onRefreshClick"
          >
            <span
              v-if="manualRefreshing"
              class="h-3.5 w-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
            ></span>
            <span>{{ manualRefreshing ? 'Đang cập nhật...' : 'Tải lại dữ liệu' }}</span>
          </button>
        </div>
      </div>

      <div class="grid grid-cols-12 gap-4 md:gap-6">
        <section class="col-span-12">
          <TradingViewChart
            :symbol="symbol"
            :theme="tradingViewTheme"
            :historical-data="historySeries"
            :chart-kind="stockDetailChartKind"
          >
            <div class="flex flex-wrap items-center justify-end gap-2">
              <div class="inline-flex items-center rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
                <button
                  v-for="group in CHART_TIMEFRAME_GROUPS"
                  :key="group.value"
                  class="rounded-md px-3 py-1.5 text-xs font-semibold transition-colors"
                  :class="chartGroupButtonClass(group.value)"
                  @click="selectChartGroup(group.value)"
                >
                  {{ group.label }}
                </button>
              </div>

              <div class="inline-flex items-center gap-1">
                <button
                  v-for="tf in activeChartTimeframes"
                  :key="tf.value"
                  class="rounded-lg px-3 py-1.5 text-xs font-medium transition-colors"
                  :class="chartTimeframeButtonClass(tf.value)"
                  @click="selectChartTimeframe(tf.value)"
                >
                  {{ tf.label }}
                </button>
              </div>
            </div>
          </TradingViewChart>
        </section>

        <!-- Cột trái: Sổ lệnh & Tổng quan định giá -->
        <div class="col-span-12 xl:col-span-4 flex flex-col gap-4 md:gap-6">
          <section
            class="flex flex-col rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
            style="max-height: 480px"
          >
            <OrderLog
              :ticks="orderTicks"
              :total-count="orderTicksCount"
              :is-in-session="orderIsInSession"
              :loading="loadingOrderLog"
              @refresh="loadOrderLog(true)"
            />
          </section>

          <section
            class="flex-1 flex flex-col rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
          >
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Tổng quan định giá</h2>
            <div class="space-y-3 flex-1 flex flex-col">
              <div
                v-for="metric in valuationCards"
                :key="metric.label"
                class="flex flex-1 items-center justify-between rounded-xl border border-gray-100 px-4 py-2 dark:border-gray-800 hover:bg-gray-50/30 dark:hover:bg-white/[0.01] transition-colors"
              >
                <p class="text-sm text-gray-600 dark:text-gray-400">{{ metric.label }}</p>
                <p class="text-sm font-semibold text-gray-800 dark:text-white/90">{{ metric.value }}</p>
              </div>
            </div>
          </section>
        </div>

        <!-- Cột phải: Phân tích kỹ thuật & Biểu đồ danh mục -->
        <div class="col-span-12 xl:col-span-8 flex flex-col gap-4 md:gap-6">
          <section>
            <TechnicalAnalysisChart :symbol="symbol" :fetch-technical="getTechnicalAnalysis" :refresh-token="technicalRefreshToken" />
          </section>

          <section v-if="hasPortfolioPositionForSymbol">
            <PortfolioChart :symbol="symbol" :historical-data="chartHistory" />
          </section>
        </div>



        <section class="col-span-12 grid gap-4 xl:grid-cols-2">
          <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <div class="mb-4 flex items-start justify-between gap-3">
              <div>
                <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Tin tức</h2>
                <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Nguồn Google News từ lần ETL gần nhất.</p>
              </div>
              <button
                class="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 transition hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
                :disabled="loadingNews"
                @click="loadNewsAndEvents()"
              >
                Làm mới
              </button>
            </div>

            <div v-if="loadingNews" class="py-8 text-sm text-gray-500 dark:text-gray-400">
              Đang tải tin tức...
            </div>
            <div v-else-if="googleNewsItems.length === 0" class="py-8 text-sm text-gray-500 dark:text-gray-400">
              Chưa có tin Google News cho mã này.
            </div>
            <div v-else class="space-y-3">
              <a
                v-for="item in googleNewsItems"
                :key="item.id"
                :href="item.url || undefined"
                target="_blank"
                rel="noopener noreferrer"
                class="block rounded-xl border border-gray-100 p-4 transition hover:border-brand-200 hover:bg-brand-50/50 dark:border-gray-800 dark:hover:border-brand-700 dark:hover:bg-brand-500/10"
              >
                <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <span class="rounded-full bg-sky-50 px-2 py-0.5 font-medium text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                    {{ item.source || 'Google News' }}
                  </span>
                  <span>{{ formatNewsTime(item.publish_time || item.time) }}</span>
                </div>
                <h3 class="mt-2 line-clamp-2 text-sm font-semibold leading-6 text-gray-800 dark:text-white/90">
                  {{ item.title }}
                </h3>
                <p v-if="item.summary" class="mt-1 line-clamp-2 text-xs leading-5 text-gray-500 dark:text-gray-400">
                  {{ item.summary }}
                </p>
              </a>
            </div>
          </div>

          <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <div class="mb-4">
              <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Thông báo từ vnstock</h2>
              <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Sự kiện doanh nghiệp và thông báo được cache từ vnstock.</p>
            </div>

            <div v-if="loadingNews" class="py-8 text-sm text-gray-500 dark:text-gray-400">
              Đang tải thông báo...
            </div>
            <div v-else-if="vnstockEvents.length === 0" class="py-8 text-sm text-gray-500 dark:text-gray-400">
              Chưa có thông báo vnstock cho mã này.
            </div>
            <div v-else class="space-y-3">
              <div
                v-for="item in vnstockEvents"
                :key="item.id"
                class="rounded-xl border border-gray-100 p-4 dark:border-gray-800"
              >
                <div class="flex flex-wrap items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <span class="rounded-full bg-amber-50 px-2 py-0.5 font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                    vnstock
                  </span>
                  <span>{{ formatNewsTime(item.date) }}</span>
                </div>
                <h3 class="mt-2 text-sm font-semibold leading-6 text-gray-800 dark:text-white/90">
                  {{ item.title || 'Thông báo doanh nghiệp' }}
                </h3>
                <p v-if="item.description" class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
                  {{ item.description }}
                </p>
              </div>
            </div>
          </div>
        </section>

        <section
          class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]"
        >
          <div class="mb-4 flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Báo cáo tài chính</h2>
              <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Bảng dữ liệu mẫu tối đa 8 dòng, ưu tiên các cột quan trọng.</p>
            </div>
            <div class="inline-flex w-fit items-center gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
              <button
                v-for="type in reportTypes"
                :key="type.value"
                class="rounded-md px-3 py-1.5 text-sm"
                :class="reportTypeButtonClass(type.value)"
                @click="changeReportType(type.value)"
              >
                {{ type.label }}
              </button>
            </div>
          </div>

          <div
            class="mb-4 rounded-2xl border border-brand-100 bg-gradient-to-r from-brand-50 via-white to-blue-50 p-4 dark:border-brand-800/40 dark:from-brand-500/10 dark:via-gray-900 dark:to-blue-900/10"
          >
            <div class="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p class="text-xs font-medium uppercase tracking-wide text-brand-700 dark:text-brand-300">Chế độ hiển thị</p>
                <p class="mt-1 text-sm font-semibold text-gray-800 dark:text-white/90">{{ activeReportTypeLabel }}</p>
              </div>
              <div class="inline-flex items-center rounded-full border border-white/80 bg-white/80 px-3 py-1.5 text-xs font-medium text-gray-700 shadow-sm dark:border-gray-700 dark:bg-gray-800/70 dark:text-gray-300">
                {{ financialPreviewRows.length }} / {{ financialRows.length }} dòng dữ liệu
              </div>
            </div>

            <div v-if="financialHighlights.length > 0" class="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
              <div
                v-for="item in financialHighlights"
                :key="item.label"
                class="rounded-xl border border-white/90 bg-white/85 px-3 py-2 dark:border-gray-700 dark:bg-gray-800/75"
              >
                <p class="text-[11px] uppercase tracking-wide text-gray-500 dark:text-gray-400">{{ item.label }}</p>
                <p class="mt-1 text-sm font-semibold text-gray-800 dark:text-white/90">{{ item.value }}</p>
              </div>
            </div>
          </div>

          <div v-if="loadingFinancials" class="py-6 text-sm text-gray-500 dark:text-gray-400">
            Đang tải báo cáo tài chính...
          </div>

          <div v-else-if="financialPreviewRows.length === 0" class="py-6 text-sm text-gray-500 dark:text-gray-400">
            Chưa có dữ liệu tài chính cho mã này.
          </div>

          <div v-else class="overflow-x-auto">
            <table class="w-full text-left text-sm">
              <thead>
                <tr class="border-b border-gray-200 bg-gray-50/80 dark:border-gray-700 dark:bg-gray-800/40">
                  <th
                    v-for="(column, colIndex) in financialColumns"
                    :key="column"
                    class="px-3 py-2 font-semibold text-gray-600 dark:text-gray-300"
                    :class="colIndex === 0 ? 'sticky left-0 z-10 bg-gray-50/95 dark:bg-gray-800/95' : ''"
                  >
                    {{ formatColumnName(column) }}
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="(row, index) in financialPreviewRows"
                  :key="`row-${index}`"
                  class="border-b border-gray-100 transition-colors hover:bg-brand-50/60 dark:border-gray-800 dark:hover:bg-brand-500/10"
                  :class="index % 2 === 0 ? 'bg-white dark:bg-transparent' : 'bg-gray-50/40 dark:bg-gray-900/25'"
                >
                  <td
                    v-for="(column, colIndex) in financialColumns"
                    :key="`${index}-${column}`"
                    class="px-3 py-2 text-gray-700 dark:text-gray-300"
                    :class="colIndex === 0 ? 'sticky left-0 z-[1] font-semibold bg-inherit' : ''"
                  >
                    <span
                      class="inline-flex rounded-md px-2 py-0.5"
                      :class="cellValueClass(row[column], column, colIndex)"
                    >
                      {{ formatCell(row[column]) }}
                    </span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import PortfolioChart from '@/components/stock/PortfolioChart.vue'
import TechnicalAnalysisChart from '@/components/stock/TechnicalAnalysisChart.vue'
import TradingViewChart from '@/components/stock/TradingViewChart.vue'
import OrderLog from '@/components/stock/OrderLog.vue'
import { VN30_TICKERS, useStockData } from '@/composables/useStockData'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { getMyPortfolio, type PortfolioItem } from '@/services/authApi'
import {
  stockBackendApi,
  type CompanyOverview,
  type MarketEventItem,
  type MarketNewsItem,
  type OrderTick,
} from '@/services/stockBackendApi'

type FinancialType = 'income' | 'balance' | 'cashflow' | 'ratios'
type ChartTimeframeGroup = 'minutes' | 'hours' | 'days'
type ChartTimeframeMode = 'intraday' | 'daily'
type ChartTimeframe = '1min' | '5min' | '15min' | '1h' | '4h' | '1d' | '1m' | '3m' | '6m' | '1y'

type ChartTimeframeOption = {
  label: string
  value: ChartTimeframe
  mode: ChartTimeframeMode
  limit: number
  intervalMinutes?: number
}

type ChartTimeframeGroupOption = {
  label: string
  value: ChartTimeframeGroup
  timeframes: ChartTimeframeOption[]
}

const CHART_TIMEFRAME_GROUPS: ChartTimeframeGroupOption[] = [
  {
    label: 'Phút',
    value: 'minutes',
    timeframes: [
      { label: '1P', value: '1min', mode: 'intraday', intervalMinutes: 1, limit: 360 },
      { label: '5P', value: '5min', mode: 'intraday', intervalMinutes: 5, limit: 120 },
      { label: '15P', value: '15min', mode: 'intraday', intervalMinutes: 15, limit: 96 },
    ],
  },
  {
    label: 'Giờ',
    value: 'hours',
    timeframes: [
      { label: '1G', value: '1h', mode: 'intraday', intervalMinutes: 60, limit: 80 },
      { label: '4G', value: '4h', mode: 'intraday', intervalMinutes: 240, limit: 60 },
    ],
  },
  {
    label: 'Ngày',
    value: 'days',
    timeframes: [
      { label: '1D', value: '1d', mode: 'intraday', intervalMinutes: 1, limit: 360 },
      { label: '1T', value: '1m', mode: 'daily', limit: 30 },
      { label: '3T', value: '3m', mode: 'daily', limit: 90 },
      { label: '6T', value: '6m', mode: 'daily', limit: 180 },
      { label: '1N', value: '1y', mode: 'daily', limit: 365 },
    ],
  },
]

const ORDER_LOG_REFRESH_IN_SESSION_MS = 3000
const ORDER_LOG_REFRESH_OUT_SESSION_MS = 15000

type HistoricalCandle = {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

const route = useRoute()
const router = useRouter()

const {
  stocks,
  fetchInitialData,
  getTechnicalAnalysis,
} = useStockData()

const historySeries = ref<HistoricalCandle[]>([])
const chartTimeframe = ref<ChartTimeframe>('1d')
const activeChartGroup = ref<ChartTimeframeGroup>('days')
const overview = ref<CompanyOverview | null>(null)
const financialRows = ref<Record<string, unknown>[]>([])
const googleNewsItems = ref<MarketNewsItem[]>([])
const vnstockEvents = ref<MarketEventItem[]>([])
const portfolioItems = ref<PortfolioItem[]>([])
const orderTicks = ref<OrderTick[]>([])
const orderTicksCount = ref(0)
const orderIsInSession = ref(false)
const loadingOrderLog = ref(false)
const loadingOverview = ref(false)
const loadingFinancials = ref(false)
const loadingNews = ref(false)
const manualRefreshing = ref(false)
const technicalRefreshToken = ref(0)
const activeReportType = ref<FinancialType>('income')
const symbolPicker = ref('FPT')
const priceFlashDirection = ref<'up' | 'down' | null>(null)
const hasSeenFirstPriceForSymbol = ref(false)
let priceFlashTimer: ReturnType<typeof setTimeout> | null = null
let orderLogAutoRefreshTimer: ReturnType<typeof setTimeout> | null = null

const vn30Tickers = VN30_TICKERS

const reportTypes: Array<{ label: string; value: FinancialType }> = [
  { label: 'KQKD', value: 'income' },
  { label: 'Cân đối', value: 'balance' },
  { label: 'Lưu chuyển', value: 'cashflow' },
  { label: 'Chỉ số', value: 'ratios' },
]

const symbol = computed(() => {
  const value = route.params.symbol
  if (Array.isArray(value)) {
    return (value[0] || 'FPT').toUpperCase()
  }
  return String(value || 'FPT').toUpperCase()
})

usePriceSubscription('stock-detail', () => [symbol.value])

const selectedStock = computed(() => stocks[symbol.value] || null)
const hasCurrentPrice = computed(() => Boolean(
  selectedStock.value &&
  selectedStock.value.price > 0 &&
  selectedStock.value.dataStatus !== 'NO_DATA_IN_SNAPSHOT',
))
const currentPriceDisplay = computed(() => (
  hasCurrentPrice.value ? formatPriceWithDecimals(selectedStock.value?.price || 0) : '--'
))
const currentChangeDisplay = computed(() => {
  if (!hasCurrentPrice.value) return '--'
  const stock = selectedStock.value
  return `${formatSignedChange(stock?.change || 0)} / ${(stock?.changePercent || 0) >= 0 ? '+' : ''}${(stock?.changePercent || 0).toFixed(2)}%`
})
const tradingViewTheme = computed<'light' | 'dark'>(() => (
  document.documentElement.classList.contains('dark') ? 'dark' : 'light'
))

const displayName = computed(() => {
  if (selectedStock.value?.companyName) return selectedStock.value.companyName

  const nameKeys = ['company_name', 'companyName', 'name', 'company', 'short_name']
  for (const key of nameKeys) {
    const value = overview.value?.[key]
    if (typeof value === 'string' && value.trim()) {
      return value
    }
  }

  return symbol.value
})

const chartHistory = computed(() => historySeries.value.map((item) => ({
  time: item.time,
  close: item.close,
})))

const hasPortfolioPositionForSymbol = computed(() =>
  portfolioItems.value.some((item) => item.symbol === symbol.value && item.quantity > 0),
)

const activeChartGroupConfig = computed(() => (
  CHART_TIMEFRAME_GROUPS.find((group) => group.value === activeChartGroup.value) || CHART_TIMEFRAME_GROUPS[2]
))

const activeChartTimeframes = computed(() => activeChartGroupConfig.value.timeframes)

const selectedChartTimeframe = computed(() => {
  for (const group of CHART_TIMEFRAME_GROUPS) {
    const found = group.timeframes.find((item) => item.value === chartTimeframe.value)
    if (found) return found
  }

  return CHART_TIMEFRAME_GROUPS[2].timeframes[0]
})

const stockDetailChartKind = computed<'candlestick' | 'line'>(() => (
  activeChartGroup.value === 'minutes' ? 'line' : 'candlestick'
))

const valuationCards = computed(() => [
  { label: 'P/E', value: formatMetric(readNumber(overview.value, ['pe', 'p_e', 'pe_ratio', 'pe_ttm'])) },
  { label: 'P/B', value: formatMetric(readNumber(overview.value, ['pb', 'p_b', 'pb_ratio', 'pb_ttm'])) },
  { label: 'EPS', value: formatMetric(readNumber(overview.value, ['eps', 'eps_ttm'])) },
  { label: 'ROE', value: formatPercent(readNumber(overview.value, ['roe', 'roe_ttm'])) },
  { label: 'ROA', value: formatPercent(readNumber(overview.value, ['roa', 'roa_ttm'])) },
  { label: 'Market Cap', value: formatLargeValue(readNumber(overview.value, ['market_cap', 'marketCap', 'marketCapitalization'])) },
])

const activeReportTypeLabel = computed(() => {
  const found = reportTypes.find((item) => item.value === activeReportType.value)
  return found?.label || 'Báo cáo'
})

const financialColumns = computed(() => {
  const first = financialRows.value[0]
  return first ? Object.keys(first).slice(0, 6) : []
})

const financialPreviewRows = computed(() => financialRows.value.slice(0, 8))

const financialHighlights = computed(() => {
  const first = financialRows.value[0]
  if (!first) return [] as Array<{ label: string; value: string }>

  const ignored = ['symbol', 'ticker', 'ma', 'year', 'quarter', 'period', 'report_type', 'date', 'time']

  return Object.entries(first)
    .filter(([key, value]) => !ignored.includes(String(key).toLowerCase()) && typeof value === 'number')
    .slice(0, 4)
    .map(([key, value]) => ({
      label: formatColumnName(key),
      value: formatCell(value),
    }))
})

function toNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.replace(/,/g, ''))
    if (Number.isFinite(parsed)) return parsed
  }
  return null
}

function readNumber(source: CompanyOverview | null, keys: string[]): number | null {
  if (!source) return null

  for (const key of keys) {
    const value = toNumber(source[key])
    if (value !== null) return value
  }

  return null
}

function formatMetric(value: number | null): string {
  if (value === null) return '-'
  return value.toFixed(2)
}

function formatPercent(value: number | null): string {
  if (value === null) return '-'
  return `${value.toFixed(2)}%`
}

function formatLargeValue(value: number | null): string {
  if (value === null) return '-'
  if (value >= 1_000_000_000_000) {
    return `${(value / 1_000_000_000_000).toFixed(2)}T`
  }
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toFixed(2)}B`
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`
  }
  return new Intl.NumberFormat('vi-VN').format(value)
}

function formatPriceWithDecimals(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatSignedChange(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value)}`
}

function formatColumnName(value: string): string {
  return value
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/^./, (letter) => letter.toUpperCase())
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'number') {
    const absolute = Math.abs(value)
    if (absolute >= 1_000_000_000_000) {
      return `${(value / 1_000_000_000_000).toFixed(2)} T`
    }
    if (absolute >= 1_000_000_000) {
      return `${(value / 1_000_000_000).toFixed(2)} B`
    }
    if (absolute >= 1_000_000) {
      return `${(value / 1_000_000).toFixed(2)} M`
    }
    if (absolute >= 1000) {
      return new Intl.NumberFormat('vi-VN').format(value)
    }
    return value.toFixed(2)
  }
  return String(value)
}

function formatNewsTime(value: string | null | undefined): string {
  if (!value) return '-'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
  }).format(parsed)
}

function reportTypeButtonClass(type: FinancialType): string {
  const isActive = activeReportType.value === type
  if (!isActive) {
    return 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
  }

  if (type === 'income') {
    return 'bg-emerald-100 text-emerald-800 shadow-theme-xs dark:bg-emerald-500/20 dark:text-emerald-300'
  }
  if (type === 'balance') {
    return 'bg-sky-100 text-sky-800 shadow-theme-xs dark:bg-sky-500/20 dark:text-sky-300'
  }
  if (type === 'cashflow') {
    return 'bg-amber-100 text-amber-800 shadow-theme-xs dark:bg-amber-500/20 dark:text-amber-300'
  }
  return 'bg-violet-100 text-violet-800 shadow-theme-xs dark:bg-violet-500/20 dark:text-violet-300'
}

function chartGroupButtonClass(group: ChartTimeframeGroup): string {
  if (activeChartGroup.value === group) {
    return 'bg-white text-brand-700 shadow-theme-xs dark:bg-gray-900 dark:text-brand-300'
  }

  return 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
}

function chartTimeframeButtonClass(timeframe: ChartTimeframe): string {
  if (chartTimeframe.value === timeframe) {
    return 'bg-brand-500 text-white'
  }

  return 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-400 dark:hover:bg-gray-700'
}

function selectChartGroup(group: ChartTimeframeGroup): void {
  activeChartGroup.value = group
  const firstTimeframe = activeChartGroupConfig.value.timeframes[0]
  if (firstTimeframe) {
    chartTimeframe.value = firstTimeframe.value
  }
}

function selectChartTimeframe(timeframe: ChartTimeframe): void {
  chartTimeframe.value = timeframe
}

function cellValueClass(value: unknown, column: string, columnIndex: number): string {
  if (columnIndex === 0) {
    return 'bg-brand-50 text-brand-700 dark:bg-brand-500/15 dark:text-brand-300'
  }

  if (typeof value !== 'number') {
    return 'text-gray-700 dark:text-gray-300'
  }

  const key = column.toLowerCase()
  const neutralKeys = ['year', 'quarter', 'period', 'date', 'time']
  if (neutralKeys.some((item) => key.includes(item))) {
    return 'text-gray-700 dark:text-gray-300'
  }

  if (value > 0) {
    return 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300'
  }
  if (value < 0) {
    return 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-300'
  }
  return 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
}

async function loadOverview(forceRefresh: boolean = false): Promise<void> {
  loadingOverview.value = true

  try {
    overview.value = await stockBackendApi.getCompanyOverview(symbol.value, forceRefresh)
  } catch {
    overview.value = null
  } finally {
    loadingOverview.value = false
  }
}

async function loadFinancials(forceRefresh: boolean = false): Promise<void> {
  loadingFinancials.value = true

  try {
    const response = await stockBackendApi.getFinancials(symbol.value, activeReportType.value, forceRefresh)
    financialRows.value = response.data
  } catch {
    financialRows.value = []
  } finally {
    loadingFinancials.value = false
  }
}

async function loadNewsAndEvents(forceRefresh: boolean = false): Promise<void> {
  loadingNews.value = true

  try {
    const [googleNewsResult, eventsResult] = await Promise.allSettled([
      stockBackendApi.getGoogleNews([symbol.value], 8),
      stockBackendApi.getMarketEvents([symbol.value], 8, forceRefresh),
    ])

    googleNewsItems.value = googleNewsResult.status === 'fulfilled' ? googleNewsResult.value.data : []
    vnstockEvents.value = eventsResult.status === 'fulfilled' ? eventsResult.value.data : []
  } finally {
    loadingNews.value = false
  }
}

async function loadPortfolio(): Promise<void> {
  try {
    const response = await getMyPortfolio()
    portfolioItems.value = response.items
  } catch {
    portfolioItems.value = []
  }
}

async function loadDailyHistory(
  forceRefresh: boolean = false,
  limitOverride?: number,
): Promise<boolean> {
  const limit = limitOverride ?? selectedChartTimeframe.value.limit

  try {
    const response = await stockBackendApi.getHistory(symbol.value, undefined, undefined, limit, forceRefresh)
    if (response.data.length === 0) {
      return false
    }

    historySeries.value = response.data.map((item) => ({
      time: item.time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
    }))
    syncPriceCardFromHistory(historySeries.value)
    return true
  } catch {
    return false
  }
}

async function loadIntradayHistory(forceRefresh: boolean = false): Promise<boolean> {
  const timeframe = selectedChartTimeframe.value

  try {
    const response = await stockBackendApi.getIntraday(
      symbol.value,
      timeframe.limit,
      forceRefresh,
      forceRefresh,
      timeframe.intervalMinutes || 1,
    )

    if (response.data.length === 0) {
      return false
    }

    historySeries.value = response.data.map((item) => ({
      time: item.time,
      open: item.open,
      high: item.high,
      low: item.low,
      close: item.close,
      volume: item.volume,
    }))
    syncPriceCardFromHistory(historySeries.value)
    return true
  } catch {
    return false
  }
}

async function loadOrderLog(forceRefresh: boolean = false): Promise<void> {
  loadingOrderLog.value = true
  try {
    const response = await stockBackendApi.getOrderLog(symbol.value, 100, forceRefresh, forceRefresh)
    const sortedTicks = [...response.ticks].sort((a, b) => parseTickTimestamp(b.time) - parseTickTimestamp(a.time))

    orderTicks.value = sortedTicks
    orderTicksCount.value = response.count
    orderIsInSession.value = response.is_in_session
    syncPriceCardFromLatestTick(sortedTicks)
  } catch {
    orderTicks.value = []
  } finally {
    loadingOrderLog.value = false
  }
}

function stopPriceFlash(): void {
  if (priceFlashTimer) {
    clearTimeout(priceFlashTimer)
    priceFlashTimer = null
  }

  priceFlashDirection.value = null
}

async function triggerPriceFlash(direction: 'up' | 'down'): Promise<void> {
  if (priceFlashTimer) {
    clearTimeout(priceFlashTimer)
    priceFlashTimer = null
  }

  priceFlashDirection.value = null
  await nextTick()
  priceFlashDirection.value = direction

  priceFlashTimer = setTimeout(() => {
    priceFlashDirection.value = null
    priceFlashTimer = null
  }, 520)
}

function parseTickTimestamp(isoTime: string): number {
  const parsed = new Date(isoTime).getTime()
  return Number.isFinite(parsed) ? parsed : 0
}

function currentSnapshotHasUsablePrice(): boolean {
  const current = stocks[symbol.value]
  return Boolean(current && current.price > 0 && current.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}

function syncPriceCardFromHistory(candles: HistoricalCandle[]): void {
  if (currentSnapshotHasUsablePrice()) {
    return
  }

  const latest = candles[candles.length - 1]
  if (!latest || !Number.isFinite(latest.close) || latest.close <= 0) {
    return
  }

  const symbolKey = symbol.value
  const current = stocks[symbolKey]
  const previous = candles.length > 1 ? candles[candles.length - 2] : latest
  const refPrice = Number.isFinite(previous.close) && previous.close > 0
    ? previous.close
    : (Number.isFinite(latest.open) && latest.open > 0 ? latest.open : latest.close)
  const change = latest.close - refPrice
  const changePercent = refPrice > 0 ? (change / refPrice) * 100 : 0

  stocks[symbolKey] = {
    ...(current || {
      symbol: symbolKey,
      companyName: symbolKey,
      logoColor: '#465FFF',
      syncedAt: null,
    }),
    symbol: symbolKey,
    companyName: current?.companyName || displayName.value || symbolKey,
    price: latest.close,
    change,
    changePercent,
    volume: latest.volume,
    high: latest.high,
    low: latest.low,
    open: latest.open,
    refPrice,
    lastUpdate: latest.time,
    syncedAt: latest.time,
    priceSource: 'eod_snapshot',
    dataStatus: 'DATA_AVAILABLE',
    logoColor: current?.logoColor || '#465FFF',
  }
}

function syncPriceCardFromLatestTick(ticks: OrderTick[]): void {
  const latestTick = ticks[0]
  const symbolKey = symbol.value
  const current = stocks[symbolKey]

  if (!latestTick || !current) {
    return
  }

  const latestTickTs = parseTickTimestamp(latestTick.time)
  const currentTs = parseTickTimestamp(current.lastUpdate)
  const hasNewerTick = latestTickTs > currentTs
  const priceChanged = Math.abs(current.price - latestTick.price) > 1e-6

  if (!hasNewerTick && !priceChanged) {
    return
  }

  const fallbackRefPrice = (current.price - current.change) || latestTick.price
  const refPrice = current.refPrice > 0 ? current.refPrice : fallbackRefPrice
  const change = latestTick.price - refPrice
  const changePercent = refPrice > 0 ? (change / refPrice) * 100 : current.changePercent

  stocks[symbolKey] = {
    ...current,
    price: latestTick.price,
    change,
    changePercent,
    lastUpdate: latestTick.time,
    priceSource: 'dnse_live',
    dataStatus: 'DATA_AVAILABLE',
  }
}

function stopOrderLogAutoRefresh(): void {
  if (!orderLogAutoRefreshTimer) {
    return
  }

  clearTimeout(orderLogAutoRefreshTimer)
  orderLogAutoRefreshTimer = null
}

function scheduleOrderLogAutoRefresh(): void {
  stopOrderLogAutoRefresh()

  const refreshDelayMs = orderIsInSession.value
    ? ORDER_LOG_REFRESH_IN_SESSION_MS
    : ORDER_LOG_REFRESH_OUT_SESSION_MS

  orderLogAutoRefreshTimer = setTimeout(async () => {
    await loadOrderLog()
    scheduleOrderLogAutoRefresh()
  }, refreshDelayMs)
}

async function loadHistory(forceRefresh: boolean = false): Promise<void> {
  const timeframe = selectedChartTimeframe.value

  if (timeframe.mode === 'intraday') {
    const intradayLoaded = await loadIntradayHistory(forceRefresh)
    if (intradayLoaded) {
      return
    }

    if (timeframe.value === '1d') {
      const fallbackLoaded = await loadDailyHistory(forceRefresh, 3)
      if (fallbackLoaded) {
        return
      }
    }

    historySeries.value = []
    return
  }

  const dailyLoaded = await loadDailyHistory(forceRefresh)
  if (!dailyLoaded) {
    historySeries.value = []
  }
}

async function reloadSymbolData(forceRefresh: boolean = false): Promise<void> {
  await Promise.all([
    loadOverview(forceRefresh),
    loadFinancials(forceRefresh),
    loadHistory(forceRefresh),
    loadOrderLog(forceRefresh),
    loadNewsAndEvents(forceRefresh),
  ])
}

function changeReportType(nextType: FinancialType): void {
  activeReportType.value = nextType
  void loadFinancials()
}

function onSymbolPickerChange(): void {
  const nextSymbol = symbolPicker.value.toUpperCase()
  if (nextSymbol === symbol.value) {
    return
  }

  void router.push(`/stocks/${nextSymbol}`)
}

async function onRefreshClick(): Promise<void> {
  if (manualRefreshing.value) {
    return
  }

  manualRefreshing.value = true
  try {
    await reloadSymbolData(true)
    technicalRefreshToken.value += 1
  } finally {
    manualRefreshing.value = false
  }
}

watch(symbol, (nextSymbol) => {
  symbolPicker.value = nextSymbol
  hasSeenFirstPriceForSymbol.value = false
  stopPriceFlash()
}, { immediate: true })

watch(
  () => selectedStock.value?.price ?? null,
  (nextPrice, prevPrice) => {
    if (nextPrice === null || !Number.isFinite(nextPrice) || nextPrice <= 0) {
      return
    }

    if (!hasSeenFirstPriceForSymbol.value) {
      hasSeenFirstPriceForSymbol.value = true
      return
    }

    if (prevPrice === null || !Number.isFinite(prevPrice)) {
      return
    }

    const delta = nextPrice - prevPrice
    if (Math.abs(delta) < 1e-6) {
      return
    }

    void triggerPriceFlash(delta > 0 ? 'up' : 'down')
  },
)

watch(symbol, () => {
  void reloadSymbolData()
})

watch(chartTimeframe, () => {
  void loadHistory()
})

onMounted(async () => {
  await Promise.all([fetchInitialData(), loadPortfolio()])
  await reloadSymbolData()
  scheduleOrderLogAutoRefresh()

})

onUnmounted(() => {
  stopPriceFlash()
  stopOrderLogAutoRefresh()
})
</script>

<style scoped>
.price-flash-up {
  animation: priceFlashUp 520ms ease-out;
}

.price-flash-down {
  animation: priceFlashDown 520ms ease-out;
}

@keyframes priceFlashUp {
  0% {
    box-shadow: 0 0 0 0 rgba(34, 197, 94, 0.45), inset 0 0 0 999px rgba(34, 197, 94, 0.25);
  }

  100% {
    box-shadow: 0 0 0 12px rgba(34, 197, 94, 0), inset 0 0 0 999px rgba(34, 197, 94, 0);
  }
}

@keyframes priceFlashDown {
  0% {
    box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.45), inset 0 0 0 999px rgba(239, 68, 68, 0.25);
  }

  100% {
    box-shadow: 0 0 0 12px rgba(239, 68, 68, 0), inset 0 0 0 999px rgba(239, 68, 68, 0);
  }
}
</style>
