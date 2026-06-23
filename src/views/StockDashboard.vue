<template>
  <admin-layout>
    <div class="grid grid-cols-12 items-start gap-5">
      <div class="col-span-12 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-2xl font-bold text-gray-800 dark:text-white/90">
            Bảng điều khiển thị trường
          </h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Dữ liệu VN30 từ DNSE Lightspeed
          </p>
          <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
            Dữ liệu cập nhật lần cuối: {{ formattedLastDataSync }}
          </p>
        </div>
        <div class="flex items-center gap-3">
          <ConnectionStatus
            :connected="isConnected"
            :backend-available="backendAvailable"
            :last-update="lastRefresh"
          />
          <button
            class="rounded-lg border border-gray-200 px-3 py-2 text-sm font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-white/5"
            :disabled="isDashboardRefreshing"
            @click="refreshDashboard"
          >
            {{ isDashboardRefreshing ? 'Đang tải' : 'Làm mới' }}
          </button>
        </div>
      </div>

      <div
        v-if="isLoading"
        class="col-span-12 rounded-lg border border-brand-200 bg-brand-50 px-4 py-3 text-sm text-brand-700 dark:border-brand-800 dark:bg-brand-500/10 dark:text-brand-300"
      >
        Đang tải dữ liệu thị trường mới nhất...
      </div>

      <div
        v-if="error"
        class="col-span-12 rounded-lg border border-warning-200 bg-warning-50 px-4 py-3 text-sm text-warning-700 dark:border-warning-800 dark:bg-warning-500/10 dark:text-warning-300"
      >
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <span>{{ error }}</span>
          <button
            class="w-fit rounded-lg border border-warning-300 px-3 py-1.5 text-xs font-semibold text-warning-700 transition-colors hover:bg-warning-100 dark:border-warning-700 dark:text-warning-300 dark:hover:bg-warning-500/20"
            :disabled="isDashboardRefreshing"
            @click="refreshDashboard"
          >
            Thử lại
          </button>
        </div>
      </div>

      <div
        v-if="dashboardDataError"
        class="col-span-12 rounded-lg border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-800 dark:bg-error-500/10 dark:text-error-300"
      >
        {{ dashboardDataError }}
      </div>

      <div class="col-span-12 rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">
            Cổ phiếu tiêu biểu VN30
          </h2>
          <div class="inline-flex items-center gap-1 rounded-lg bg-gray-100 p-1 dark:bg-gray-800">
            <button
              class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors"
              :class="
                activeTab === 'gainers'
                  ? 'bg-success-500 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              "
              @click="activeTab = 'gainers'"
            >
              ↑ Top tăng
            </button>
            <button
              class="rounded-md px-4 py-1.5 text-sm font-medium transition-colors"
              :class="
                activeTab === 'losers'
                  ? 'bg-error-500 text-white shadow-sm'
                  : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200'
              "
              @click="activeTab = 'losers'"
            >
              ↓ Top giảm
            </button>
          </div>
        </div>

        <div v-if="snapshotsLoading" class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <div
            v-for="item in 8"
            :key="item"
            class="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-4 dark:border-gray-800 dark:bg-white/[0.03]"
          >
            <div class="flex items-center gap-3">
              <div class="h-12 w-12 animate-pulse rounded-lg bg-gray-200 dark:bg-gray-700"></div>
              <div>
                <div class="h-4 w-14 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
                <div class="mt-2 h-3 w-28 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
              </div>
            </div>
            <div class="text-right">
              <div class="ml-auto h-4 w-20 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
              <div class="ml-auto mt-2 h-3 w-12 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
            </div>
          </div>
        </div>

        <div v-else-if="displayedStocks.length === 0" class="py-6 text-center text-sm text-gray-500 dark:text-gray-400">
          Không có dữ liệu. Hãy thử làm mới lại sau.
        </div>

        <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          <button
            v-for="stock in displayedStocks"
            :key="stock.symbol"
            class="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50 px-4 py-4 text-left transition-colors hover:border-brand-200 hover:bg-white dark:border-gray-800 dark:bg-white/[0.03] dark:hover:border-brand-500/40 dark:hover:bg-white/[0.05]"
            @click="navigateToStock(stock.symbol)"
          >
            <div class="flex min-w-0 items-center gap-3">
              <div
                class="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-lg text-base font-bold text-white"
                :style="{ backgroundColor: symbolColor(stock.symbol) }"
              >
                {{ stock.symbol.charAt(0) }}
              </div>
              <div class="min-w-0">
                <p class="text-base font-semibold text-gray-800 dark:text-white/90">{{ stock.symbol }}</p>
                <p class="max-w-[150px] truncate text-sm text-gray-500 dark:text-gray-400">{{ stock.companyName || stock.symbol }}</p>
              </div>
            </div>
            <div class="ml-3 shrink-0 text-right">
              <p class="text-base font-semibold text-gray-800 dark:text-white/90">
                {{ formatPrice(stock.price) }}
              </p>
              <p
                class="text-sm font-semibold"
                :class="stock.changePercent >= 0 ? 'text-success-600' : 'text-error-600'"
              >
                {{ stock.changePercent >= 0 ? '+' : '' }}{{ stock.changePercent.toFixed(2) }}%
              </p>
            </div>
          </button>
        </div>
      </div>

      <div class="col-span-12">
        <section class="rounded-xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-lg font-semibold text-gray-800 dark:text-white/90">Chỉ số nhanh</h3>
            <p class="text-xs text-gray-500 dark:text-gray-400">Nhấn để xem chi tiết</p>
          </div>

          <div v-if="dashboardIndicesLoading" class="grid gap-4 sm:grid-cols-2">
            <div
              v-for="item in 2"
              :key="item"
              class="rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/40"
            >
              <div class="h-3 w-20 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
              <div class="mt-3 h-7 w-28 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
              <div class="mt-3 h-4 w-14 animate-pulse rounded bg-gray-200 dark:bg-gray-700"></div>
            </div>
          </div>

          <div v-else class="grid gap-4 sm:grid-cols-2">
            <button
              v-for="item in dashboardIndexCards"
              :key="item.symbol"
              class="w-full rounded-lg border border-gray-200 bg-gray-50 p-4 text-left transition-colors hover:border-brand-300 hover:bg-white dark:border-gray-700 dark:bg-gray-800/40 dark:hover:bg-white/[0.05]"
              @click="goToMarketOverview(item.symbol)"
            >
              <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{{ item.name }}</p>
              <p class="mt-1 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ formatIndex(item.price) }}</p>
              <p class="mt-1 text-sm font-semibold" :class="item.changePercent >= 0 ? 'text-success-600' : 'text-error-600'">
                {{ item.changePercent >= 0 ? '+' : '' }}{{ item.changePercent.toFixed(2) }}%
              </p>
            </button>

            <div v-if="dashboardIndexCards.length === 0" class="rounded-lg border border-dashed border-gray-200 px-4 py-8 text-center text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
              Chưa có dữ liệu chỉ số từ backend.
            </div>
          </div>
        </section>
      </div>

      <div class="col-span-12 xl:col-span-4">
        <StockWatchlist
          :stocks="watchlistStocks"
          @select="navigateToStock"
          @add="addToWatchlist"
          @remove="removeFromWatchlist"
          @clear="clearWatchlist"
        />
      </div>

      <div class="col-span-12 xl:col-span-8">
        <MarketOverview :stocks="allStocksArray" @select="navigateToStock" />
      </div>

      <div class="col-span-12">
        <TechnicalAnalysisChart
          symbol="VNINDEX"
          value-unit="điểm"
          y-axis-title="Điểm"
          :fetch-technical="getVnindexTechnicalAnalysis"
        />
      </div>
    </div>
  </admin-layout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import StockWatchlist from '@/components/stock/StockWatchlist.vue'
import MarketOverview from '@/components/stock/MarketOverview.vue'
import ConnectionStatus from '@/components/stock/ConnectionStatus.vue'
import TechnicalAnalysisChart from '@/components/stock/TechnicalAnalysisChart.vue'
import { useStockData, VN30_TICKERS } from '@/composables/useStockData'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { fetchMarketIndexTechnicalAnalysis } from '@/services/marketIndexTechnical'
import { stockBackendApi, type MarketIndexQuote, type StockSnapshot, type TechnicalResponse } from '@/services/stockBackendApi'

const router = useRouter()

const {
  stocks,
  watchlist,
  featuredSymbols,
  watchlistStocks,
  isConnected,
  isLoading,
  error,
  lastRefresh,
  lastDataSyncAt,
  backendAvailable,
  fetchInitialData,
  addToWatchlist,
  removeFromWatchlist,
  clearWatchlist,
} = useStockData()

usePriceSubscription('stock-dashboard', () => [...featuredSymbols.value, ...watchlist.value])

type FilterTab = 'gainers' | 'losers'

const snapshots = ref<StockSnapshot[]>([])
const snapshotsLoading = ref(false)
const activeTab = ref<FilterTab>('gainers')
const dashboardDataError = ref<string | null>(null)

function hasUsableSnapshotPrice(item: { price?: number; dataStatus?: string } | null | undefined): boolean {
  return Boolean(item && Number(item.price) > 0 && item.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}

const topGainers = computed(() =>
  [...snapshots.value]
    .filter((s) => hasUsableSnapshotPrice(s) && s.changePercent >= 0)
    .sort((a, b) => b.changePercent - a.changePercent)
    .slice(0, 12),
)

const topLosers = computed(() =>
  [...snapshots.value]
    .filter((s) => hasUsableSnapshotPrice(s) && s.changePercent < 0)
    .sort((a, b) => a.changePercent - b.changePercent)
    .slice(0, 12),
)

const displayedStocks = computed(() =>
  activeTab.value === 'gainers' ? topGainers.value : topLosers.value,
)

async function loadSnapshots(): Promise<void> {
  snapshotsLoading.value = true
  try {
    const res = await stockBackendApi.getSnapshots(VN30_TICKERS, false)
    snapshots.value = res.data
  } catch {
    snapshots.value = []
    dashboardDataError.value = 'Không tải được nhóm cổ phiếu tăng/giảm từ backend.'
  } finally {
    snapshotsLoading.value = false
  }
}

const dashboardIndicesLoading = ref(false)
const dashboardIndices = ref<MarketIndexQuote[]>([])

const dashboardIndexCards = computed(() => {
  const preferred = ['VNINDEX', 'VN30']
  return preferred
    .map((symbol) => dashboardIndices.value.find((item) => String(item.symbol).toUpperCase() === symbol))
    .filter((item): item is MarketIndexQuote => Boolean(item))
})

async function loadDashboardIndices(): Promise<void> {
  dashboardIndicesLoading.value = true
  try {
    const response = await stockBackendApi.getMarketIndices(undefined, undefined, 8, false)
    dashboardIndices.value = response.data
  } catch {
    dashboardIndices.value = []
    dashboardDataError.value = dashboardDataError.value
      ? `${dashboardDataError.value} Không tải được chỉ số nhanh.`
      : 'Không tải được chỉ số nhanh từ backend.'
  } finally {
    dashboardIndicesLoading.value = false
  }
}

async function getVnindexTechnicalAnalysis(_symbol: string, limit: number): Promise<TechnicalResponse | null> {
  return fetchMarketIndexTechnicalAnalysis('VNINDEX', limit, false)
}

const isDashboardRefreshing = computed(() =>
  isLoading.value || snapshotsLoading.value || dashboardIndicesLoading.value,
)

async function refreshDashboard(): Promise<void> {
  dashboardDataError.value = null
  await fetchInitialData()
  await Promise.all([loadSnapshots(), loadDashboardIndices()])
}

function goToMarketOverview(symbol: string): void {
  void router.push({
    path: '/market-overview',
    query: { index: symbol },
  })
}

function navigateToStock(symbol: string): void {
  void router.push({
    name: 'StockDetail',
    params: { symbol: symbol.toUpperCase() },
  })
}

const SYMBOL_COLORS: Record<string, string> = {
  FPT: '#F37021', VNM: '#0072BC', VCB: '#00553E', HPG: '#E31E24',
  MBB: '#1B3C87', TCB: '#E31E24', VIC: '#003366', MSN: '#E31E24',
}
const COLOR_PALETTE = ['#465FFF', '#0EA5E9', '#22C55E', '#F59E0B', '#EF4444', '#06B6D4', '#8B5CF6', '#14B8A6']

function symbolColor(symbol: string): string {
  const s = symbol.toUpperCase()
  if (SYMBOL_COLORS[s]) return SYMBOL_COLORS[s]
  let h = 0
  for (const c of s) h = (h * 31 + c.charCodeAt(0)) >>> 0
  return COLOR_PALETTE[h % COLOR_PALETTE.length]
}

function formatPrice(price: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(price)
}

function formatIndex(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

const allStocksArray = computed(() => {
  return Object.values(stocks).filter((s) => hasUsableSnapshotPrice(s))
})

const formattedLastDataSync = computed(() => {
  if (!lastDataSyncAt.value) {
    return 'Chưa có dữ liệu'
  }

  const dt = new Date(lastDataSyncAt.value)
  if (Number.isNaN(dt.getTime())) {
    return lastDataSyncAt.value
  }

  return dt.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
})

onMounted(async () => {
  await refreshDashboard()
})
</script>
