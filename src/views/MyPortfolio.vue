<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Danh mục của tôi</h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">Quản lý vị thế và đặt mức chốt lời/cắt lỗ cho từng mã (đơn vị giá: nghìn đồng/cp).</p>
        </div>
        <button
          @click="showAddModal = true"
          class="inline-flex items-center gap-2 rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
          </svg>
          Thêm mã
        </button>
      </div>

      <div class="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Số mã đang sở hữu</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ ownedSymbolCount }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Số tiền vốn</p>
          <p class="mt-2 text-2xl font-semibold text-gray-800 dark:text-white/90">{{ formatCurrency(totalCapital) }}</p>
        </div>
        <div class="rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Số tiền lãi / lỗ</p>
          <p
            class="mt-2 text-2xl font-semibold"
            :class="totalPnl >= 0 ? 'text-success-600' : 'text-error-600'"
          >
            {{ formatCurrency(totalPnl) }}
          </p>
        </div>
      </div>

      <div
        v-if="loading"
        class="rounded-2xl border border-gray-200 bg-white p-10 text-center dark:border-gray-800 dark:bg-white/[0.03]"
      >
        <div class="mx-auto h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
      </div>

      <div
        v-else-if="items.length === 0"
        class="rounded-2xl border border-dashed border-gray-300 bg-white p-12 text-center dark:border-gray-700 dark:bg-white/[0.03]"
      >
        <p class="text-sm text-gray-500 dark:text-gray-400">Chưa có mã cổ phiếu nào trong danh mục.</p>
        <button
          @click="showAddModal = true"
          class="mt-4 inline-flex items-center rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white hover:bg-brand-600"
        >
          Thêm mã đầu tiên
        </button>
      </div>

      <section
        v-else
        class="overflow-hidden rounded-2xl border border-gray-200 bg-white dark:border-gray-800 dark:bg-white/[0.03]"
      >
        <div class="overflow-x-auto">
          <table class="w-full text-left text-sm">
            <thead>
              <tr class="border-b border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800/40">
                <th class="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Mã CK</th>
                <th class="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Số lượng</th>
                <th class="px-4 py-3 text-right font-medium text-gray-500 dark:text-gray-400">Giá TB (nghìn)</th>
                <th class="px-4 py-3 text-right font-medium text-success-700 dark:text-success-400">Giá TP (nghìn)</th>
                <th class="px-4 py-3 text-right font-medium text-error-700 dark:text-error-400">Giá SL (nghìn)</th>
                <th class="px-4 py-3 font-medium text-gray-500 dark:text-gray-400">Ghi chú</th>
                <th class="px-4 py-3 text-center font-medium text-gray-500 dark:text-gray-400">Thao tác</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="item in items"
                :key="item.id"
                class="border-b border-gray-100 transition-colors hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-800/30"
              >
                <td class="px-4 py-3">
                  <router-link :to="`/stocks/${item.symbol}`" class="font-semibold text-brand-600 hover:underline">
                    {{ item.symbol }}
                  </router-link>
                </td>
                <td class="px-4 py-3 text-right font-mono">{{ item.quantity.toLocaleString() }}</td>
                <td class="px-4 py-3 text-right font-mono">{{ item.avg_price ? formatPrice(item.avg_price) : '—' }}</td>
                <td class="px-4 py-3">
                  <input
                    v-model.number="editTpPrice[item.id]"
                    type="number"
                    min="1"
                    max="1000"
                    step="0.1"
                    placeholder="—"
                    class="w-28 rounded-md border border-success-200 bg-white px-2 py-1 text-right font-mono text-sm text-success-700 focus:outline-none focus:ring-2 focus:ring-success-500 dark:border-success-700/50 dark:bg-gray-800 dark:text-success-400"
                  />
                </td>
                <td class="px-4 py-3">
                  <input
                    v-model.number="editSlPrice[item.id]"
                    type="number"
                    min="1"
                    max="1000"
                    step="0.1"
                    placeholder="—"
                    class="w-28 rounded-md border border-error-200 bg-white px-2 py-1 text-right font-mono text-sm text-error-700 focus:outline-none focus:ring-2 focus:ring-error-500 dark:border-error-700/50 dark:bg-gray-800 dark:text-error-400"
                  />
                </td>
                <td class="max-w-[220px] truncate px-4 py-3 text-gray-600 dark:text-gray-300">{{ item.note || '—' }}</td>
                <td class="px-4 py-3 text-center">
                  <div class="flex items-center justify-center gap-3">
                    <button
                      @click="handleSaveTargets(item)"
                      :disabled="rowSaving[item.id]"
                      class="text-sm font-medium text-brand-600 hover:text-brand-700 disabled:opacity-50"
                    >
                      {{ rowSaving[item.id] ? 'Lưu...' : 'Lưu' }}
                    </button>
                    <button @click="handleRemove(item.symbol)" class="text-sm font-medium text-error-600 hover:text-error-700">
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <div
      v-if="showAddModal"
      class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4"
      @click.self="showAddModal = false"
    >
      <div class="w-full max-w-xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-gray-800">
        <h3 class="mb-1 text-lg font-semibold text-gray-900 dark:text-white">Thêm vào danh mục</h3>
        <p class="mb-5 text-sm text-gray-500 dark:text-gray-400">Bạn có thể điền luôn mức TP/SL để theo dõi rủi ro (đơn vị nghìn đồng/cp).</p>
        <form @submit.prevent="handleAdd" class="space-y-4">
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Mã cổ phiếu</label>
            <div class="relative">
              <input
                v-model="newSymbol"
                type="text"
                maxlength="10"
                placeholder="Gõ mã, ví dụ: FPT"
                required
                @focus="showSymbolSuggestions = true"
                @input="showSymbolSuggestions = true"
                @blur="handleSymbolBlur"
                class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 uppercase text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
              <div
                v-if="showSymbolSuggestions && filteredSymbols.length > 0"
                class="absolute z-10 mt-1 max-h-48 w-full overflow-auto rounded-lg border border-gray-200 bg-white shadow-lg dark:border-gray-700 dark:bg-gray-800"
              >
                <button
                  v-for="symbol in filteredSymbols"
                  :key="symbol"
                  type="button"
                  @mousedown.prevent="pickSymbol(symbol)"
                  class="flex w-full items-center justify-between px-3 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 dark:text-gray-200 dark:hover:bg-gray-700"
                >
                  <span class="font-semibold">{{ symbol }}</span>
                  <span class="text-xs text-gray-400">VN30</span>
                </button>
              </div>
            </div>
            <p class="mt-1 text-xs" :class="isNewSymbolValid || !newSymbol ? 'text-gray-500 dark:text-gray-400' : 'text-error-600'">
              {{ isNewSymbolValid || !newSymbol ? 'Chỉ cho phép mã trong rổ VN30.' : 'Mã không hợp lệ. Hãy chọn từ danh sách VN30.' }}
            </p>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Số lượng</label>
              <input
                v-model.number="newQuantity"
                type="number"
                min="0"
                placeholder="0"
                class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Giá TB (nghìn đồng/cp)</label>
              <input
                v-model.number="newAvgPrice"
                type="number"
                min="1"
                max="1000"
                step="0.1"
                placeholder="VD: 20"
                class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
              />
            </div>
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-sm font-medium text-success-700 dark:text-success-400">Giá TP (nghìn đồng/cp)</label>
              <input
                v-model.number="newTpPrice"
                type="number"
                min="1"
                max="1000"
                step="0.1"
                placeholder="VD: 23"
                class="w-full rounded-lg border border-success-200 bg-white px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-success-500 dark:border-success-700/50 dark:bg-gray-700 dark:text-white"
              />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-error-700 dark:text-error-400">Giá SL (nghìn đồng/cp)</label>
              <input
                v-model.number="newSlPrice"
                type="number"
                min="1"
                max="1000"
                step="0.1"
                placeholder="VD: 18"
                class="w-full rounded-lg border border-error-200 bg-white px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-error-500 dark:border-error-700/50 dark:bg-gray-700 dark:text-white"
              />
            </div>
          </div>
          <div>
            <label class="mb-1 block text-sm font-medium text-gray-700 dark:text-gray-300">Ghi chú</label>
            <input
              v-model="newNote"
              type="text"
              placeholder="Tùy chọn..."
              class="w-full rounded-lg border border-gray-300 bg-white px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-brand-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
            />
          </div>
          <div class="flex gap-3 pt-2">
            <button
              type="button"
              @click="showAddModal = false"
              class="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-gray-700 transition-colors hover:bg-gray-50 dark:border-gray-600 dark:text-gray-300 dark:hover:bg-gray-700"
            >
              Hủy
            </button>
            <button
              type="submit"
              :disabled="addLoading"
              class="flex-1 rounded-lg bg-brand-500 px-4 py-2 text-white transition-colors hover:bg-brand-600 disabled:opacity-50"
            >
              {{ addLoading ? 'Đang thêm...' : 'Thêm' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { stockBackendApi } from '@/services/stockBackendApi'
import { usePriceSubscription } from '@/composables/usePriceSubscription'
import { stockPriceStore } from '@/stores/stockPriceStore'
import {
  getMyPortfolio,
  addToPortfolio,
  removeFromPortfolio,
  updatePortfolioItem,
  type PortfolioItem,
} from '@/services/authApi'

const items = ref<PortfolioItem[]>([])
const loading = ref(true)
const showAddModal = ref(false)
const addLoading = ref(false)

const newSymbol = ref('')
const newQuantity = ref(0)
const newAvgPrice = ref<number | undefined>(undefined)
const newTpPrice = ref<number | undefined>(undefined)
const newSlPrice = ref<number | undefined>(undefined)
const newNote = ref('')
const availableSymbols = ref<string[]>([])
const showSymbolSuggestions = ref(false)
const editTpPrice = ref<Record<number, number | undefined>>({})
const editSlPrice = ref<Record<number, number | undefined>>({})
const rowSaving = ref<Record<number, boolean>>({})
const { stocksBySymbol } = stockPriceStore
usePriceSubscription('my-portfolio', () => items.value.map((item) => item.symbol))

const MIN_PRICE_THOUSAND = 1
const MAX_PRICE_THOUSAND = 1000

const ownedItems = computed(() => items.value.filter((item) => item.quantity > 0))
const ownedSymbolCount = computed(() => ownedItems.value.length)
const totalCapital = computed(() =>
  ownedItems.value.reduce((sum, item) => sum + (item.avg_price || 0) * item.quantity * 1000, 0),
)
const totalPnl = computed(() =>
  ownedItems.value.reduce((sum, item) => {
    const avgPrice = item.avg_price || 0
    if (avgPrice <= 0) return sum

    const currentPriceRaw = stocksBySymbol[item.symbol]?.price ?? avgPrice
    const currentPrice = toThousandPrice(currentPriceRaw)
    return sum + (currentPrice - avgPrice) * item.quantity * 1000
  }, 0),
)
const normalizedNewSymbol = computed(() => newSymbol.value.trim().toUpperCase())
const filteredSymbols = computed(() => {
  const keyword = normalizedNewSymbol.value
  if (!keyword) return availableSymbols.value.slice(0, 10)

  return availableSymbols.value
    .filter((symbol) => symbol.includes(keyword))
    .slice(0, 10)
})
const isNewSymbolValid = computed(
  () => normalizedNewSymbol.value.length > 0 && availableSymbols.value.includes(normalizedNewSymbol.value),
)

function formatPrice(n: number): string {
  return n.toLocaleString('vi-VN', { minimumFractionDigits: 0, maximumFractionDigits: 2 })
}

function formatCurrency(n: number): string {
  return n.toLocaleString('vi-VN')
}

function toThousandPrice(raw: number): number {
  if (!Number.isFinite(raw) || raw <= 0) return 0
  return raw >= 1000 ? raw / 1000 : raw
}

function isValidThousandPrice(value?: number): boolean {
  if (value === undefined || value === null) return true
  return Number.isFinite(value) && value >= MIN_PRICE_THOUSAND && value <= MAX_PRICE_THOUSAND
}

async function loadPortfolio() {
  loading.value = true
  try {
    const data = await getMyPortfolio()
    items.value = data.items
    const tpMap: Record<number, number | undefined> = {}
    const slMap: Record<number, number | undefined> = {}
    for (const item of data.items) {
      tpMap[item.id] = item.tp_price ?? undefined
      slMap[item.id] = item.sl_price ?? undefined
    }
    editTpPrice.value = tpMap
    editSlPrice.value = slMap
  } catch (e) {
    console.error('Failed to load portfolio:', e)
  } finally {
    loading.value = false
  }
}

async function loadAvailableSymbols() {
  try {
    const symbols = await stockBackendApi.getStockList()
    availableSymbols.value = [...new Set(symbols.map((item) => item.toUpperCase()))].sort()
  } catch (error) {
    console.error('Failed to load VN30 symbols:', error)
    availableSymbols.value = []
  }
}

function pickSymbol(symbol: string) {
  newSymbol.value = symbol
  showSymbolSuggestions.value = false
}

function handleSymbolBlur() {
  setTimeout(() => {
    showSymbolSuggestions.value = false
  }, 120)
}

async function handleSaveTargets(item: PortfolioItem) {
  const nextTp = editTpPrice.value[item.id]
  const nextSl = editSlPrice.value[item.id]

  if (!isValidThousandPrice(nextTp) || !isValidThousandPrice(nextSl)) {
    alert(`Giá TP/SL phải theo đơn vị nghìn đồng/cp và nằm trong khoảng ${MIN_PRICE_THOUSAND}-${MAX_PRICE_THOUSAND}.`)
    return
  }

  rowSaving.value[item.id] = true
  try {
    await updatePortfolioItem(item.symbol, {
      tp_price: nextTp,
      sl_price: nextSl,
    })
    await loadPortfolio()
  } catch (e: any) {
    alert(e.message || 'Lỗi khi lưu TP/SL')
  } finally {
    rowSaving.value[item.id] = false
  }
}

async function handleAdd() {
  if (!newSymbol.value.trim()) return

  const symbol = normalizedNewSymbol.value
  if (!availableSymbols.value.includes(symbol)) {
    alert('Vui lòng chọn mã hợp lệ trong rổ VN30.')
    return
  }

  if (!isValidThousandPrice(newAvgPrice.value) || !isValidThousandPrice(newTpPrice.value) || !isValidThousandPrice(newSlPrice.value)) {
    alert(`Giá TB/TP/SL phải theo đơn vị nghìn đồng/cp và nằm trong khoảng ${MIN_PRICE_THOUSAND}-${MAX_PRICE_THOUSAND}.`)
    return
  }

  addLoading.value = true
  try {
    await addToPortfolio(
      symbol,
      newQuantity.value,
      newAvgPrice.value,
      newTpPrice.value,
      newSlPrice.value,
      newNote.value || undefined,
    )
    showAddModal.value = false
    newSymbol.value = ''
    newQuantity.value = 0
    newAvgPrice.value = undefined
    newTpPrice.value = undefined
    newSlPrice.value = undefined
    newNote.value = ''
    await loadPortfolio()
  } catch (e: any) {
    alert(e.message || 'Lỗi khi thêm mã')
  } finally {
    addLoading.value = false
  }
}

async function handleRemove(symbol: string) {
  if (!confirm(`Xóa ${symbol} khỏi danh mục?`)) return
  try {
    await removeFromPortfolio(symbol)
    await loadPortfolio()
  } catch (e: any) {
    alert(e.message || 'Lỗi khi xóa mã')
  }
}

onMounted(loadPortfolio)
onMounted(loadAvailableSymbols)
</script>
