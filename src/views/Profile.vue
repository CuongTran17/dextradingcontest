<template>
  <admin-layout>
    <div class="grid grid-cols-12 gap-4 md:gap-6">
      <section class="col-span-12 rounded-2xl border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03] md:p-6">
        <h1 class="text-2xl font-bold text-gray-800 dark:text-white/90">Tài khoản của tôi</h1>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
          Xem và chỉnh sửa thông tin cá nhân, đồng thời cập nhật ảnh đại diện.
        </p>

        <form class="mt-6 grid grid-cols-1 gap-5 md:grid-cols-2" @submit.prevent="saveProfile">
          <div class="md:col-span-2 flex items-center gap-4 rounded-xl border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/40">
            <img
              :src="avatarPreview"
              alt="Avatar"
              class="h-20 w-20 rounded-full border border-gray-200 object-cover dark:border-gray-700"
            />
            <div class="space-y-2">
              <label class="inline-flex cursor-pointer rounded-lg border border-brand-200 bg-brand-50 px-4 py-2 text-sm font-medium text-brand-700 hover:bg-brand-100 dark:border-brand-700/50 dark:bg-brand-500/10 dark:text-brand-300">
                Tải ảnh của bạn
                <input class="hidden" type="file" accept="image/*" @change="handleAvatarChange" />
              </label>
              <p class="text-xs text-gray-500 dark:text-gray-400">Hỗ trợ ảnh JPG/PNG, tối đa 8MB.</p>
            </div>
          </div>

          <div>
            <label class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Tên</label>
            <input
              v-model="firstName"
              type="text"
              class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            />
          </div>

          <div>
            <label class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Họ</label>
            <input
              v-model="lastName"
              type="text"
              class="h-11 w-full rounded-lg border border-gray-300 bg-transparent px-4 py-2.5 text-sm text-gray-800 focus:border-brand-300 focus:outline-hidden focus:ring-3 focus:ring-brand-500/10 dark:border-gray-700 dark:bg-gray-900 dark:text-white/90"
            />
          </div>

          <div class="md:col-span-2">
            <label class="mb-1.5 block text-sm font-medium text-gray-700 dark:text-gray-300">Email</label>
            <input
              :value="email"
              type="email"
              disabled
              class="h-11 w-full rounded-lg border border-gray-200 bg-gray-100 px-4 py-2.5 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-400"
            />
          </div>

          <p v-if="errorMessage" class="md:col-span-2 text-sm text-error-600 dark:text-error-400">{{ errorMessage }}</p>
          <p v-if="successMessage" class="md:col-span-2 text-sm text-success-600 dark:text-success-400">{{ successMessage }}</p>

          <div class="md:col-span-2">
            <button
              type="submit"
              :disabled="loading"
              class="inline-flex items-center justify-center rounded-lg bg-brand-500 px-5 py-2.5 text-sm font-medium text-white transition hover:bg-brand-600 disabled:opacity-60"
            >
              {{ loading ? 'Đang lưu...' : 'Lưu thay đổi' }}
            </button>
          </div>
        </form>
      </section>
    </div>
  </admin-layout>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AdminLayout from '@/components/layout/AdminLayout.vue'
import { getMe, getSavedUser, saveUser, updateProfile, type UserInfo } from '@/services/authApi'

const MAX_AVATAR_SIZE_MB = 8
const MAX_AVATAR_SIZE_BYTES = MAX_AVATAR_SIZE_MB * 1024 * 1024

const currentUser = ref<UserInfo | null>(getSavedUser())
const firstName = ref(currentUser.value?.first_name || '')
const lastName = ref(currentUser.value?.last_name || '')
const avatarData = ref<string | null>(currentUser.value?.avatar_data || null)
const loading = ref(false)
const errorMessage = ref('')
const successMessage = ref('')

const email = computed(() => currentUser.value?.email || '')
const avatarPreview = computed(() => avatarData.value || '/images/user/owner.jpg')

const hydrateProfileForm = (user: UserInfo) => {
  currentUser.value = user
  firstName.value = user.first_name || ''
  lastName.value = user.last_name || ''
  avatarData.value = user.avatar_data || null
}

const loadProfile = async () => {
  try {
    const user = await getMe()
    hydrateProfileForm(user)
  } catch (error) {
    // Keep fallback cached data if request fails.
    const cached = getSavedUser()
    if (cached) {
      hydrateProfileForm(cached)
    }
    errorMessage.value = error instanceof Error ? error.message : 'Không thể tải dữ liệu tài khoản.'
  }
}

const handleAvatarChange = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return

  if (file.size > MAX_AVATAR_SIZE_BYTES) {
    errorMessage.value = `Ảnh vượt quá dung lượng ${MAX_AVATAR_SIZE_MB}MB.`
    return
  }

  if (!file.type.startsWith('image/')) {
    errorMessage.value = 'File tải lên phải là ảnh hợp lệ.'
    return
  }

  const dataUrl = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Không thể đọc file ảnh.'))
    reader.readAsDataURL(file)
  })

  avatarData.value = dataUrl
  errorMessage.value = ''
  successMessage.value = ''
}

const saveProfile = async () => {
  errorMessage.value = ''
  successMessage.value = ''

  if (!firstName.value.trim() || !lastName.value.trim()) {
    errorMessage.value = 'Vui lòng nhập đầy đủ Tên và Họ.'
    return
  }

  loading.value = true
  try {
    const response = await updateProfile({
      firstName: firstName.value.trim(),
      lastName: lastName.value.trim(),
      avatarData: avatarData.value,
    })

    currentUser.value = response.user
    saveUser(response.user)
    successMessage.value = 'Đã cập nhật thông tin cá nhân thành công.'
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'Cập nhật thất bại.'
  } finally {
    loading.value = false
  }
}

onMounted(loadProfile)
</script>
