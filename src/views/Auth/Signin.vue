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
              Đăng nhập
            </h1>
            <p class="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Nhập email và mật khẩu để tiếp tục vào cuộc thi mô phỏng.
            </p>
          </div>

          <form data-test="signin-form" class="mt-8 space-y-5" @submit.prevent="handleSubmit">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300">
              Email
              <input
                v-model.trim="email"
                data-test="signin-email"
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
                  data-test="signin-password"
                  :type="showPassword ? 'text' : 'password'"
                  autocomplete="current-password"
                  placeholder="Nhập mật khẩu"
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

            <div class="flex items-center justify-between gap-3">
              <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                <input
                  v-model="keepLoggedIn"
                  type="checkbox"
                  class="h-4 w-4 rounded border-gray-300 text-brand-500 focus:ring-brand-500"
                />
                Ghi nhớ đăng nhập
              </label>
            </div>

            <p
              v-if="errorMsg"
              data-test="signin-error"
              class="rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700 dark:border-rose-900 dark:bg-rose-950/30 dark:text-rose-300"
            >
              {{ errorMsg }}
            </p>

            <button
              type="submit"
              :disabled="isSubmitting"
              class="h-11 w-full rounded-lg bg-brand-500 text-sm font-semibold text-white transition hover:bg-brand-600 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {{ isSubmitting ? 'Đang đăng nhập...' : 'Đăng nhập' }}
            </button>
          </form>

          <p class="mt-5 text-sm text-gray-600 dark:text-gray-400">
            Chưa có tài khoản?
            <router-link to="/signup" class="font-medium text-brand-500 hover:text-brand-600">
              Đăng ký
            </router-link>
          </p>
        </section>

        <section class="hidden flex-1 lg:block">
          <div class="rounded-lg border border-gray-200 bg-gray-50 p-8 dark:border-gray-800 dark:bg-white/[0.03]">
            <p class="text-sm font-medium uppercase text-gray-500 dark:text-gray-400">Student contest</p>
            <h2 class="mt-3 text-2xl font-semibold text-gray-900 dark:text-white">
              Vào lại tài khoản để tiếp tục contest đang tham gia.
            </h2>
            <p class="mt-4 text-sm leading-6 text-gray-500 dark:text-gray-400">
              Sau khi đăng nhập, hệ thống sẽ đưa bạn về trang trước đó hoặc dashboard contest nếu không có redirect.
            </p>
          </div>
        </section>
      </div>
    </main>
  </FullScreenLayout>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import FullScreenLayout from '@/components/layout/FullScreenLayout.vue'
import { login } from '@/services/authApi'

const router = useRouter()
const route = useRoute()
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const keepLoggedIn = ref(false)
const isSubmitting = ref(false)
const errorMsg = ref('')

onMounted(() => {
  if (route.query.locked === '1') {
    errorMsg.value = 'Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên.'
  }
})

async function handleSubmit() {
  if (!email.value || !password.value) {
    errorMsg.value = 'Vui lòng nhập email và mật khẩu.'
    return
  }

  isSubmitting.value = true
  errorMsg.value = ''
  try {
    await login(email.value, password.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    errorMsg.value = error instanceof Error ? error.message : 'Đăng nhập thất bại.'
  } finally {
    isSubmitting.value = false
  }
}
</script>
