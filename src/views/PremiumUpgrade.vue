<template>
  <AdminLayout>
    <div class="space-y-6">
      <PageHeader title="⭐ Nâng cấp Premium" />

      <section class="rounded-2xl border border-gray-200 bg-white p-6 dark:border-gray-800 dark:bg-white/[0.03] md:p-8">
        <div class="mx-auto max-w-3xl text-center">
          <span class="inline-flex items-center rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700 dark:bg-brand-500/10 dark:text-brand-300">
            Premium AI
          </span>
          <h1 class="mt-4 text-3xl font-bold text-gray-800 dark:text-white/90">Nâng cấp gói Premium</h1>
          <p class="mx-auto mt-3 max-w-2xl text-sm leading-6 text-gray-500 dark:text-gray-400">
            Mở khóa AI Trading-R1 để nhận phân tích chuyên sâu, khuyến nghị mua/bán và các tính năng nâng cao khác.
          </p>
        </div>

        <div class="mx-auto mt-8 grid max-w-4xl gap-6 lg:grid-cols-[1.2fr_0.8fr]">
          <div class="rounded-2xl border border-gray-200 bg-gray-50 p-5 dark:border-gray-800 dark:bg-gray-800/40">
            <h2 class="text-lg font-semibold text-gray-800 dark:text-gray-200">Quyền lợi</h2>
            <ul class="mt-4 space-y-3">
              <li v-for="feature in features" :key="feature" class="flex items-start gap-3 text-sm text-gray-600 dark:text-gray-300">
                <span class="mt-0.5 inline-flex h-5 w-5 flex-none items-center justify-center rounded-full bg-success-50 text-success-600 dark:bg-success-500/10 dark:text-success-400">✓</span>
                <span>{{ feature }}</span>
              </li>
            </ul>
          </div>

          <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <p class="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">Gói Premium AI</p>
            <div class="mt-3 flex items-baseline gap-1">
              <span class="text-4xl font-bold text-brand-600">{{ formatPrice(paymentInfo?.amount || 99000) }}</span>
              <span class="text-sm text-gray-500 dark:text-gray-400">₫ / tháng</span>
            </div>

            <div v-if="loading" class="py-10 text-center">
              <div class="mx-auto h-10 w-10 animate-spin rounded-full border-b-2 border-brand-500"></div>
              <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">Đang tải thông tin gói...</p>
            </div>

            <div v-else-if="paymentInfo" class="mt-5 space-y-4">
              <div class="rounded-xl border border-brand-100 bg-brand-50/50 p-4 text-sm text-gray-600 dark:border-brand-500/20 dark:bg-brand-500/10 dark:text-gray-300">
                Bạn sẽ đi qua trang checkout trước khi chuyển sang cổng thanh toán SePay.
              </div>

              <button
                @click="goToCheckout"
                class="inline-flex w-full items-center justify-center rounded-xl bg-brand-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-brand-600"
              >
                Tiếp tục đến Checkout
              </button>
            </div>

            <div v-else-if="error" class="mt-5 text-center">
              <p class="text-sm text-error-600 dark:text-error-400">{{ error }}</p>
              <button @click="loadPaymentInfo" class="mt-3 text-sm font-medium text-brand-600 hover:text-brand-700">Thử lại</button>
            </div>
          </div>
        </div>
      </section>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { getPremiumPaymentInfo, type PaymentInfo } from '@/services/authApi'

const router = useRouter()
const paymentInfo = ref<PaymentInfo | null>(null)
const loading = ref(true)
const error = ref('')

const features = [
  'Phân tích AI Trading-R1 không giới hạn',
  'Khuyến nghị Mua/Bán hàng ngày',
  'Chain-of-Thought reasoning chuyên sâu',
  'Xem lịch sử backtest model',
  'Hỗ trợ tư vấn từ Admin',
  'Truy cập sớm tính năng mới',
]

function formatPrice(n: number): string {
  return n.toLocaleString('vi-VN')
}

async function loadPaymentInfo() {
  loading.value = true
  error.value = ''
  try {
    paymentInfo.value = await getPremiumPaymentInfo()
  } catch (e: any) {
    error.value = e.message || 'Không thể tải thông tin thanh toán'
  } finally {
    loading.value = false
  }
}

function goToCheckout() {
  router.push('/premium/checkout')
}

onMounted(loadPaymentInfo)
</script>
