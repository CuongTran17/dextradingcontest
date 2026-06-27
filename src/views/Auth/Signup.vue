<template>
  <FullScreenLayout>
    <main class="min-h-screen bg-white px-6 py-8 dark:bg-gray-900">
      <div class="mx-auto flex min-h-[calc(100vh-4rem)] w-full max-w-6xl items-center gap-10">
        <section class="w-full max-w-md">
          <router-link
            to="/welcome"
            class="inline-flex items-center text-sm text-gray-500 transition-colors hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300"
          >
            <span aria-hidden="true" class="mr-2 text-lg">‹</span>
            Quay lại
          </router-link>

          <div class="mt-10">
            <p class="text-sm font-medium uppercase text-brand-500">Crypto Trading Contest</p>
            <h1 class="mt-2 text-3xl font-semibold text-gray-900 dark:text-white">
              Tạo tài khoản sinh viên
            </h1>
            <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Đăng ký miễn phí để tham gia contest giao dịch crypto mô phỏng.
            </p>
          </div>

          <form data-test="signup-form" class="mt-8 space-y-5" @submit.prevent="handleSubmit">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Họ và tên
              <input
                v-model.trim="fullname"
                data-test="signup-fullname"
                type="text"
                autocomplete="name"
                placeholder="Nguyen Van A"
                class="mt-2 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white"
              />
            </label>

            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Email
              <input
                v-model.trim="email"
                data-test="signup-email"
                type="email"
                autocomplete="email"
                placeholder="student@example.edu"
                class="mt-2 h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white"
              />
            </label>

            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Mật khẩu
              <div class="relative mt-2">
                <input
                  v-model="password"
                  data-test="signup-password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="new-password"
                  placeholder="Tối thiểu 6 ký tự"
                  class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 pr-20 text-sm text-gray-900 outline-none focus:border-brand-500 dark:border-gray-700 dark:text-white"
                />
                <button
                  type="button"
                  class="absolute right-3 top-1/2 -translate-y-1/2 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400"
                  @click="showPassword = !showPassword"
                >
                  {{ showPassword ? 'Ẩn' : 'Hiện' }}
                </button>
              </div>
            </label>

            <label class="flex items-start gap-3 text-sm text-gray-600 dark:text-gray-400">
              <input
                v-model="acceptedSimulation"
                data-test="signup-agreement"
                type="checkbox"
                class="mt-1 h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
              />
              <span>
                Tôi hiểu đây là cuộc thi mô phỏng giáo dục, không dùng tiền thật và không tạo lợi nhuận thật.
              </span>
            </label>

            <p
              v-if="errorMsg"
              data-test="signup-error"
              class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300"
            >
              {{ errorMsg }}
            </p>

            <button
              type="submit"
              :disabled="isSubmitting"
              class="h-11 w-full rounded-lg bg-brand-500 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {{ isSubmitting ? 'Đang tạo tài khoản...' : 'Tạo tài khoản' }}
            </button>
          </form>

          <p class="mt-5 text-sm text-gray-600 dark:text-gray-400">
            Đã có tài khoản?
            <router-link to="/signin" class="font-medium text-brand-500 hover:text-brand-600">
              Đăng nhập
            </router-link>
          </p>
        </section>

        <section class="hidden flex-1 lg:block">
          <div class="rounded-lg border border-gray-200 bg-gray-50 p-8 dark:border-gray-800 dark:bg-white/[0.03]">
            <p class="text-sm font-medium uppercase text-gray-500 dark:text-gray-400">Virtual capital</p>
            <h2 class="mt-3 text-2xl font-semibold text-gray-900 dark:text-white">
              Bắt đầu với tài khoản mô phỏng và bảng xếp hạng thật.
            </h2>
            <p class="mt-4 text-sm leading-6 text-gray-500 dark:text-gray-400">
              Sau khi đăng ký, bạn có thể chọn contest, join bằng vốn khởi đầu do admin đặt, rồi giao dịch BTC,
              ETH, SOL, XRP và BNB bằng dữ liệu thị trường Binance.
            </p>
          </div>
        </section>
      </div>
    </main>
  </FullScreenLayout>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import FullScreenLayout from '@/components/layout/FullScreenLayout.vue'
import { register } from '@/services/authApi'

const router = useRouter()
const fullname = ref('')
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const acceptedSimulation = ref(false)
const isSubmitting = ref(false)
const errorMsg = ref('')

function validateForm(): string {
  if (!fullname.value) return 'Vui lòng nhập họ và tên.'
  if (!email.value || !password.value) return 'Vui lòng nhập email và mật khẩu.'
  if (password.value.length < 6) return 'Mật khẩu phải có ít nhất 6 ký tự.'
  if (!acceptedSimulation.value) return 'Vui lòng đồng ý với điều kiện mô phỏng.'
  return ''
}

async function handleSubmit() {
  const validationError = validateForm()
  if (validationError) {
    errorMsg.value = validationError
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''
  try {
    await register(email.value, password.value, fullname.value)
    await router.push('/contests')
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : 'Đăng ký thất bại.'
  } finally {
    isSubmitting.value = false
  }
}
</script>
