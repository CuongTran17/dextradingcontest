<template>
  <div class="space-y-6">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">ETL Monitor</p>
          <h2 class="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">Theo dõi pipeline dữ liệu</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Tóm tắt Extract, Transform, Load; snapshot mới nhất; dữ liệu đã lấy; và lịch sử chạy pipeline.
          </p>
        </div>

        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <button
            class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            :disabled="loading"
            @click="loadMonitor"
          >
            Làm mới
          </button>
          <button
            class="rounded-lg bg-brand-500 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-50"
            :disabled="triggering"
            @click="triggerManualRun"
          >
            {{ triggering ? 'Đang khởi chạy...' : 'Chạy ETL thủ công' }}
          </button>
        </div>
      </div>

      <div v-if="notice" class="mt-4 rounded-xl border px-4 py-3 text-sm" :class="noticeClass">
        {{ notice }}
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center rounded-2xl border border-gray-200 bg-white py-16 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
    </div>

    <div v-else-if="error" class="rounded-2xl border border-error-200 bg-error-50 px-5 py-4 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300">
      {{ error }}
    </div>

    <template v-else>
      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Trạng thái</p>
          <div class="mt-3 flex items-center gap-2">
            <span class="h-3 w-3 rounded-full" :class="statusDotClass"></span>
            <span class="text-xl font-bold capitalize text-gray-800 dark:text-white/90">{{ status?.status || health?.status || 'unknown' }}</span>
          </div>
          <p class="mt-2 font-mono text-xs text-gray-500 dark:text-gray-400">{{ dataStatus }}</p>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ health?.details || status?.details || 'Chưa có dữ liệu health.' }}</p>
        </div>

        <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Run mới nhất</p>
          <p class="mt-3 font-mono text-lg font-bold text-gray-800 dark:text-white/90">{{ latestRunId }}</p>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ formatDateTime(status?.last_run_time || health?.latest_run?.completed_at || null) }}</p>
        </div>

        <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Rows / Symbols</p>
          <p class="mt-3 text-2xl font-bold text-brand-600 dark:text-brand-400">{{ formatNumber(latestRowCount) }}</p>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ latestSymbols.length }} mã · {{ dateRangeLabel }}</p>
        </div>

        <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Freshness / Disk</p>
          <p class="mt-3 text-2xl font-bold text-emerald-600 dark:text-emerald-400">{{ ageLabel }}</p>
          <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ diskLabel }}</p>
        </div>
      </div>

      <div class="grid gap-4 xl:grid-cols-3">
        <div
          v-for="phase in pipelinePhases"
          :key="phase.key"
          class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]"
        >
          <div class="flex items-start justify-between gap-3">
            <div>
              <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">{{ phase.key }}</p>
              <h3 class="mt-1 text-base font-semibold text-gray-800 dark:text-white/90">{{ phase.title }}</h3>
            </div>
            <div class="flex flex-col items-end gap-2">
              <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="phase.badgeClass">{{ phase.badge }}</span>
              <span class="font-mono text-xs text-gray-500 dark:text-gray-400">{{ phaseDurationLabel(phase.key) }}</span>
            </div>
          </div>
          <ul class="mt-4 space-y-3">
            <li v-for="item in phase.items" :key="item" class="flex gap-3 text-sm text-gray-600 dark:text-gray-400">
              <span class="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500"></span>
              <span>{{ item }}</span>
            </li>
          </ul>
        </div>
      </div>

      <div class="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
        <div class="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <div class="border-b border-gray-100 px-6 py-4 dark:border-gray-800">
            <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">Dữ liệu trong snapshot mới nhất</h3>
            <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
              Phân nhóm theo cột đã ghi vào processed parquet và cache backend.
            </p>
          </div>

          <div class="grid gap-3 p-5 sm:grid-cols-2">
            <div
              v-for="group in columnGroups"
              :key="group.key"
              class="rounded-xl border border-gray-100 bg-gray-50 p-4 dark:border-gray-800 dark:bg-gray-800/60"
            >
              <div class="flex items-center justify-between gap-3">
                <h4 class="font-semibold text-gray-800 dark:text-gray-100">{{ group.label }}</h4>
                <span class="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-gray-600 dark:bg-gray-900 dark:text-gray-300">
                  {{ group.columns.length }}
                </span>
              </div>
              <p class="mt-2 text-xs leading-5 text-gray-500 dark:text-gray-400">{{ group.description }}</p>
              <div class="mt-3 flex flex-wrap gap-2">
                <span
                  v-for="column in group.columns.slice(0, 8)"
                  :key="column"
                  class="rounded-md bg-white px-2 py-1 font-mono text-[11px] text-gray-600 dark:bg-gray-900 dark:text-gray-300"
                >
                  {{ column }}
                </span>
                <span v-if="group.columns.length > 8" class="rounded-md px-2 py-1 text-[11px] text-gray-500 dark:text-gray-400">
                  +{{ group.columns.length - 8 }} cột
                </span>
              </div>
            </div>
          </div>
        </div>

        <div class="space-y-6">
          <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">Làm sạch & chất lượng</h3>
            <div class="mt-3 rounded-xl px-4 py-3 text-sm" :class="qualityStatusClass">
              Contract: {{ quality.status || 'unknown' }}
              <span v-if="quality.warnings?.length">· {{ quality.warnings.length }} cảnh báo</span>
              <span v-if="quality.errors?.length">· {{ quality.errors.length }} lỗi</span>
            </div>
            <div class="mt-4 grid gap-3 sm:grid-cols-3 xl:grid-cols-1">
              <div class="rounded-xl bg-gray-50 p-4 dark:bg-gray-800/60">
                <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Outliers</p>
                <p class="mt-1 text-xl font-bold text-gray-800 dark:text-white/90">{{ formatNumber(quality.outlier_count) }}</p>
              </div>
              <div class="rounded-xl bg-gray-50 p-4 dark:bg-gray-800/60">
                <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Duplicate rows</p>
                <p class="mt-1 text-xl font-bold text-gray-800 dark:text-white/90">{{ formatNumber(quality.duplicate_rows) }}</p>
              </div>
              <div class="rounded-xl bg-gray-50 p-4 dark:bg-gray-800/60">
                <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Cột còn thiếu</p>
                <p class="mt-1 text-xl font-bold text-gray-800 dark:text-white/90">{{ formatNumber(quality.columns_with_missing) }}</p>
              </div>
            </div>
            <ul class="mt-4 space-y-2 text-sm text-gray-600 dark:text-gray-400">
              <li>Dedup theo symbol và ngày giao dịch trước khi ghi snapshot.</li>
              <li>Flag outlier bằng IQR và giữ `is_outlier` để backend/frontend có thể lọc hoặc cảnh báo.</li>
              <li>Fundamental merge bằng as-of backward để tránh look-ahead bias.</li>
              <li>News được gộp title/description, loại trùng, forward-fill khi cấu hình cho phép.</li>
            </ul>
            <div v-if="quality.errors?.length || quality.warnings?.length" class="mt-4 space-y-2 text-xs">
              <p
                v-for="item in [...(quality.errors || []), ...(quality.warnings || [])].slice(0, 4)"
                :key="item"
                class="rounded-lg bg-gray-50 px-3 py-2 text-gray-600 dark:bg-gray-800 dark:text-gray-300"
              >
                {{ item }}
              </p>
            </div>
          </div>

          <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">Load targets</h3>
            <div class="mt-4 space-y-3">
              <div v-for="target in loadTargets" :key="target.name" class="flex items-start justify-between gap-3 rounded-xl bg-gray-50 p-3 dark:bg-gray-800/60">
                <div>
                  <p class="font-mono text-sm font-semibold text-gray-800 dark:text-gray-100">{{ target.name }}</p>
                  <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ target.description }}</p>
                </div>
                <span class="rounded-full bg-white px-2.5 py-1 text-xs text-gray-500 dark:bg-gray-900 dark:text-gray-400">{{ target.kind }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div class="border-b border-gray-100 px-6 py-4 dark:border-gray-800">
          <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">Lịch sử chạy ETL</h3>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full min-w-[860px]">
            <thead class="bg-gray-50 dark:bg-gray-800/80">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Run ID</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Trạng thái</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thời gian</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Rows</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Symbols</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Output</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-for="run in runs" :key="run.run_id" class="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                <td class="px-6 py-4 font-mono text-sm text-gray-700 dark:text-gray-300">{{ run.run_id }}</td>
                <td class="px-6 py-4">
                  <span class="rounded-full px-3 py-1 text-xs font-semibold" :class="runStatusClass(run.status)">
                    {{ run.status }}
                  </span>
                  <p v-if="Object.keys(run.errors || {}).length" class="mt-2 max-w-[240px] text-xs text-error-600 dark:text-error-300">
                    {{ Object.values(run.errors)[0] }}
                  </p>
                  <p v-else-if="Object.keys(run.extract_errors || {}).length" class="mt-2 max-w-[240px] text-xs text-warning-600 dark:text-warning-300">
                    Extract soft failures: {{ Object.keys(run.extract_errors || {}).length }}
                  </p>
                </td>
                <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">
                  <div>{{ formatDateTime(run.started_at) }}</div>
                  <div class="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{{ formatDuration(run.duration_seconds) }}</div>
                  <div class="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{{ run.run_mode || 'full' }} · {{ run.effective_start_date || '?' }} → {{ run.effective_end_date || '?' }}</div>
                </td>
                <td class="px-6 py-4 text-right font-mono text-sm text-gray-700 dark:text-gray-300">{{ formatNumber(run.row_count) }}</td>
                <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">{{ formatSymbols(run.symbols) }}</td>
                <td class="px-6 py-4 max-w-[260px] truncate font-mono text-xs text-gray-500 dark:text-gray-400">{{ run.output_file || 'metadata only' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <div v-if="!runs.length" class="px-6 py-10 text-center text-gray-500 dark:text-gray-400">
          Chưa có run metadata.
        </div>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  getEtlHealth,
  getEtlRuns,
  getEtlStatus,
  triggerEtlRun,
  type EtlHealthResponse,
  type EtlRunMetadata,
  type EtlStatusResponse,
} from '@/services/authApi'

const status = ref<EtlStatusResponse | null>(null)
const health = ref<EtlHealthResponse | null>(null)
const runs = ref<EtlRunMetadata[]>([])
const loading = ref(true)
const triggering = ref(false)
const error = ref('')
const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')

const pipelinePhases = [
  {
    key: 'Extract',
    title: 'Lấy dữ liệu nguồn',
    badge: 'E',
    badgeClass: 'bg-sky-50 text-sky-700 dark:bg-sky-500/15 dark:text-sky-300',
    items: [
      'Giá OHLCV theo ngày từ vnstock cho danh sách symbols cấu hình.',
      'Company overview, báo cáo tài chính, news/events và Google News.',
      'Macro indices như VNINDEX, VN30, HNXINDEX, UPCOMINDEX.',
      'Tick/intraday từ Data Lake hoặc Redis khi bật tick EOD.',
    ],
  },
  {
    key: 'Transform',
    title: 'Chuẩn hóa và làm sạch',
    badge: 'T',
    badgeClass: 'bg-amber-50 text-amber-700 dark:bg-amber-500/15 dark:text-amber-300',
    items: [
      'Ép schema cuối pipeline, dedup theo khóa thời gian và symbol.',
      'Gắn cờ outlier bằng IQR, giữ dữ liệu gốc để audit thay vì xóa mù.',
      'Tính SMA, EMA, RSI, MACD, Bollinger Bands, volume SMA và ATR.',
      'Merge fundamental bằng as-of backward để không dùng dữ liệu tương lai.',
    ],
  },
  {
    key: 'Load',
    title: 'Ghi snapshot và cache',
    badge: 'L',
    badgeClass: 'bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300',
    items: [
      'Ghi processed parquet kèm checksum và metadata sidecar JSON.',
      'Cập nhật by_symbol/latest.parquet để đọc nhanh theo từng mã.',
      'Load vào MySQL cache tables cho backend API và frontend.',
      'Warmup cache backend sau ETL khi scheduler chạy trong FastAPI.',
    ],
  },
]

const loadTargets = [
  { name: 'lake/processed/market_data_*.parquet', kind: 'Parquet', description: 'Dataset hợp nhất sau transform, dùng cho audit và batch model sau này.' },
  { name: 'lake/processed/by_symbol/*/latest.parquet', kind: 'Parquet', description: 'Snapshot mới nhất theo từng symbol, tối ưu đọc lẻ.' },
  { name: 'lake/gold/market_features/run_id=*/data.parquet', kind: 'Gold', description: 'Canonical feature table theo run, dùng cho ML, audit và downstream batch jobs.' },
  { name: 'lake/gold/market_features/latest.parquet', kind: 'Gold', description: 'Alias mới nhất của feature table đã validate, không phụ thuộc legacy processed path.' },
  { name: 'lake/gold/market_features/by_symbol/symbol=*/latest.parquet', kind: 'Gold', description: 'Partition đọc nhanh theo từng mã trong layout lake chuẩn.' },
  { name: 'daily_ohlcv', kind: 'MySQL', description: 'Giá ngày đã chuẩn hóa, dùng cho chart và API lịch sử.' },
  { name: 'company_overview_cache', kind: 'MySQL', description: 'Thông tin doanh nghiệp và metadata ngành.' },
  { name: 'financial_report_cache', kind: 'MySQL', description: 'Bảng cân đối, kết quả kinh doanh, lưu chuyển tiền tệ, chỉ số tài chính.' },
  { name: 'news_cache / events_cache', kind: 'MySQL', description: 'Tin tức, sự kiện doanh nghiệp đã chuẩn hóa payload.' },
  { name: 'technical_cache', kind: 'MySQL', description: 'Chỉ báo kỹ thuật đã tính sẵn cho backend analysis.' },
]

const latestSnapshot = computed(() => health.value?.latest_snapshot || null)
const dataStatus = computed(() => status.value?.data_status || health.value?.data_status || 'SNAPSHOT_NOT_BUILT')
const latestRunId = computed(() => status.value?.last_run_id || health.value?.latest_run?.run_id || latestSnapshot.value?.run_id || 'N/A')
const latestRowCount = computed(() => status.value?.row_count || health.value?.latest_run?.row_count || latestSnapshot.value?.row_count || 0)
const latestSymbols = computed(() => status.value?.symbols?.length ? status.value.symbols : latestSnapshot.value?.symbols || [])
const columns = computed(() => latestSnapshot.value?.columns || [])
const quality = computed(() => (
  health.value?.latest_run?.quality_report
  || latestSnapshot.value?.quality_summary
  || { status: 'unknown', outlier_count: 0, duplicate_rows: 0, columns_with_missing: 0, top_missing_columns: {} }
))
const latestPhaseDurations = computed(() => health.value?.latest_run?.phase_durations || {})

const qualityStatusClass = computed(() => {
  if (quality.value.status === 'passed') {
    return 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300'
  }
  if (quality.value.status === 'failed') {
    return 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-300'
  }
  return 'bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-300'
})

const statusDotClass = computed(() => {
  const current = status.value?.status || health.value?.status
  if (current === 'healthy' || current === 'success') return 'bg-success-500'
  if (current === 'stale' || current === 'running') return 'bg-warning-500'
  return 'bg-error-500'
})

const noticeClass = computed(() =>
  noticeType.value === 'success'
    ? 'border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-300'
    : 'border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300',
)

const dateRangeLabel = computed(() => {
  const range = latestSnapshot.value?.date_range
  if (!range?.min && !range?.max) return 'chưa có date range'
  return `${range.min || '?'} → ${range.max || '?'}`
})

const ageLabel = computed(() => {
  const age = health.value?.age_hours
  if (age === null || age === undefined) return 'N/A'
  if (age < 1) return `${Math.round(age * 60)} phút`
  return `${age.toFixed(1)} giờ`
})

const diskLabel = computed(() => {
  const disk = health.value?.disk
  if (!disk || disk.free_ratio === null || disk.free_ratio === undefined) return 'Disk: N/A'
  return `Free disk ${(disk.free_ratio * 100).toFixed(1)}%`
})

const columnGroups = computed(() => {
  const all = columns.value
  const pick = (matcher: (column: string) => boolean) => all.filter(matcher)
  return [
    {
      key: 'identity',
      label: 'Định danh',
      description: 'Khóa symbol, ngày và metadata doanh nghiệp.',
      columns: pick((c) => ['symbol', 'company_name', 'sector', 'industry', 'data_date'].includes(c)),
    },
    {
      key: 'price',
      label: 'Giá & khối lượng',
      description: 'OHLCV đã chuẩn hóa cho daily chart và cache.',
      columns: pick((c) => ['open_price', 'high_price', 'low_price', 'close_price', 'volume'].includes(c)),
    },
    {
      key: 'technical',
      label: 'Chỉ báo kỹ thuật',
      description: 'Feature kỹ thuật tính từ chuỗi giá.',
      columns: pick((c) => ['sma_', 'ema_', 'rsi_', 'macd', 'bb_', 'vol_sma', 'atr_'].some((prefix) => c.startsWith(prefix))),
    },
    {
      key: 'fundamental',
      label: 'Fundamental',
      description: 'Chỉ số doanh nghiệp và báo cáo tài chính đã merge theo thời gian.',
      columns: pick((c) => c.startsWith('micro_') || c.startsWith('fund_')),
    },
    {
      key: 'macro',
      label: 'Macro indices',
      description: 'Bối cảnh thị trường theo chỉ số.',
      columns: pick((c) => c.startsWith('macro_')),
    },
    {
      key: 'news',
      label: 'News & events',
      description: 'Headline nội bộ và Google News đã gom/trừ trùng.',
      columns: pick((c) => c.includes('news') || c.includes('headline') || c.includes('event')),
    },
    {
      key: 'quality',
      label: 'Quality flags',
      description: 'Cờ kiểm soát chất lượng sau validate.',
      columns: pick((c) => c === 'is_outlier' || c.startsWith('quality_')),
    },
  ]
})

function formatNumber(value: number | undefined | null): string {
  return new Intl.NumberFormat('vi-VN').format(value || 0)
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return 'N/A'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('vi-VN', {
    dateStyle: 'short',
    timeStyle: 'medium',
  }).format(date)
}

function formatDuration(seconds: number | undefined): string {
  if (!seconds) return 'N/A'
  if (seconds < 60) return `${seconds.toFixed(1)} giây`
  return `${(seconds / 60).toFixed(1)} phút`
}

function phaseDurationLabel(phase: string): string {
  return formatDuration(latestPhaseDurations.value[phase.toLowerCase()])
}

function formatSymbols(symbols: string[]): string {
  if (!symbols?.length) return 'N/A'
  if (symbols.length <= 6) return symbols.join(', ')
  return `${symbols.slice(0, 6).join(', ')} +${symbols.length - 6}`
}

function runStatusClass(runStatus: string): string {
  if (runStatus === 'success') return 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300'
  if (runStatus === 'running') return 'bg-warning-50 text-warning-700 dark:bg-warning-500/15 dark:text-warning-300'
  return 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-300'
}

function showNotice(message: string, type: 'success' | 'error' = 'success'): void {
  notice.value = message
  noticeType.value = type
}

async function loadMonitor(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const [statusData, healthData, runsData] = await Promise.all([
      getEtlStatus(),
      getEtlHealth(),
      getEtlRuns(10),
    ])
    status.value = statusData
    health.value = healthData
    runs.value = runsData.runs
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không tải được dữ liệu ETL monitor.'
  } finally {
    loading.value = false
  }
}

async function triggerManualRun(): Promise<void> {
  const accepted = window.confirm('Chạy ETL thủ công với cấu hình mặc định hiện tại? Tác vụ này có thể mất vài phút.')
  if (!accepted) return

  triggering.value = true
  try {
    const result = await triggerEtlRun()
    showNotice(`Da khoi chay ETL ${result.run_id} cho ${result.symbols.length} ma (${result.data_status || 'ETL_RUNNING'}).`, 'success')
    await loadMonitor()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không khởi chạy được ETL.', 'error')
  } finally {
    triggering.value = false
  }
}

onMounted(loadMonitor)
</script>
