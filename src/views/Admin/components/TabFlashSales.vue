<template>
  <div class="space-y-6">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">Flash sale management</p>
          <h2 class="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">Flash Sale</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Tạo ưu đãi hệ thống tự động áp dụng vào giá checkout Premium trong khoảng thời gian đã đặt.
          </p>
        </div>

        <button
          class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
          :disabled="loading"
          @click="loadFlashSales"
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
          {{ editingId ? 'Cập nhật Flash Sale' : 'Tạo Flash Sale mới' }}
        </h3>
        <p class="mt-1 text-xs text-gray-500 dark:text-gray-400">Ưu đãi này sẽ tự động cộng vào checkout nếu đang trong thời gian hiệu lực.</p>

        <form class="mt-4 space-y-3" @submit.prevent="submitFlashSale">
          <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Tiêu đề
            <input
              v-model.trim="form.title"
              maxlength="255"
              class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              placeholder="Flash Sale cuối tuần"
              required
            />
          </label>

          <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
            Mô tả
            <textarea
              v-model.trim="form.description"
              rows="2"
              class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              placeholder="Ưu đãi tự động cho Premium"
            ></textarea>
          </label>

          <div class="grid gap-3 sm:grid-cols-2">
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Giảm (%)
              <input
                v-model.number="form.discount_percentage"
                type="number"
                min="1"
                max="90"
                step="0.01"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                required
              />
            </label>
            <label class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
              Trạng thái
              <select
                v-model="form.is_active"
                class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
              >
                <option :value="true">Bật</option>
                <option :value="false">Tắt</option>
              </select>
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
            Bật ưu đãi ngay sau khi lưu
          </label>

          <div class="flex gap-2 pt-1">
            <button
              type="submit"
              class="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
              :disabled="saving"
            >
              {{ saving ? 'Đang lưu...' : editingId ? 'Lưu cập nhật' : 'Tạo flash sale' }}
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

        <div v-else-if="flashSales.length === 0" class="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
          Chưa có flash sale nào.
        </div>

        <div v-else class="overflow-hidden">
          <table class="w-full min-w-[900px]">
            <thead class="bg-gray-50 dark:bg-gray-800/80">
              <tr>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Tiêu đề</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Giảm</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thời gian</th>
                <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Trạng thái</th>
                <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thao tác</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
              <tr v-for="sale in flashSales" :key="sale.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/60">
                <td class="px-6 py-4 align-top">
                  <div class="font-semibold text-gray-800 dark:text-gray-200">{{ sale.title }}</div>
                  <div class="mt-1 text-xs text-gray-500 dark:text-gray-400">{{ sale.description || 'Không có mô tả' }}</div>
                </td>
                <td class="px-6 py-4 align-top text-sm text-gray-600 dark:text-gray-400">
                  {{ sale.discount_percentage }}%
                </td>
                <td class="px-6 py-4 align-top text-sm text-gray-600 dark:text-gray-400">
                  <div>Từ: {{ formatDate(sale.starts_at) }}</div>
                  <div>Đến: {{ formatDate(sale.ends_at) }}</div>
                </td>
                <td class="px-6 py-4 align-top">
                  <span
                    class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                    :class="sale.is_active ? 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300' : 'bg-gray-100 text-gray-700 dark:bg-gray-700/60 dark:text-gray-200'"
                  >
                    {{ sale.is_active ? 'Đang bật' : 'Đang tắt' }}
                  </span>
                </td>
                <td class="px-6 py-4 align-top text-right">
                  <div class="flex justify-end gap-2">
                    <button
                      class="rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
                      :disabled="processingId === sale.id"
                      @click="startEdit(sale)"
                    >
                      Sửa
                    </button>
                    <button
                      class="rounded-lg px-3 py-2 text-xs font-semibold text-white transition disabled:cursor-not-allowed disabled:opacity-60"
                      :class="sale.is_active ? 'bg-warning-500 hover:bg-warning-600' : 'bg-success-500 hover:bg-success-600'"
                      :disabled="processingId === sale.id"
                      @click="toggleStatus(sale)"
                    >
                      {{ sale.is_active ? 'Tắt sale' : 'Bật sale' }}
                    </button>
                    <button
                      class="rounded-lg bg-error-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-error-600 disabled:cursor-not-allowed disabled:opacity-60"
                      :disabled="processingId === sale.id"
                      @click="removeFlashSale(sale)"
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
  createFlashSale,
  deleteFlashSale,
  getAdminFlashSales,
  setFlashSaleStatus,
  updateFlashSale,
  type FlashSaleConfig,
  type FlashSalePayload,
} from '@/services/authApi'

type FlashSaleForm = {
  title: string
  description: string
  discount_percentage: number | null
  starts_at: string
  ends_at: string
  is_active: boolean
}

const flashSales = ref<FlashSaleConfig[]>([])
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')
const editingId = ref<number | null>(null)
const processingId = ref<number | null>(null)

const form = ref<FlashSaleForm>(buildEmptyForm())

const noticeClass = computed(() =>
  noticeType.value === 'success'
    ? 'border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-300'
    : 'border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300',
)

function buildEmptyForm(): FlashSaleForm {
  return {
    title: '',
    description: '',
    discount_percentage: null,
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

function toPayload(): FlashSalePayload {
  return {
    title: form.value.title.trim(),
    description: form.value.description.trim() || null,
    discount_percentage: Number(form.value.discount_percentage || 0),
    starts_at: form.value.starts_at ? new Date(form.value.starts_at).toISOString() : null,
    ends_at: form.value.ends_at ? new Date(form.value.ends_at).toISOString() : null,
    is_active: form.value.is_active,
  }
}

async function loadFlashSales(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    const data = await getAdminFlashSales()
    flashSales.value = data.flash_sales
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không tải được danh sách flash sale.'
  } finally {
    loading.value = false
  }
}

async function submitFlashSale(): Promise<void> {
  if (!form.value.title || !form.value.discount_percentage) {
    showNotice('Vui lòng nhập tiêu đề và tỷ lệ giảm.', 'error')
    return
  }

  if (form.value.discount_percentage <= 0 || form.value.discount_percentage > 90) {
    showNotice('Tỷ lệ giảm phải từ 1 đến 90%.', 'error')
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
      await updateFlashSale(editingId.value, payload)
      showNotice('Đã cập nhật flash sale.', 'success')
    } else {
      await createFlashSale(payload)
      showNotice('Đã tạo flash sale.', 'success')
    }
    resetForm()
    await loadFlashSales()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể lưu flash sale.', 'error')
  } finally {
    saving.value = false
  }
}

function startEdit(sale: FlashSaleConfig): void {
  editingId.value = sale.id
  form.value = {
    title: sale.title,
    description: sale.description || '',
    discount_percentage: sale.discount_percentage,
    starts_at: toDatetimeLocal(sale.starts_at),
    ends_at: toDatetimeLocal(sale.ends_at),
    is_active: sale.is_active,
  }
}

function resetForm(): void {
  editingId.value = null
  form.value = buildEmptyForm()
}

async function toggleStatus(sale: FlashSaleConfig): Promise<void> {
  processingId.value = sale.id
  try {
    await setFlashSaleStatus(sale.id, !sale.is_active)
    showNotice(`Đã ${sale.is_active ? 'tắt' : 'bật'} flash sale.`, 'success')
    await loadFlashSales()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể cập nhật trạng thái flash sale.', 'error')
  } finally {
    processingId.value = null
  }
}

async function removeFlashSale(sale: FlashSaleConfig): Promise<void> {
  if (!window.confirm(`Xóa flash sale ${sale.title}?`)) {
    return
  }

  processingId.value = sale.id
  try {
    await deleteFlashSale(sale.id)
    if (editingId.value === sale.id) {
      resetForm()
    }
    showNotice('Đã xóa flash sale.', 'success')
    await loadFlashSales()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể xóa flash sale.', 'error')
  } finally {
    processingId.value = null
  }
}

onMounted(() => {
  loadFlashSales()
})
</script>
