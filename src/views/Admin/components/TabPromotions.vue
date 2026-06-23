<template>
  <div class="space-y-6">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Promotion management</p>
          <h2 class="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">Mã khuyến mãi</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Tạo mã giảm giá cho gói premium, bật tắt nhanh và kiểm soát điều kiện áp dụng.
          </p>
        </div>

        <button
          class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          :disabled="loading"
          @click="loadPromotions"
        >
          Làm mới
        </button>
      </div>

      <div v-if="notice" class="mt-4 rounded-xl border px-4 py-3 text-sm" :class="noticeClass">
        {{ notice }}
      </div>
    </div>

    <div class="grid gap-6 xl:grid-cols-[380px_minmax(0,1fr)]">
      <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <h3 class="text-base font-semibold text-gray-800 dark:text-white/90">
          {{ editingId ? 'Cập nhật mã khuyến mãi' : 'Tạo mã khuyến mãi mới' }}
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Hỗ trợ giảm theo % hoặc giảm tiền cố định.</p>

        <form class="mt-4 space-y-3" @submit.prevent="submitPromotion">
          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Mã
              <input
                v-model.trim="form.code"
                maxlength="50"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 uppercase outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                placeholder="PREMIUM30"
                required
              />
            </label>
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Loại giảm
              <select
                v-model="form.discount_type"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              >
                <option value="percentage">Theo phần trăm</option>
                <option value="fixed">Giảm tiền cố định</option>
              </select>
            </label>
          </div>

          <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Tiêu đề
            <input
              v-model.trim="form.title"
              maxlength="255"
              class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              placeholder="Ưu đãi đầu tháng"
              required
            />
          </label>

          <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Mô tả
            <textarea
              v-model.trim="form.description"
              rows="2"
              class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              placeholder="Áp dụng cho đăng ký premium mới"
            ></textarea>
          </label>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Giá trị giảm
              <input
                v-model.number="form.discount_value"
                type="number"
                min="1"
                step="0.01"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                required
              />
            </label>
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Số lượt tối đa
              <input
                v-model.number="form.usage_limit"
                type="number"
                min="1"
                step="1"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                placeholder="Bỏ trống = không giới hạn"
              />
            </label>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Đơn tối thiểu
              <input
                v-model.number="form.min_order_amount"
                type="number"
                min="0"
                step="0.01"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              />
            </label>
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Giảm tối đa
              <input
                v-model.number="form.max_discount_amount"
                type="number"
                min="1"
                step="0.01"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              />
            </label>
          </div>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Bắt đầu
              <input
                v-model="form.starts_at"
                type="datetime-local"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              />
            </label>
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Kết thúc
              <input
                v-model="form.ends_at"
                type="datetime-local"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              />
            </label>
          </div>

          <label class="inline-flex items-center gap-2 pt-1 text-sm text-gray-600 dark:text-gray-300">
            <input v-model="form.is_active" type="checkbox" class="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500" />
            Bật mã ngay sau khi lưu
          </label>

          <div class="flex gap-2 pt-1">
            <button
              type="submit"
              class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="saving"
            >
              {{ saving ? 'Đang lưu...' : editingId ? 'Lưu cập nhật' : 'Tạo mã' }}
            </button>
            <button
              v-if="editingId"
              type="button"
              class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
              @click="resetForm"
            >
              Hủy sửa
            </button>
          </div>
        </form>
      </div>

      <div class="rounded-2xl border border-gray-200 bg-white shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
        <div v-if="loading" class="flex items-center justify-center py-16">
          <div class="h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
        </div>

        <div v-else-if="error" class="px-6 py-8">
          <div class="rounded-xl border border-error-200 bg-error-50 px-4 py-3 text-sm text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300">
            {{ error }}
          </div>
        </div>

        <div v-else-if="promotions.length === 0" class="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
          Chưa có mã khuyến mãi nào.
        </div>

        <div v-else class="overflow-hidden">
          <table class="w-full min-w-[980px]">
            <thead class="bg-gray-50 dark:bg-gray-800/80">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Mã</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Giá trị</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Điều kiện</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thời gian</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Trạng thái</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thao tác</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-for="promotion in promotions" :key="promotion.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                <td class="px-6 py-4 align-top">
                  <div class="font-semibold text-gray-800 dark:text-gray-200">{{ promotion.code }}</div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ promotion.title }}</div>
                </td>
                <td class="px-6 py-4 align-top text-sm text-gray-600 dark:text-gray-400">
                  <span v-if="promotion.discount_type === 'percentage'">{{ promotion.discount_value }}%</span>
                  <span v-else>{{ formatCurrency(promotion.discount_value) }}</span>
                </td>
                <td class="px-6 py-4 align-top text-sm text-gray-600 dark:text-gray-400">
                  <div>Đơn tối thiểu: {{ formatCurrency(promotion.min_order_amount ?? 0) }}</div>
                  <div>Đã dùng: {{ promotion.used_count }}{{ promotion.usage_limit ? `/${promotion.usage_limit}` : '' }}</div>
                </td>
                <td class="px-6 py-4 align-top text-sm text-gray-600 dark:text-gray-400">
                  <div>Từ: {{ formatDate(promotion.starts_at) }}</div>
                  <div>Đến: {{ formatDate(promotion.ends_at) }}</div>
                </td>
                <td class="px-6 py-4 align-top">
                  <span
                    class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                    :class="promotion.is_active ? 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-700/60 dark:text-gray-200'"
                  >
                    {{ promotion.is_active ? 'Đang bật' : 'Đang tắt' }}
                  </span>
                </td>
                <td class="px-6 py-4 align-top text-right">
                  <div class="flex justify-end gap-2">
                    <button
                      class="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                      :disabled="processingId === promotion.id"
                      @click="startEdit(promotion)"
                    >
                      Sửa
                    </button>
                    <button
                      class="rounded-lg px-3 py-2 text-xs font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
                      :class="promotion.is_active ? 'bg-warning-500 hover:bg-warning-600' : 'bg-success-500 hover:bg-success-600'"
                      :disabled="processingId === promotion.id"
                      @click="toggleStatus(promotion)"
                    >
                      {{ promotion.is_active ? 'Tắt mã' : 'Bật mã' }}
                    </button>
                    <button
                      class="rounded-lg bg-error-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-error-600 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="processingId === promotion.id"
                      @click="removePromotion(promotion)"
                    >
                      Xóa
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  createPromotion,
  deletePromotion,
  getAdminPromotions,
  setPromotionStatus,
  updatePromotion,
  type PromotionCode,
  type PromotionPayload,
} from '@/services/authApi'

type PromotionForm = {
  code: string
  title: string
  description: string
  discount_type: 'percentage' | 'fixed'
  discount_value: number | null
  min_order_amount: number | null
  max_discount_amount: number | null
  usage_limit: number | null
  starts_at: string
  ends_at: string
  is_active: boolean
}

const promotions = ref<PromotionCode[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')
const editingId = ref<number | null>(null)
const processingId = ref<number | null>(null)

const form = ref<PromotionForm>(buildEmptyForm())

const noticeClass = computed(() =>
  noticeType.value === 'success'
    ? 'border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-300'
    : 'border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300',
)

function buildEmptyForm(): PromotionForm {
  return {
    code: '',
    title: '',
    description: '',
    discount_type: 'percentage',
    discount_value: null,
    min_order_amount: null,
    max_discount_amount: null,
    usage_limit: null,
    starts_at: '',
    ends_at: '',
    is_active: true,
  }
}

function toDatetimeLocal(value: string | null): string {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function showNotice(message: string, type: 'success' | 'error' = 'success'): void {
  notice.value = message
  noticeType.value = type
}

function formatDate(value: string | null): string {
  if (!value) return 'Không giới hạn'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Không hợp lệ'
  return date.toLocaleString('vi-VN')
}

function formatCurrency(value: number): string {
  return value.toLocaleString('vi-VN', { style: 'currency', currency: 'VND', maximumFractionDigits: 0 })
}

function toPayload(): PromotionPayload {
  return {
    code: form.value.code.trim().toUpperCase(),
    title: form.value.title.trim(),
    description: form.value.description.trim() || null,
    discount_type: form.value.discount_type,
    discount_value: Number(form.value.discount_value || 0),
    min_order_amount: form.value.min_order_amount || null,
    max_discount_amount: form.value.max_discount_amount || null,
    usage_limit: form.value.usage_limit || null,
    starts_at: form.value.starts_at ? new Date(form.value.starts_at).toISOString() : null,
    ends_at: form.value.ends_at ? new Date(form.value.ends_at).toISOString() : null,
    is_active: form.value.is_active,
  }
}

async function loadPromotions(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const data = await getAdminPromotions()
    promotions.value = data.promotions
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không tải được danh sách khuyến mãi.'
  } finally {
    loading.value = false
  }
}

async function submitPromotion(): Promise<void> {
  if (!form.value.code || !form.value.title || !form.value.discount_value) {
    showNotice('Vui lòng nhập đủ mã, tiêu đề và giá trị giảm.', 'error')
    return
  }

  if (form.value.discount_type === 'percentage' && Number(form.value.discount_value) > 100) {
    showNotice('Giảm theo phần trăm không được vượt quá 100.', 'error')
    return
  }

  if (form.value.starts_at && form.value.ends_at && new Date(form.value.ends_at) < new Date(form.value.starts_at)) {
    showNotice('Thời gian kết thúc phải sau thời gian bắt đầu.', 'error')
    return
  }

  saving.value = true
  try {
    const payload = toPayload()
    if (editingId.value) {
      await updatePromotion(editingId.value, payload)
      showNotice('Đã cập nhật mã khuyến mãi.', 'success')
    } else {
      await createPromotion(payload)
      showNotice('Đã tạo mã khuyến mãi.', 'success')
    }
    resetForm()
    await loadPromotions()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể lưu mã khuyến mãi.', 'error')
  } finally {
    saving.value = false
  }
}

function startEdit(promotion: PromotionCode): void {
  editingId.value = promotion.id
  form.value = {
    code: promotion.code,
    title: promotion.title,
    description: promotion.description || '',
    discount_type: promotion.discount_type,
    discount_value: promotion.discount_value,
    min_order_amount: promotion.min_order_amount,
    max_discount_amount: promotion.max_discount_amount,
    usage_limit: promotion.usage_limit,
    starts_at: toDatetimeLocal(promotion.starts_at),
    ends_at: toDatetimeLocal(promotion.ends_at),
    is_active: promotion.is_active,
  }
}

function resetForm(): void {
  editingId.value = null
  form.value = buildEmptyForm()
}

async function toggleStatus(promotion: PromotionCode): Promise<void> {
  processingId.value = promotion.id
  try {
    await setPromotionStatus(promotion.id, !promotion.is_active)
    showNotice(`Đã ${promotion.is_active ? 'tắt' : 'bật'} mã ${promotion.code}.`, 'success')
    await loadPromotions()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể cập nhật trạng thái mã.', 'error')
  } finally {
    processingId.value = null
  }
}

async function removePromotion(promotion: PromotionCode): Promise<void> {
  if (!window.confirm(`Xóa mã khuyến mãi ${promotion.code}?`)) {
    return
  }

  processingId.value = promotion.id
  try {
    await deletePromotion(promotion.id)
    if (editingId.value === promotion.id) {
      resetForm()
    }
    showNotice(`Đã xóa mã ${promotion.code}.`, 'success')
    await loadPromotions()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể xóa mã khuyến mãi.', 'error')
  } finally {
    processingId.value = null
  }
}

onMounted(() => {
  loadPromotions()
})
</script>
