<template>
  <div class="space-y-6">
    <!-- KPI Cards -->
    <div class="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <div class="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Tổng doanh thu</p>
            <p class="mt-2 text-2xl font-bold text-emerald-600 dark:text-emerald-400">
              {{ loading ? '—' : formatPrice(stats?.total_revenue || 0) }}₫
            </p>
            <p v-if="revenueGrowth !== null" class="mt-1 text-xs" :class="revenueGrowth >= 0 ? 'text-emerald-500' : 'text-rose-500'">
              {{ revenueGrowth >= 0 ? '↑' : '↓' }} {{ Math.abs(revenueGrowth).toFixed(1) }}% so với tháng trước
            </p>
          </div>
          <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-50 dark:bg-emerald-500/10">
            <svg class="h-5 w-5 text-emerald-600 dark:text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Giao dịch hoàn tất</p>
            <p class="mt-2 text-2xl font-bold text-brand-600 dark:text-brand-400">
              {{ loading ? '—' : (stats?.total_subscriptions || 0).toLocaleString('vi-VN') }}
            </p>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {{ loading ? '' : (stats?.pending_count || 0) }} đang chờ thanh toán
            </p>
          </div>
          <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 dark:bg-brand-500/10">
            <svg class="h-5 w-5 text-brand-600 dark:text-brand-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Premium đang hoạt động</p>
            <p class="mt-2 text-2xl font-bold text-amber-600 dark:text-amber-400">
              {{ loading ? '—' : (stats?.active_premium_count || 0).toLocaleString('vi-VN') }}
            </p>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {{ loading || !stats ? '' : `${conversionRate}% tỷ lệ chuyển đổi` }}
            </p>
          </div>
          <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-amber-50 dark:bg-amber-500/10">
            <svg class="h-5 w-5 text-amber-600 dark:text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="relative overflow-hidden rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="flex items-start justify-between">
          <div>
            <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Tổng người dùng</p>
            <p class="mt-2 text-2xl font-bold text-purple-600 dark:text-purple-400">
              {{ loading ? '—' : (stats?.total_users || 0).toLocaleString('vi-VN') }}
            </p>
            <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {{ loading || !stats ? '' : `ARPU: ${formatPrice(arpu)}₫` }}
            </p>
          </div>
          <div class="flex h-11 w-11 items-center justify-center rounded-xl bg-purple-50 dark:bg-purple-500/10">
            <svg class="h-5 w-5 text-purple-600 dark:text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z"/>
            </svg>
          </div>
        </div>
      </div>
    </div>

    <!-- Revenue Chart -->
    <div class="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-1 border-b border-gray-100 px-6 py-5 dark:border-gray-800 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 class="text-base font-semibold text-gray-800 dark:text-white/90">Doanh thu & Tăng trưởng 12 tháng</h2>
          <p class="mt-0.5 text-sm text-gray-500 dark:text-gray-400">Cột = doanh thu · Đường = số giao dịch</p>
        </div>
        <div class="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span class="flex items-center gap-1.5">
            <span class="inline-block h-2.5 w-2.5 rounded-sm bg-emerald-500"></span> Doanh thu
          </span>
          <span class="flex items-center gap-1.5">
            <span class="inline-block h-0.5 w-5 bg-indigo-500"></span> Giao dịch
          </span>
        </div>
      </div>

      <div v-if="loading" class="flex items-center justify-center py-20">
        <div class="h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
      </div>

      <div v-else-if="error" class="px-6 py-8">
        <div class="rounded-xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300">
          {{ error }}
        </div>
      </div>

      <div v-else-if="!chartMonths.length" class="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
        Chưa có dữ liệu doanh thu. Hãy chạy seed script để tạo dữ liệu mẫu.
      </div>

      <div v-else class="px-4 pb-4 pt-2">
        <apexchart
          type="bar"
          height="320"
          :options="chartOptions"
          :series="chartSeries"
        />
      </div>
    </div>

    <!-- Monthly Data Table -->
    <div class="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="border-b border-gray-100 px-6 py-4 dark:border-gray-800">
        <h2 class="text-base font-semibold text-gray-800 dark:text-white/90">Chi tiết theo tháng</h2>
      </div>

      <div v-if="!loading && !error && chartMonths.length" class="overflow-x-auto">
        <table class="w-full min-w-[640px]">
          <thead class="bg-gray-50 dark:bg-gray-800/80">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Tháng</th>
              <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Doanh thu</th>
              <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Giao dịch</th>
              <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">TB/GD</th>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Tăng trưởng</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
            <tr
              v-for="(row, idx) in sortedMonthly"
              :key="row.month"
              class="hover:bg-gray-50 dark:hover:bg-gray-800/60"
            >
              <td class="px-6 py-3.5 font-medium text-gray-800 dark:text-gray-200">{{ row.month }}</td>
              <td class="px-6 py-3.5 text-right font-mono text-emerald-600 dark:text-emerald-400">
                {{ formatPrice(row.revenue) }}₫
              </td>
              <td class="px-6 py-3.5 text-right text-sm text-gray-600 dark:text-gray-400">{{ row.count }}</td>
              <td class="px-6 py-3.5 text-right text-sm text-gray-600 dark:text-gray-400">
                {{ row.count > 0 ? formatPrice(Math.round(row.revenue / row.count)) + '₫' : '—' }}
              </td>
              <td class="px-6 py-3.5">
                <div class="flex items-center gap-2">
                  <div class="h-1.5 w-32 overflow-hidden rounded-full bg-gray-200 dark:bg-gray-700">
                    <div
                      class="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-600 transition-all"
                      :style="{ width: barWidth(row.revenue) }"
                    ></div>
                  </div>
                  <span
                    v-if="idx > 0"
                    class="text-xs font-medium"
                    :class="monthGrowth(idx) >= 0 ? 'text-emerald-500' : 'text-rose-500'"
                  >
                    {{ monthGrowth(idx) >= 0 ? '+' : '' }}{{ monthGrowth(idx).toFixed(1) }}%
                  </span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-else-if="loading" class="flex items-center justify-center py-10">
        <div class="h-8 w-8 animate-spin rounded-full border-b-2 border-brand-500"></div>
      </div>

      <div v-else class="px-6 py-8 text-center text-gray-500 dark:text-gray-400">
        Chưa có dữ liệu.
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { getAdminSalesStats, type SalesStats } from '@/services/authApi'

const stats   = ref<SalesStats | null>(null)
const loading = ref(true)
const error   = ref('')

// ── Dark-mode detection ──────────────────────────────────────────────
const isDark = ref(document.documentElement.classList.contains('dark'))
const _observer = new MutationObserver(() => {
  isDark.value = document.documentElement.classList.contains('dark')
})
_observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] })
onUnmounted(() => _observer.disconnect())

// ── Formatters ───────────────────────────────────────────────────────
function formatPrice(value: number): string {
  return new Intl.NumberFormat('vi-VN').format(Math.round(value))
}

// ── Derived data (sorted ascending for chart) ───────────────────────
const sortedMonthly = computed(() => {
  if (!stats.value) return []
  return [...stats.value.monthly_revenue].sort((a, b) => a.month.localeCompare(b.month))
})

const chartMonths  = computed(() => sortedMonthly.value.map((r) => r.month))
const chartRevenue = computed(() => sortedMonthly.value.map((r) => Math.round(r.revenue)))
const chartCounts  = computed(() => sortedMonthly.value.map((r) => r.count))

// ── KPI computed ──────────────────────────────────────────────────────
const revenueGrowth = computed<number | null>(() => {
  const rows = sortedMonthly.value
  if (rows.length < 2) return null
  const prev = rows[rows.length - 2].revenue
  const curr = rows[rows.length - 1].revenue
  if (prev <= 0) return null
  return ((curr - prev) / prev) * 100
})

const conversionRate = computed(() => {
  if (!stats.value || !stats.value.total_users) return '0.0'
  return ((stats.value.active_premium_count / stats.value.total_users) * 100).toFixed(1)
})

const arpu = computed(() => {
  if (!stats.value || !stats.value.total_users) return 0
  return Math.round(stats.value.total_revenue / stats.value.total_users)
})

function barWidth(revenue: number): string {
  const max = Math.max(...(sortedMonthly.value.map((r) => r.revenue)), 1)
  return `${Math.max(4, (revenue / max) * 100)}%`
}

function monthGrowth(idx: number): number {
  const rows = sortedMonthly.value
  const prev = rows[idx - 1]?.revenue ?? 0
  const curr = rows[idx]?.revenue ?? 0
  if (prev <= 0) return 0
  return ((curr - prev) / prev) * 100
}

// ── ApexCharts config ────────────────────────────────────────────────
const axisColor = computed(() => isDark.value ? '#6B7280' : '#9CA3AF')
const gridColor = computed(() => isDark.value ? '#374151' : '#F3F4F6')

const chartSeries = computed(() => [
  { name: 'Doanh thu (₫)', type: 'bar',  data: chartRevenue.value },
  { name: 'Giao dịch',      type: 'line', data: chartCounts.value  },
])

const chartOptions = computed(() => ({
  chart: {
    type: 'bar' as const,
    height: 320,
    toolbar:    { show: false },
    background: 'transparent',
    fontFamily: 'Outfit, Inter, sans-serif',
    animations: { enabled: true, speed: 600 },
  },
  plotOptions: {
    bar: {
      borderRadius:  6,
      columnWidth:   '55%',
      borderRadiusApplication: 'end' as const,
    },
  },
  dataLabels: { enabled: false },
  stroke: {
    width: [0, 3],
    curve: 'smooth' as const,
    colors: ['transparent', '#6366F1'],
  },
  markers: {
    size: [0, 4],
    colors: ['#6366F1'],
    strokeColors: isDark.value ? '#1F2937' : '#FFFFFF',
    strokeWidth: 2,
  },
  colors: ['#10B981', '#6366F1'],
  fill: {
    type: ['gradient', 'solid'],
    gradient: {
      shade:       'light',
      type:        'vertical',
      shadeIntensity: 0.3,
      gradientToColors: ['#059669'],
      opacityFrom: 0.95,
      opacityTo:   0.75,
    },
  },
  xaxis: {
    categories: chartMonths.value,
    labels: {
      style: { colors: axisColor.value, fontSize: '11px' },
      rotate: -30,
    },
    axisBorder: { color: gridColor.value },
    axisTicks:  { color: gridColor.value },
  },
  yaxis: [
    {
      seriesName: 'Doanh thu (₫)',
      title: {
        text: 'Doanh thu (₫)',
        style: { color: axisColor.value, fontSize: '11px' },
      },
      labels: {
        style: { colors: axisColor.value, fontSize: '11px' },
        formatter: (v: number) => {
          if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`
          if (v >= 1_000)     return `${(v / 1_000).toFixed(0)}K`
          return String(v)
        },
      },
    },
    {
      seriesName: 'Giao dịch',
      opposite: true,
      title: {
        text: 'Giao dịch',
        style: { color: axisColor.value, fontSize: '11px' },
      },
      labels: {
        style: { colors: axisColor.value, fontSize: '11px' },
        formatter: (v: number) => String(Math.round(v)),
      },
      min: 0,
    },
  ],
  grid: {
    borderColor: gridColor.value,
    strokeDashArray: 4,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
  },
  tooltip: {
    theme: isDark.value ? 'dark' : 'light',
    shared: true,
    intersect: false,
    y: [
      { formatter: (v: number) => `${new Intl.NumberFormat('vi-VN').format(v)}₫` },
      { formatter: (v: number) => `${v} giao dịch` },
    ],
  },
  legend: { show: false },
}))

// ── Load ─────────────────────────────────────────────────────────────
async function loadStats(): Promise<void> {
  loading.value = true
  error.value   = ''
  try {
    stats.value = await getAdminSalesStats()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Lỗi tải dữ liệu doanh thu.'
  } finally {
    loading.value = false
  }
}

onMounted(loadStats)
</script>
