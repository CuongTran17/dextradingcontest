<template>
  <AdminLayout>
    <div class="space-y-6">
      <div class="mx-auto max-w-3xl">
        <div class="rounded-2xl border border-gray-200 bg-white p-8 text-center shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
          <div
            class="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full text-2xl"
            :class="iconBgClass"
          >
            {{ emoji }}
          </div>
          <h1 class="mb-2 text-2xl font-bold text-gray-800 dark:text-white/90" :class="titleClass">{{ title }}</h1>
          <p class="mb-2 text-sm text-gray-600 dark:text-gray-300">{{ description }}</p>
          <p class="text-sm text-gray-500 dark:text-gray-400">{{ subDescription }}</p>

          <div class="mt-8 flex flex-wrap items-center justify-center gap-3">
            <button
              v-if="status !== 'success'"
              type="button"
              class="rounded-xl bg-brand-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-brand-600"
              @click="goCheckout"
            >
              Quay lại checkout
            </button>
            <button
              type="button"
              class="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              @click="goPremium"
            >
              Về trang Premium
            </button>
            <button
              type="button"
              class="rounded-xl border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              @click="goHome"
            >
              Về trang chủ
            </button>
          </div>
        </div>
    </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { getSubscriptionStatus } from '@/services/authApi'

type ReturnStatus = 'success' | 'cancel' | 'error'

const route = useRoute()
const router = useRouter()
const status = ref<ReturnStatus>('error')

const emoji = computed(() => {
  if (status.value === 'success') return '🎉'
  if (status.value === 'cancel') return '↩️'
  return '❌'
})

const iconBgClass = computed(() => {
  if (status.value === 'success') return 'bg-success-50 text-success-600 dark:bg-success-500/10 dark:text-success-400'
  if (status.value === 'cancel') return 'bg-amber-50 text-amber-600 dark:bg-amber-500/10 dark:text-amber-400'
  return 'bg-error-50 text-error-600 dark:bg-error-500/10 dark:text-error-400'
})

const title = computed(() => {
  if (status.value === 'success') return 'Đang xác nhận thanh toán'
  if (status.value === 'cancel') return 'Bạn đã hủy thanh toán'
  return 'Thanh toán thất bại'
})

const titleClass = computed(() => {
  if (status.value === 'success') return 'text-success-600'
  if (status.value === 'cancel') return 'text-amber-600'
  return 'text-error-600'
})

const description = computed(() => {
  if (status.value === 'success') {
    return 'Hệ thống đang chờ IPN từ SePay và sẽ tự nâng cấp Premium cho bạn.'
  }
  if (status.value === 'cancel') return 'Bạn có thể quay lại checkout bất cứ lúc nào.'
  return 'Đã có lỗi trong quá trình thanh toán. Vui lòng thử lại.'
})

const subDescription = ref('')

async function checkSubscriptionOnce() {
  try {
    const result = await getSubscriptionStatus()
    if (result.is_premium) {
      subDescription.value = 'Tài khoản đã là Premium. Bạn có thể dùng ngay tính năng AI.'
      return true
    }
    return false
  } catch {
    return false
  }
}

async function handleSuccessStatus() {
  subDescription.value = 'Có thể mất 1-2 phút để webhook xử lý xong.'
  const upgraded = await checkSubscriptionOnce()
  if (upgraded) return

  for (let i = 0; i < 5; i += 1) {
    await new Promise((resolve) => setTimeout(resolve, 5000))
    const ok = await checkSubscriptionOnce()
    if (ok) return
  }

  subDescription.value = 'Chưa thấy Premium được kích hoạt. Vui lòng đợi thêm hoặc liên hệ admin nếu cần hỗ trợ.'
}

function goCheckout() {
  router.push('/premium/checkout')
}

function goPremium() {
  router.push('/premium')
}

function goHome() {
  router.push('/premium')
}

onMounted(async () => {
  const raw = String(route.query.status || '').toLowerCase()
  if (raw === 'success' || raw === 'cancel' || raw === 'error') {
    status.value = raw
  } else {
    status.value = 'error'
  }

  if (status.value === 'success') {
    await handleSuccessStatus()
  }
})
</script>
