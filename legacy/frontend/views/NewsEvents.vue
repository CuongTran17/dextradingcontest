<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Tin tức và sự kiện</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Theo dõi tin Google News, thông báo doanh nghiệp từ vnstock và lọc nhanh theo mã, nhóm ngành hoặc tin nóng.
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Tin đang hiển thị</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ filteredNews.length }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Tin nóng</p>
          <p class="mt-2 text-2xl font-semibold text-error-600 dark:text-error-400">{{ hotNewsCount }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Thông báo vnstock</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ filteredEvents.length }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Bộ lọc</p>
          <p class="mt-2 text-sm font-semibold text-gray-800 dark:text-white/90">{{ activeFilterLabel }}</p>
        </div>
      </div>

      <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="grid gap-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-end">
          <div class="grid gap-4 md:grid-cols-3">
            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
              Mã cổ phiếu
              <select
                v-model="selectedSymbol"
                class="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
              >
                <option value="all">Tất cả VN30</option>
                <option v-for="symbol in VN30_TICKERS" :key="symbol" :value="symbol">{{ symbol }}</option>
              </select>
            </label>

            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
              Nhóm ngành
              <select
                v-model="selectedSector"
                class="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
                :disabled="selectedSymbol !== 'all'"
              >
                <option value="all">Tất cả ngành</option>
                <option v-for="sector in sectors" :key="sector.name" :value="sector.name">{{ sector.name }}</option>
              </select>
            </label>

            <label class="text-sm font-medium text-gray-700 dark:text-gray-300">
              Loại tin
              <select
                v-model="selectedNewsMode"
                class="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-200"
              >
                <option value="all">Tất cả tin</option>
                <option value="hot">Tin nóng</option>
                <option value="normal">Tin thường</option>
              </select>
            </label>
          </div>

          <div class="flex flex-wrap gap-2">
            <button
              v-for="option in impactOptions"
              :key="option"
              class="rounded-lg px-3 py-2 text-sm font-medium transition"
              :class="
                selectedImpact === option
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700'
              "
              @click="selectedImpact = option"
            >
              {{ impactLabel(option) }}
            </button>
            <button
              class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              :disabled="loading"
              @click="loadNewsAndEvents(true)"
            >
              {{ loading ? 'Đang tải...' : 'Làm mới' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="error" class="rounded-2xl border border-error-200 bg-error-50 px-5 py-4 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300">
        {{ error }}
      </div>

      <div class="grid grid-cols-12 gap-4 md:gap-6">
        <section class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] xl:col-span-8">
          <div class="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Tin tức</h2>
              <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Nguồn Google News từ dữ liệu ETL mới nhất.</p>
            </div>
            <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-300">
              {{ newsSourceLabel }}
            </span>
          </div>

          <div v-if="loading" class="flex items-center justify-center py-16">
            <div class="h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
          </div>

          <ul v-else-if="filteredNews.length > 0" class="space-y-3">
            <li
              v-for="item in filteredNews"
              :key="item.id"
              class="rounded-xl border border-gray-100 p-4 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/5"
            >
              <div class="flex flex-wrap items-center gap-2">
                <span class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium" :class="impactClass(item.impact)">
                  {{ impactLabel(item.impact) }}
                </span>
                <span v-if="item.isHot" class="rounded-full bg-error-50 px-2 py-0.5 text-xs font-semibold text-error-700 dark:bg-error-500/15 dark:text-error-300">
                  Tin nóng
                </span>
                <span class="text-xs text-gray-500 dark:text-gray-400">{{ item.source }} · {{ item.time }}</span>
              </div>

              <a
                :href="item.url || undefined"
                target="_blank"
                rel="noopener noreferrer"
                class="mt-2 block font-medium text-gray-800 hover:text-brand-600 dark:text-white/90 dark:hover:text-brand-300"
              >
                {{ item.title }}
              </a>
              <p v-if="item.summary" class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ item.summary }}</p>

              <div class="mt-3 flex flex-wrap gap-2">
                <button
                  v-for="symbol in item.symbols"
                  :key="`${item.id}-${symbol}`"
                  class="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                  @click="goToStock(symbol)"
                >
                  {{ symbol }}
                </button>
                <span class="rounded-full bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 dark:bg-sky-500/15 dark:text-sky-300">
                  {{ sectorForSymbols(item.symbols) }}
                </span>
              </div>
            </li>
          </ul>

          <div v-else class="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
            Không có tin phù hợp với bộ lọc hiện tại.
          </div>
        </section>

        <section class="col-span-12 space-y-4 xl:col-span-4">
          <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Mã biến động mạnh</h2>
            <ul v-if="topMovers.length" class="space-y-2">
              <li
                v-for="stock in topMovers"
                :key="stock.symbol"
                class="flex items-center justify-between rounded-lg bg-gray-50 px-3 py-2 dark:bg-white/5"
              >
                <button class="font-medium text-gray-800 dark:text-white/90" @click="goToStock(stock.symbol)">
                  {{ stock.symbol }}
                </button>
                <span class="text-sm font-medium" :class="stock.changePercent >= 0 ? 'text-success-600' : 'text-error-600'">
                  {{ stock.changePercent >= 0 ? '+' : '' }}{{ stock.changePercent.toFixed(2) }}%
                </span>
              </li>
            </ul>
            <div v-else class="rounded-xl border border-dashed border-gray-200 px-3 py-6 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
              Chưa có dữ liệu biến động.
            </div>
          </div>

          <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Thông báo từ vnstock</h2>
            <ul v-if="filteredEvents.length > 0" class="space-y-3">
              <li
                v-for="event in filteredEvents"
                :key="event.id"
                class="rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-800"
              >
                <p class="text-xs text-gray-500 dark:text-gray-400">{{ formatEventDate(event.date) }}</p>
                <p class="mt-1 font-medium text-gray-800 dark:text-white/90">{{ event.title }}</p>
                <p v-if="event.description" class="mt-1 text-sm text-gray-500 dark:text-gray-400">{{ event.description }}</p>
                <div class="mt-2 flex flex-wrap gap-2">
                  <button
                    class="rounded-full bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700 dark:bg-gray-800 dark:text-gray-300"
                    @click="goToStock(event.symbol)"
                  >
                    {{ event.symbol }}
                  </button>
                  <span class="rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 dark:bg-amber-500/15 dark:text-amber-300">
                    vnstock
                  </span>
                </div>
              </li>
            </ul>

            <div v-else class="rounded-xl border border-dashed border-gray-200 px-3 py-6 text-sm text-gray-500 dark:border-gray-700 dark:text-gray-400">
              Không có thông báo phù hợp với bộ lọc hiện tại.
            </div>
          </div>
        </section>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { useStockData, VN30_TICKERS } from '@/composables/useStockData'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { stockBackendApi } from '@/services/stockBackendApi'
import { MARKET_SECTORS, sectorForSymbol, type SectorDefinition } from '@/constants/marketSectors'

type ImpactLevel = 'High' | 'Medium' | 'Low'
type NewsMode = 'all' | 'hot' | 'normal'

interface NewsItem {
  id: string
  source: string
  time: string
  rawTime: string
  impact: ImpactLevel
  title: string
  summary: string
  symbols: string[]
  url: string
  isHot: boolean
}

interface EventItem {
  id: string
  date: string
  title: string
  description: string
  symbol: string
}

const sectors: SectorDefinition[] = MARKET_SECTORS

const hotKeywords = [
  'lãi',
  'lỗ',
  'tăng',
  'giảm',
  'cổ tức',
  'phát hành',
  'mua lại',
  'thoái vốn',
  'sáp nhập',
  'đầu tư',
  'thắng thầu',
  'kỷ luật',
  'khởi tố',
  'thanh tra',
]

const router = useRouter()
const { stocks, fetchInitialData } = useStockData()
usePriceSubscription('news-events-prices', () => VN30_TICKERS)

const impactOptions = ['All', 'High', 'Medium', 'Low'] as const
const selectedImpact = ref<(typeof impactOptions)[number]>('All')
const selectedSymbol = ref<string>('all')
const selectedSector = ref<string>('all')
const selectedNewsMode = ref<NewsMode>('all')
const newsFeed = ref<NewsItem[]>([])
const events = ref<EventItem[]>([])
const loading = ref(false)
const error = ref('')
const newsSourceLabel = ref('Google News')

const selectedSectorSymbols = computed(() => {
  if (selectedSymbol.value !== 'all') return [selectedSymbol.value]
  if (selectedSector.value === 'all') return [...VN30_TICKERS]
  return sectors.find((sector) => sector.name === selectedSector.value)?.symbols || []
})

const topMovers = computed(() =>
  Object.values(stocks)
    .filter((stock) => hasUsableSnapshotPrice(stock))
    .sort((a, b) => Math.abs(b.changePercent) - Math.abs(a.changePercent))
    .slice(0, 6),
)

const hotMoverSymbols = computed(() =>
  new Set(topMovers.value.filter((stock) => Math.abs(stock.changePercent) >= 2).map((stock) => stock.symbol)),
)

const filteredNews = computed(() => {
  const allowed = new Set(selectedSectorSymbols.value)
  return newsFeed.value.filter((item) => {
    const matchesSymbol = item.symbols.some((symbol) => allowed.has(symbol))
    const matchesImpact = selectedImpact.value === 'All' || item.impact === selectedImpact.value
    const matchesMode =
      selectedNewsMode.value === 'all' ||
      (selectedNewsMode.value === 'hot' && item.isHot) ||
      (selectedNewsMode.value === 'normal' && !item.isHot)

    return matchesSymbol && matchesImpact && matchesMode
  })
})

const filteredEvents = computed(() => {
  const allowed = new Set(selectedSectorSymbols.value)
  return events.value.filter((event) => allowed.has(event.symbol))
})

const hotNewsCount = computed(() => filteredNews.value.filter((item) => item.isHot).length)

const activeFilterLabel = computed(() => {
  const parts = [
    selectedSymbol.value === 'all' ? selectedSector.value : selectedSymbol.value,
    selectedNewsMode.value === 'hot' ? 'Tin nóng' : selectedNewsMode.value === 'normal' ? 'Tin thường' : 'Tất cả tin',
    impactLabel(selectedImpact.value),
  ]
  return parts.join(' · ')
})

function normalizeImpact(value: string | undefined, title: string, symbols: string[]): ImpactLevel {
  const normalized = String(value || '').toLowerCase()
  if (normalized === 'high') return 'High'
  if (normalized === 'medium') return 'Medium'
  if (isHotNews(title, symbols)) return 'High'
  return 'Low'
}

function isHotNews(title: string, symbols: string[]): boolean {
  const lowerTitle = title.toLowerCase()
  return hotKeywords.some((keyword) => lowerTitle.includes(keyword)) || symbols.some((symbol) => hotMoverSymbols.value.has(symbol))
}

function normalizeSymbols(rawSymbols: string[], fallback: string): string[] {
  const symbols = rawSymbols.length ? rawSymbols : [fallback]
  return symbols.map((symbol) => symbol.toUpperCase()).filter((symbol) => VN30_TICKERS.includes(symbol))
}

function formatNewsTime(value: string): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatEventDate(value: string): string {
  if (!value) return '--'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString('vi-VN')
}

async function loadNewsAndEvents(forceRefresh: boolean = false): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    const symbols = selectedSymbol.value !== 'all'
      ? [selectedSymbol.value]
      : selectedSector.value !== 'all'
        ? selectedSectorSymbols.value
        : [...VN30_TICKERS]

    const [newsResult, eventsResult] = await Promise.allSettled([
      stockBackendApi.getGoogleNews(symbols, 120),
      stockBackendApi.getMarketEvents(symbols, 80, forceRefresh),
    ])

    if (newsResult.status === 'fulfilled') {
      newsSourceLabel.value = newsResult.value.source || 'Google News'
      newsFeed.value = newsResult.value.data.map((item, index) => {
        const symbolsForItem = normalizeSymbols(item.symbols || [], item.symbol)
        const title = item.title || 'Tin tức thị trường'
        const hot = isHotNews(title, symbolsForItem)
        return {
          id: item.id || `${item.symbol}-${index}`,
          source: item.source || 'Google News',
          time: formatNewsTime(item.publish_time || item.time),
          rawTime: item.publish_time || item.time,
          impact: normalizeImpact(item.impact, title, symbolsForItem),
          title,
          summary: item.summary || '',
          symbols: symbolsForItem.length ? symbolsForItem : [item.symbol],
          url: item.url || '',
          isHot: hot,
        }
      })
    } else {
      newsFeed.value = []
      error.value = newsResult.reason instanceof Error ? newsResult.reason.message : 'Không tải được tin tức Google News.'
    }

    if (eventsResult.status === 'fulfilled') {
      events.value = eventsResult.value.data.map((item, index) => ({
        id: item.id || `${item.symbol}-event-${index}`,
        date: item.date || '',
        title: item.title || 'Thông báo doanh nghiệp',
        description: item.description || '',
        symbol: (item.symbol || 'VN30').toUpperCase(),
      }))
    } else if (!error.value) {
      events.value = []
      error.value = eventsResult.reason instanceof Error ? eventsResult.reason.message : 'Không tải được thông báo vnstock.'
    }
  } finally {
    loading.value = false
  }
}

function impactLabel(impact: (typeof impactOptions)[number]): string {
  if (impact === 'All') return 'Tất cả'
  if (impact === 'High') return 'Cao'
  if (impact === 'Medium') return 'Trung bình'
  return 'Thấp'
}

function impactClass(impact: ImpactLevel): string {
  if (impact === 'High') return 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-400'
  if (impact === 'Medium') return 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-400'
  return 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-400'
}

function sectorForSymbols(symbols: string[]): string {
  const found = symbols.map((symbol) => sectorForSymbol(symbol)).find(Boolean)
  return found?.name || 'VN30'
}

function goToStock(symbol: string): void {
  void router.push(`/stocks/${symbol}`)
}

function hasUsableSnapshotPrice(item: { price?: number; dataStatus?: string } | null | undefined): boolean {
  return Boolean(item && Number(item.price) > 0 && item.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}

watch(selectedSymbol, () => {
  if (selectedSymbol.value !== 'all') {
    selectedSector.value = 'all'
  }
  void loadNewsAndEvents()
})

watch([selectedSector], () => {
  void loadNewsAndEvents()
})

onMounted(async () => {
  await fetchInitialData()
  await loadNewsAndEvents()

})

</script>
