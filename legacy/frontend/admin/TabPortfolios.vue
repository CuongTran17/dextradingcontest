<template>
  <div class="space-y-6">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Portfolio advisory</p>
          <h2 class="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">Danh mục khách hàng</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Xem nhanh các mã cổ phiếu mà từng khách hàng đang theo dõi hoặc nắm giữ.
          </p>
        </div>
        <button
          class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          :disabled="loading"
          @click="loadPortfolios"
        >
          Làm mới
        </button>
      </div>
    </div>

    <div v-if="loading" class="rounded-2xl border border-gray-200 bg-white py-16 text-center shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="mx-auto h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
    </div>

    <div v-else-if="error" class="rounded-2xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300">
      {{ error }}
    </div>

    <div v-else-if="portfolios.length === 0" class="rounded-2xl border border-gray-200 bg-white px-6 py-14 text-center shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="text-5xl">📋</div>
      <p class="mt-4 text-gray-500 dark:text-gray-400">Chưa có khách hàng nào tạo danh mục đầu tư.</p>
    </div>

    <div v-else class="space-y-6">
      <article
        v-for="portfolio in portfolios"
        :key="portfolio.user.id"
        class="overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]"
      >
        <div class="flex flex-col gap-3 border-b border-gray-100 bg-gray-50 px-6 py-4 dark:border-gray-800 dark:bg-gray-800/40 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h3 class="text-base font-semibold text-gray-800 dark:text-gray-200">{{ portfolio.user.fullname }}</h3>
            <p class="text-sm text-gray-500 dark:text-gray-400">{{ portfolio.user.email }}</p>
          </div>
          <div class="flex items-center gap-3">
            <span
              class="inline-flex rounded-full px-3 py-1 text-xs font-semibold"
              :class="roleClass(portfolio.user.role)"
            >
              {{ portfolio.user.role.toUpperCase() }}
            </span>
            <span class="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
              {{ portfolio.total_symbols }} mã
            </span>
          </div>
        </div>

        <div v-if="portfolio.holdings.length === 0" class="px-6 py-8 text-sm text-gray-500 dark:text-gray-400">
          Không có mã nào trong danh mục.
        </div>

        <div v-else class="overflow-hidden">
          <table class="w-full min-w-[860px]">
            <thead class="bg-white dark:bg-gray-900/40">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Mã</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Số lượng</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Giá TB</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-success-700 dark:text-success-400">Giá TP</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-error-700 dark:text-error-400">Giá SL</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Ghi chú</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-for="holding in portfolio.holdings" :key="holding.symbol" class="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                <td class="px-6 py-3 font-semibold text-brand-600 dark:text-brand-400">{{ holding.symbol }}</td>
                <td class="px-6 py-3 text-right font-mono text-sm text-gray-700 dark:text-gray-300">{{ holding.quantity.toLocaleString('vi-VN') }}</td>
                <td class="px-6 py-3 text-right font-mono text-sm text-gray-700 dark:text-gray-300">
                  {{ formatMoney(holding.avg_price) }}
                </td>
                <td class="px-6 py-3 text-right font-mono text-sm text-success-700 dark:text-success-400">
                  {{ formatMoney(holding.tp_price) }}
                </td>
                <td class="px-6 py-3 text-right font-mono text-sm text-error-700 dark:text-error-400">
                  {{ formatMoney(holding.sl_price) }}
                </td>
                <td class="px-6 py-3 text-sm text-gray-500 dark:text-gray-400">{{ holding.note || '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <div v-if="total > perPage" class="flex items-center justify-center gap-2">
        <button
          class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          :disabled="page <= 1 || loading"
          @click="changePage(page - 1)"
        >
          ‹ Trước
        </button>
        <span class="px-3 text-sm text-gray-500 dark:text-gray-400">Trang {{ page }}</span>
        <button
          class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          :disabled="portfolios.length < perPage || page * perPage >= total || loading"
          @click="changePage(page + 1)"
        >
          Sau ›
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getAdminUserPortfolios, type AdminUserPortfolio } from '@/services/authApi'

const portfolios = ref<AdminUserPortfolio[]>([])
const loading = ref(true)
const error = ref('')
const page = ref(1)
const perPage = 20
const total = ref(0)

function roleClass(role: string): string {
  if (role === 'premium') {
    return 'bg-amber-100 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300'
  }
  if (role === 'admin') {
    return 'bg-red-100 text-red-700 dark:bg-red-500/15 dark:text-red-300'
  }
  return 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
}

function formatMoney(value: number | null): string {
  return value === null || Number.isNaN(value) ? '—' : value.toLocaleString('vi-VN')
}

async function loadPortfolios(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    const data = await getAdminUserPortfolios(page.value, perPage)
    portfolios.value = data.portfolios
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không tải được danh mục khách hàng.'
  } finally {
    loading.value = false
  }
}

function changePage(newPage: number): void {
  if (newPage < 1 || newPage === page.value) {
    return
  }
  page.value = newPage
  loadPortfolios()
}

onMounted(loadPortfolios)
</script>
