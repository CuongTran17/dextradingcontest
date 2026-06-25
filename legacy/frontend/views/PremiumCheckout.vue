<template>
  <AdminLayout>
    <div class="space-y-6">
      <PageHeader title="Checkout Premium" />

      <div class="mx-auto max-w-5xl space-y-6">
        <div>
          <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Xác nhận thanh toán Premium</h1>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Kiểm tra lại gói, sau đó chuyển qua SePay để hoàn tất.
          </p>
        </div>

        <div class="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <section class="lg:col-span-2 rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h2 class="mb-4 text-lg font-semibold text-gray-800 dark:text-gray-200">Phương thức thanh toán</h2>
            <label class="flex items-start gap-3 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/40">
              <input checked readonly class="mt-1" type="radio" />
              <div>
                <p class="font-semibold text-gray-800 dark:text-gray-200">SePay</p>
                <p class="text-sm text-gray-500 dark:text-gray-400">
                  Thanh toán qua chuyển khoản ngân hàng hoặc QR code.
                </p>
              </div>
            </label>

            <div class="mt-5 rounded-xl border border-success-200 bg-success-50 p-4 dark:border-success-700/40 dark:bg-success-500/10">
              <p class="text-sm font-medium text-success-700 dark:text-success-300">Thanh toán an toàn qua SePay</p>
              <p class="mt-1 text-sm text-success-700/80 dark:text-success-400">
                Hệ thống sẽ tự động kích hoạt Premium sau khi SePay xác nhận giao dịch.
              </p>
            </div>
          </section>

          <aside class="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
            <h3 class="mb-4 text-base font-semibold text-gray-800 dark:text-gray-200">Đơn hàng của bạn</h3>

            <label class="mb-4 block text-sm text-gray-500 dark:text-gray-400">
              Mã khuyến mãi
              <input
                v-model.trim="promoCode"
                type="text"
                class="mt-1 w-full rounded-xl border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 uppercase outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                placeholder="PREMIUM30"
              />
            </label>

            <div v-if="checkoutData?.flash_sale_title" class="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-300">
              Flash sale đang áp dụng: <span class="font-semibold">{{ checkoutData.flash_sale_title }}</span>
            </div>

            <div class="space-y-3 text-sm">
              <div class="flex items-center justify-between">
                <span class="text-gray-500 dark:text-gray-400">Gói</span>
                <span class="font-medium text-gray-800 dark:text-gray-200">Premium AI</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-gray-500 dark:text-gray-400">Giá gốc</span>
                <span class="font-medium text-gray-800 dark:text-gray-200">{{ formatPrice(checkoutData?.original_amount || amount) }}₫</span>
              </div>
              <div class="flex items-center justify-between" v-if="checkoutData?.discount_amount">
                <span class="text-gray-500 dark:text-gray-400">Giảm giá</span>
                <span class="font-medium text-success-600 dark:text-success-400">-{{ formatPrice(checkoutData.discount_amount) }}₫</span>
              </div>
              <div class="flex items-center justify-between">
                <span class="text-gray-500 dark:text-gray-400">Thời hạn</span>
                <span class="font-medium text-gray-800 dark:text-gray-200">30 ngày</span>
              </div>
              <div class="flex items-center justify-between border-t border-gray-100 pt-3 dark:border-gray-800">
                <span class="font-medium text-gray-600 dark:text-gray-300">Tổng cộng</span>
                <span class="text-lg font-bold text-brand-600">{{ formatPrice(amount) }}₫</span>
              </div>
            </div>

            <button
              class="mt-6 w-full rounded-xl bg-brand-500 px-4 py-3 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
              :disabled="loading"
              @click="handleSePayCheckout"
            >
              {{ loading ? 'Đang chuyển tới SePay...' : `Thanh toán SePay - ${formatPrice(amount)}₫` }}
            </button>

            <button
              class="mt-3 w-full rounded-xl border border-gray-300 px-4 py-3 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              @click="goBack"
            >
              Quay lại
            </button>
          </aside>
        </div>

        <p v-if="error" class="text-sm text-error-600 dark:text-error-400">{{ error }}</p>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import PageHeader from '@/components/layout/PageHeader.vue'
import { createPremiumSePayCheckout, type PremiumCheckoutResponse } from '@/services/authApi'

const router = useRouter()
const loading = ref(false)
const error = ref('')
const checkoutData = ref<PremiumCheckoutResponse | null>(null)
const amount = ref(99000)
const promoCode = ref('')

function formatPrice(n: number): string {
  return n.toLocaleString('vi-VN')
}

async function handleSePayCheckout() {
  loading.value = true
  error.value = ''

  try {
    const data = await createPremiumSePayCheckout({ promo_code: promoCode.value || null })
    checkoutData.value = data
    amount.value = data.amount

    // Create a temporary form in the DOM and submit it
    const form = document.createElement('form')
    form.method = 'POST'
    form.action = data.checkoutURL
    form.style.display = 'none'

    for (const [key, value] of Object.entries(data.checkoutFormFields)) {
      const input = document.createElement('input')
      input.type = 'hidden'
      input.name = key
      input.value = String(value)
      form.appendChild(input)
    }

    document.body.appendChild(form)
    form.submit()
    document.body.removeChild(form)
  } catch (e: any) {
    error.value = e.message || 'Không thể tạo thanh toán SePay'
    loading.value = false
  }
}

function goBack() {
  router.push('/premium')
}
</script>
