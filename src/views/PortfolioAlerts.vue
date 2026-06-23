<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-2">
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Danh mục và cảnh báo</h1>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Theo dõi vị thế và mức giá mục tiêu theo thời gian thực.
        </p>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Tổng giá trị thị trường</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ formatCurrency(summary.totalValue) }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Tổng giá vốn</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ formatCurrency(summary.totalCost) }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Lãi lỗ tạm tính</p>
          <p
            class="mt-2 text-2xl font-semibold"
            :class="summary.totalPnl >= 0 ? 'text-success-600' : 'text-error-600'"
          >
            {{ summary.totalPnl >= 0 ? '+' : '' }}{{ formatCurrency(summary.totalPnl) }}
          </p>
        </div>
      </div>

      <section class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
        <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Vị thế</h2>

        <div v-if="loading" class="py-6 text-sm text-gray-500 dark:text-gray-400">
          Đang tải danh mục...
        </div>
        <div v-else-if="errorMessage" class="py-6 text-sm text-error-600">
          {{ errorMessage }}
        </div>
        <div v-else-if="enrichedPositions.length === 0" class="py-6 text-sm text-gray-500 dark:text-gray-400">
          Chưa có vị thế
        </div>
        <div v-else class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b border-gray-200 dark:border-gray-700">
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Mã</th>
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Số lượng</th>
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Giá vốn</th>
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Giá hiện tại</th>
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Giá trị thị trường</th>
                <th class="px-3 py-2 font-medium text-gray-500 dark:text-gray-400">Lãi/Lỗ</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="position in enrichedPositions"
                :key="position.symbol"
                class="border-b border-gray-100 dark:border-gray-800"
              >
                <td class="px-3 py-2 font-medium text-gray-800 dark:text-white/90">{{ position.symbol }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ position.quantity }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatPrice(position.avgPrice) }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatPrice(position.currentPrice) }}</td>
                <td class="px-3 py-2 text-gray-700 dark:text-gray-300">{{ formatCurrency(position.marketValue) }}</td>
                <td
                  class="px-3 py-2 font-medium"
                  :class="position.pnl >= 0 ? 'text-success-600' : 'text-error-600'"
                >
                  {{ position.pnl >= 0 ? '+' : '' }}{{ formatCurrency(position.pnl) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>

      <div class="grid grid-cols-12 gap-4 md:gap-6">
        <section class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] xl:col-span-7">
          <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Cảnh báo giá</h2>

          <p class="text-sm text-gray-500 dark:text-gray-400">
            Cảnh báo được lấy từ mức TP/SL trong danh mục.
          </p>

          <div class="mt-4 space-y-2">
            <div v-if="alerts.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
              Chưa có cảnh báo TP/SL
            </div>
            <div
              v-else
              v-for="alert in alerts"
              :key="alert.id"
              class="flex flex-col gap-2 rounded-lg border border-gray-100 px-3 py-2 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between"
            >
              <div class="text-sm">
                <span class="mr-2 inline-flex rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                  {{ alert.label }}
                </span>
                <span class="font-semibold text-gray-800 dark:text-white/90">{{ alert.symbol }}</span>
                <span class="mx-1 text-gray-500 dark:text-gray-400">{{ alert.direction === 'above' ? '>' : '<' }}</span>
                <span class="text-gray-700 dark:text-gray-300">{{ formatPrice(alert.targetPrice) }}</span>
              </div>

              <div class="flex items-center gap-3">
                <span
                  class="inline-flex rounded-full px-2 py-0.5 text-xs font-medium"
                  :class="
                    isTriggered(alert)
                      ? 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-400'
                      : 'bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400'
                  "
                >
                  {{ isTriggered(alert) ? 'Đã kích hoạt' : 'Đang theo dõi' }}
                </span>
              </div>
            </div>
          </div>
        </section>

        <section class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] xl:col-span-5">
          <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-white/90">Cảnh báo đã kích hoạt</h2>

          <div v-if="triggeredAlerts.length === 0" class="text-sm text-gray-500 dark:text-gray-400">
            Hiện tại chưa có cảnh báo nào đủ điều kiện.
          </div>

          <ul v-else class="space-y-2">
            <li
              v-for="alert in triggeredAlerts"
              :key="`triggered-${alert.id}`"
              class="rounded-lg bg-warning-50 px-3 py-2 text-sm text-warning-700 dark:bg-warning-500/10 dark:text-warning-400"
            >
              {{ alert.symbol }} đã vượt
              {{ alert.direction === 'above' ? 'lên trên' : 'xuống dưới' }} {{ formatPrice(alert.targetPrice) }}
              (hiện tại: {{ formatPrice(currentPriceMap[alert.symbol] || 0) }})
            </li>
          </ul>
        </section>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { useStockData } from '@/composables/useStockData'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { getMyPortfolio, type PortfolioItem } from '@/services/authApi'

interface PriceAlert {
  id: string
  symbol: string
  targetPrice: number
  direction: 'above' | 'below'
  label: 'TP' | 'SL'
}

const {
  stocks,
  fetchInitialData,
  loadSymbolData,
} = useStockData()

const positions = ref<PortfolioItem[]>([])
const loading = ref(true)
const errorMessage = ref('')

const currentPriceMap = computed<Record<string, number>>(() => {
  const map: Record<string, number> = {}
  Object.values(stocks).forEach((stock) => {
    if (stock.price > 0 && stock.dataStatus !== 'NO_DATA_IN_SNAPSHOT') {
      map[stock.symbol] = toDisplayPrice(stock.price)
    }
  })
  return map
})

const alerts = computed<PriceAlert[]>(() =>
  positions.value.flatMap((item) => {
    const result: PriceAlert[] = []
    const tpPrice = toDisplayPrice(item.tp_price)
    const slPrice = toDisplayPrice(item.sl_price)

    if (tpPrice > 0) {
      result.push({
        id: `${item.symbol}-tp`,
        symbol: item.symbol,
        targetPrice: tpPrice,
        direction: 'above',
        label: 'TP',
      })
    }

    if (slPrice > 0) {
      result.push({
        id: `${item.symbol}-sl`,
        symbol: item.symbol,
        targetPrice: slPrice,
        direction: 'below',
        label: 'SL',
      })
    }

    return result
  }),
)

const subscribedSymbols = computed(() => [
  ...positions.value.map((position) => position.symbol),
  ...alerts.value.map((alert) => alert.symbol),
])
usePriceSubscription('portfolio-alerts', () => subscribedSymbols.value)

const enrichedPositions = computed(() =>
  positions.value.filter((position) => position.quantity > 0).map((position) => {
    const avgPrice = toDisplayPrice(position.avg_price)
    const currentPrice = currentPriceMap.value[position.symbol] || avgPrice
    const marketValue = currentPrice * position.quantity
    const totalCost = avgPrice * position.quantity

    return {
      symbol: position.symbol,
      quantity: position.quantity,
      avgPrice,
      currentPrice,
      marketValue,
      pnl: marketValue - totalCost,
    }
  }),
)

const summary = computed(() => {
  const totalValue = enrichedPositions.value.reduce((sum, item) => sum + item.marketValue, 0)
  const totalCost = enrichedPositions.value.reduce((sum, item) => sum + item.avgPrice * item.quantity, 0)

  return {
    totalValue,
    totalCost,
    totalPnl: totalValue - totalCost,
  }
})

const triggeredAlerts = computed(() => alerts.value.filter((alert) => isTriggered(alert)))

function isTriggered(alert: PriceAlert): boolean {
  const currentPrice = currentPriceMap.value[alert.symbol]
  if (!currentPrice) return false

  if (alert.direction === 'above') {
    return currentPrice >= alert.targetPrice
  }

  return currentPrice <= alert.targetPrice
}

function toDisplayPrice(raw: number | null | undefined): number {
  const value = Number(raw || 0)
  if (!Number.isFinite(value) || value <= 0) return 0
  return value >= 1000 ? value : value * 1000
}

function formatPrice(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    maximumFractionDigits: 0,
  }).format(value)
}

function formatCurrency(value: number): string {
  return new Intl.NumberFormat('vi-VN', {
    style: 'currency',
    currency: 'VND',
    maximumFractionDigits: 0,
  }).format(value)
}

async function loadPortfolio(): Promise<void> {
  loading.value = true
  errorMessage.value = ''
  try {
    const data = await getMyPortfolio()
    positions.value = data.items
    await loadPositionPrices()
  } catch (error: any) {
    errorMessage.value = error?.message || 'Không thể tải danh mục.'
    positions.value = []
  } finally {
    loading.value = false
  }
}

async function loadPositionPrices(): Promise<void> {
  const symbols = Array.from(
    new Set(
      positions.value
        .map((position) => position.symbol.trim().toUpperCase())
        .filter(Boolean),
    ),
  )

  await Promise.all(symbols.map((symbol) => loadSymbolData(symbol)))
}

onMounted(async () => {
  await fetchInitialData()
  await loadPortfolio()
})

</script>
