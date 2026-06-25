<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Lọc cổ phiếu</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Lọc cổ phiếu theo chỉ báo kỹ thuật (RSI, MACD) và chỉ số định giá (P/E, P/B).
        </p>
      </div>

      <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6">
          <label class="space-y-1">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">Mã / Tên</span>
            <input
              v-model="searchKeyword"
              type="text"
              placeholder="FPT, VCB..."
              class="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700"
            />
          </label>

          <label class="space-y-1">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">RSI tối thiểu</span>
            <input
              v-model.number="rsiMin"
              type="number"
              min="0"
              max="100"
              class="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700"
            />
          </label>

          <label class="space-y-1">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">RSI tối đa</span>
            <input
              v-model.number="rsiMax"
              type="number"
              min="0"
              max="100"
              class="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700"
            />
          </label>

          <label class="space-y-1">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">P/E tối đa</span>
            <input
              v-model.number="maxPe"
              type="number"
              min="0"
              class="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700"
            />
          </label>

          <label class="space-y-1">
            <span class="text-xs font-medium text-gray-500 dark:text-gray-400">P/B tối đa</span>
            <input
              v-model.number="maxPb"
              type="number"
              min="0"
              class="h-10 w-full rounded-lg border border-gray-300 bg-transparent px-3 text-sm dark:border-gray-700"
            />
          </label>

          <label class="flex items-end gap-2 pb-1">
            <input v-model="bullishMacdOnly" type="checkbox" class="h-4 w-4 rounded border-gray-300" />
            <span class="text-sm text-gray-700 dark:text-gray-300">Chỉ lấy MACD tăng</span>
          </label>
        </div>

        <div class="mt-4 flex flex-wrap gap-2">
          <button
            class="rounded-lg bg-brand-500 px-3 py-2 text-sm font-medium text-white hover:bg-brand-600"
            @click="loadScreenerData"
          >
            Quét lại
          </button>
          <button
            class="rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium text-gray-700 dark:border-gray-700 dark:text-gray-300"
            @click="resetFilters"
          >
            Đặt lại bộ lọc
          </button>
        </div>
      </section>

      <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="mb-3 flex items-center justify-between">
          <h2 class="text-lg font-semibold text-gray-800 dark:text-white/90">Kết quả</h2>
          <p class="text-xs text-gray-500 dark:text-gray-400">{{ filteredRows.length }} mã phù hợp</p>
        </div>

        <div v-if="loading" class="py-8 text-sm text-gray-500 dark:text-gray-400">Đang quét dữ liệu thị trường...</div>

        <div v-else-if="filteredRows.length === 0" class="py-8 text-sm text-gray-500 dark:text-gray-400">
          Không có cổ phiếu phù hợp bộ lọc hiện tại.
        </div>

        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('symbol')"
                >
                  Mã
                  <span v-if="sortKey === 'symbol'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('price')"
                >
                  Giá
                  <span v-if="sortKey === 'price'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('changePercent')"
                >
                  Biến động
                  <span v-if="sortKey === 'changePercent'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('rsi')"
                >
                  RSI
                  <span v-if="sortKey === 'rsi'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('macd')"
                >
                  MACD
                  <span v-if="sortKey === 'macd'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('signalSummary')"
                >
                  Tín hiệu
                  <span v-if="sortKey === 'signalSummary'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('pe')"
                >
                  P/E
                  <span v-if="sortKey === 'pe'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
                <th
                  class="cursor-pointer select-none px-3 py-2 font-semibold text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
                  @click="toggleSort('pb')"
                >
                  P/B
                  <span v-if="sortKey === 'pb'" class="inline-block ml-0.5 text-[10px]">
                    {{ sortOrder === 'asc' ? '▲' : '▼' }}
                  </span>
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in filteredRows"
                :key="row.symbol"
                class="border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-white/5"
              >
                <td class="px-3 py-2">
                  <button class="font-semibold text-brand-600" @click="goToDetail(row.symbol)">
                    {{ row.symbol }}
                  </button>
                  <p class="text-xs text-gray-500 dark:text-gray-400">{{ row.companyName }}</p>
                </td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatPrice(row.price) }}</td>
                <td
                  class="px-3 py-2 font-medium"
                  :class="row.changePercent >= 0 ? 'text-success-600' : 'text-error-600'"
                >
                  {{ row.changePercent >= 0 ? '+' : '' }}{{ row.changePercent.toFixed(2) }}%
                </td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatMaybeNumber(row.rsi) }}</td>
                <td class="px-3 py-2">
                  <span
                    class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium"
                    :class="
                      row.macd === 'bullish'
                        ? 'bg-success-50 text-success-600 dark:bg-success-500/15'
                        : row.macd === 'bearish'
                          ? 'bg-error-50 text-error-600 dark:bg-error-500/15'
                          : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                    "
                  >
                    {{ formatMacdLabel(row.macd) }}
                  </span>
                </td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatSignalSummary(row.signalSummary) }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatMaybeNumber(row.pe) }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatMaybeNumber(row.pb) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { VN30_TICKERS, useStockData } from '@/composables/useStockData'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { stockBackendApi, type CompanyOverview, type TradingSignals } from '@/services/stockBackendApi'

interface ScreenerRow {
  symbol: string
  companyName: string
  price: number
  changePercent: number
  rsi: number | null
  macd: TradingSignals['macd'] | 'n/a'
  signalSummary: TradingSignals['summary'] | '-'
  pe: number | null
  pb: number | null
}

const router = useRouter()

const { stocks, fetchInitialData } = useStockData()

const rows = ref<ScreenerRow[]>([])
usePriceSubscription('stock-screener', () => rows.value.map((row) => row.symbol))
const loading = ref(false)

const searchKeyword = ref('')
const rsiMin = ref(0)
const rsiMax = ref(100)
const maxPe = ref(100)
const maxPb = ref(10)
const bullishMacdOnly = ref(false)

const sortKey = ref<string>('changePercent')
const sortOrder = ref<'asc' | 'desc'>('desc')

function toggleSort(key: string) {
  if (sortKey.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = key
    // Default to desc for changePercent/RSI/PE/PB, asc for symbol/price/signal
    sortOrder.value = ['changePercent', 'rsi', 'pe', 'pb'].includes(key) ? 'desc' : 'asc'
  }
}

const filteredRows = computed(() => {
  const keyword = searchKeyword.value.trim().toLowerCase()

  return rows.value
    .map((row) => {
      const live = stocks[row.symbol]
      return live
        ? { ...row, price: live.price, changePercent: live.changePercent }
        : row
    })
    .filter((row) => {
      const keywordMatch =
        keyword.length === 0 ||
        row.symbol.toLowerCase().includes(keyword) ||
        row.companyName.toLowerCase().includes(keyword)

      if (!keywordMatch) return false

      if (row.rsi !== null && (row.rsi < rsiMin.value || row.rsi > rsiMax.value)) {
        return false
      }

      if (bullishMacdOnly.value && row.macd !== 'bullish') {
        return false
      }

      if (row.pe !== null && row.pe > maxPe.value) {
        return false
      }

      if (row.pb !== null && row.pb > maxPb.value) {
        return false
      }

      return true
    })
    .sort((a, b) => {
      const valA = a[sortKey.value as keyof ScreenerRow]
      const valB = b[sortKey.value as keyof ScreenerRow]

      if (valA === null || valA === undefined) return 1
      if (valB === null || valB === undefined) return -1

      if (typeof valA === 'string' && typeof valB === 'string') {
        const cmp = valA.localeCompare(valB)
        return sortOrder.value === 'asc' ? cmp : -cmp
      }

      const numA = Number(valA) || 0
      const numB = Number(valB) || 0

      if (numA < numB) return sortOrder.value === 'asc' ? -1 : 1
      if (numA > numB) return sortOrder.value === 'asc' ? 1 : -1
      return 0
    })
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
    const numberValue = toNumber(source[key])
    if (numberValue !== null) return numberValue
  }

  return null
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value)
}

function formatMaybeNumber(value: number | null): string {
  if (value === null) return '-'
  return value.toFixed(2)
}

function formatMacdLabel(value: ScreenerRow['macd']): string {
  if (value === 'bullish') return 'Tăng'
  if (value === 'bearish') return 'Giảm'
  return 'Không rõ'
}

function formatSignalSummary(value: ScreenerRow['signalSummary']): string {
  const map: Record<string, string> = {
    strong_buy: 'Mua mạnh',
    buy: 'Mua',
    neutral: 'Trung lập',
    sell: 'Bán',
    strong_sell: 'Bán mạnh',
    '-': '-',
  }

  return map[value] ?? value
}

function hasUsableSnapshotPrice(item: { price?: number; dataStatus?: string } | null | undefined): boolean {
  return Boolean(item && Number(item.price) > 0 && item.dataStatus !== 'NO_DATA_IN_SNAPSHOT')
}

function goToDetail(symbol: string): void {
  void router.push(`/stocks/${symbol}`)
}

function resetFilters(): void {
  searchKeyword.value = ''
  rsiMin.value = 0
  rsiMax.value = 100
  maxPe.value = 100
  maxPb.value = 10
  bullishMacdOnly.value = false
}

async function buildRow(symbol: string): Promise<ScreenerRow | null> {
  const upperSymbol = symbol.toUpperCase()
  const base = stocks[upperSymbol]

  let overview: CompanyOverview | null = null
  let technicalRsi: number | null = null
  let technicalMacd: TradingSignals['macd'] | 'n/a' = 'n/a'
  let technicalSummary: TradingSignals['summary'] | '-' = '-'

  try {
    const [overviewResult, technicalResult] = await Promise.allSettled([
      stockBackendApi.getCompanyOverview(upperSymbol),
      stockBackendApi.getTechnicalAnalysis(upperSymbol, undefined, undefined, 120),
    ])

    if (overviewResult.status === 'fulfilled') {
      overview = overviewResult.value
    }

    if (technicalResult.status === 'fulfilled') {
      const technical = technicalResult.value
      const rsiSeries = technical.indicators.rsi_14
      technicalRsi = rsiSeries.length > 0 ? rsiSeries[rsiSeries.length - 1] : null
      technicalMacd = technical.signals.macd
      technicalSummary = technical.signals.summary
    }
  } catch {
    // Keep fallback values.
  }

  const companyName =
    (typeof overview?.company_name === 'string' && overview.company_name) ||
    (typeof overview?.companyName === 'string' && overview.companyName) ||
    (typeof overview?.name === 'string' && overview.name) ||
    base?.companyName ||
    upperSymbol

  const baseHasPrice = hasUsableSnapshotPrice(base)
  const price = baseHasPrice ? base.price : readNumber(overview, ['last_price', 'price']) || 0
  const changePercent = baseHasPrice ? base.changePercent : 0

  if (price <= 0 && technicalRsi === null) {
    return null
  }

  return {
    symbol: upperSymbol,
    companyName,
    price,
    changePercent,
    rsi: technicalRsi,
    macd: technicalMacd,
    signalSummary: technicalSummary,
    pe: readNumber(overview, ['pe', 'p_e', 'pe_ratio', 'pe_ttm']),
    pb: readNumber(overview, ['pb', 'p_b', 'pb_ratio', 'pb_ttm']),
  }
}

async function loadScreenerData(): Promise<void> {
  loading.value = true

  try {
    await fetchInitialData()

    let symbols: string[] = [...VN30_TICKERS]

    try {
      const backendSymbols = await stockBackendApi.getStockList()
      if (backendSymbols.length > 0) {
        symbols = backendSymbols
      }
    } catch {
      // Keep VN30 fallback list.
    }

    const selectedSymbols = symbols.slice(0, 20)

    const result = await Promise.all(selectedSymbols.map((symbol) => buildRow(symbol)))
    rows.value = result.filter((item): item is ScreenerRow => item !== null)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadScreenerData()
})
</script>
