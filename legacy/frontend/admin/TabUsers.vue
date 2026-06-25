<template>
  <div class="space-y-6">
    <div class="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-800 dark:bg-white/[0.03]">
      <div class="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p class="text-xs uppercase tracking-wide text-gray-500 dark:text-gray-400">User management</p>
          <h2 class="mt-1 text-lg font-semibold text-gray-800 dark:text-white/90">Quản lý người dùng</h2>
          <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
            Đổi quyền, khóa và mở khóa tài khoản ngay trong một bảng.
          </p>
        </div>

        <div class="flex flex-col gap-3 sm:flex-row sm:items-center">
          <label class="text-sm text-gray-500 dark:text-gray-400">
            Lọc vai trò
            <select
              v-model="roleFilter"
              class="mt-1 w-full rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
            >
              <option value="all">Tất cả</option>
              <option value="user">User</option>
              <option value="premium">Premium</option>
              <option value="admin">Admin</option>
            </select>
          </label>

          <button
            class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            :disabled="loading"
            @click="loadUsers"
          >
            Làm mới
          </button>
        </div>
      </div>

      <div v-if="notice" class="mt-4 rounded-xl border px-4 py-3 text-sm" :class="noticeClass">
        {{ notice }}
      </div>
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

      <div v-else-if="users.length === 0" class="px-6 py-12 text-center text-gray-500 dark:text-gray-400">
        Không có người dùng phù hợp với bộ lọc hiện tại.
      </div>

      <div v-else class="overflow-x-auto">
        <table class="w-full min-w-[860px]">
          <thead class="bg-gray-50 dark:bg-gray-800/80">
            <tr>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">ID</th>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Họ tên</th>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Email / Điện thoại</th>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Quyền hạn</th>
              <th class="px-6 py-3 text-left text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Trạng thái</th>
              <th class="px-6 py-3 text-right text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">Thao tác</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
            <tr v-for="user in users" :key="user.id" class="hover:bg-gray-50 dark:hover:bg-gray-800/60">
              <td class="px-6 py-4 text-sm text-gray-600 dark:text-gray-400">#{{ user.id }}</td>
              <td class="px-6 py-4">
                <div class="font-semibold text-gray-800 dark:text-gray-200">{{ user.fullname }}</div>
                <div v-if="isCurrentUser(user.id)" class="mt-1 text-xs text-brand-600 dark:text-brand-400">Tài khoản hiện tại</div>
              </td>
              <td class="px-6 py-4">
                <div class="text-sm text-gray-600 dark:text-gray-400">{{ user.email }}</div>
                <div class="mt-0.5 text-xs text-gray-400 dark:text-gray-500">{{ user.phone || '—' }}</div>
              </td>
              <td class="px-6 py-4">
                <select
                  :value="user.role"
                  class="min-w-[120px] rounded-lg border border-gray-200 bg-white px-3 py-2 text-sm text-gray-700 outline-none transition focus:border-brand-500 disabled:cursor-not-allowed disabled:opacity-60 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-200"
                  :disabled="isActionPending(user.id) || isCurrentUser(user.id)"
                  @change="handleRoleChange(user, $event)"
                >
                  <option value="user">User</option>
                  <option value="premium">Premium</option>
                  <option value="admin">Admin</option>
                </select>
              </td>
              <td class="px-6 py-4">
                <span
                  class="inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold"
                  :class="user.is_locked ? 'bg-error-50 text-error-700 dark:bg-error-500/15 dark:text-error-300' : 'bg-success-50 text-success-700 dark:bg-success-500/15 dark:text-success-300'"
                >
                  {{ user.is_locked ? 'Đã khóa' : 'Hoạt động' }}
                </span>
                <p v-if="user.is_locked && user.locked_reason" class="mt-2 max-w-[260px] text-xs text-error-600 dark:text-error-300">
                  Lý do: {{ user.locked_reason }}
                </p>
              </td>
              <td class="px-6 py-4 text-right">
                <button
                  v-if="user.is_locked"
                  class="rounded-lg bg-success-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-success-600 disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="isActionPending(user.id) || isCurrentUser(user.id)"
                  @click="unlockAccount(user)"
                >
                  Mở khóa
                </button>
                <button
                  v-else
                  class="rounded-lg bg-error-500 px-3 py-2 text-xs font-semibold text-white transition hover:bg-error-600 disabled:cursor-not-allowed disabled:opacity-60"
                  :disabled="isActionPending(user.id) || isCurrentUser(user.id)"
                  @click="lockAccount(user)"
                >
                  Khóa tài khoản
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="flex items-center justify-between border-t border-gray-100 px-6 py-4 dark:border-gray-800">
        <p class="text-sm text-gray-500 dark:text-gray-400">
          Trang {{ page }} · Hiển thị {{ users.length }} / {{ total }} người dùng
        </p>
        <div class="flex gap-2">
          <button
            class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            :disabled="page <= 1 || loading"
            @click="changePage(page - 1)"
          >
            ‹ Trước
          </button>
          <button
            class="rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-600 transition hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700"
            :disabled="page * perPage >= total || loading"
            @click="changePage(page + 1)"
          >
            Sau ›
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  getAdminUsers,
  lockUser,
  unlockUser,
  updateUserRole,
  getSavedUser,
  type UserInfo,
} from '@/services/authApi'

const users = ref<Array<UserInfo & { is_locked?: boolean }>>([])
const loading = ref(false)
const error = ref('')
const notice = ref('')
const noticeType = ref<'success' | 'error'>('success')
const page = ref(1)
const perPage = 20
const total = ref(0)
const roleFilter = ref<'all' | 'user' | 'premium' | 'admin'>('all')
const pendingUserId = ref<number | null>(null)
const currentUserId = computed(() => getSavedUser()?.id ?? null)

const noticeClass = computed(() =>
  noticeType.value === 'success'
    ? 'border-success-200 bg-success-50 text-success-700 dark:border-success-500/30 dark:bg-success-500/10 dark:text-success-300'
    : 'border-error-200 bg-error-50 text-error-700 dark:border-error-500/30 dark:bg-error-500/10 dark:text-error-300',
)

function showNotice(message: string, type: 'success' | 'error' = 'success'): void {
  notice.value = message
  noticeType.value = type
}

function isActionPending(userId: number): boolean {
  return pendingUserId.value === userId
}

function isCurrentUser(userId: number): boolean {
  return currentUserId.value === userId
}

async function loadUsers(): Promise<void> {
  loading.value = true
  error.value = ''

  try {
    const role = roleFilter.value === 'all' ? undefined : roleFilter.value
    const data = await getAdminUsers(page.value, perPage, role)
    users.value = data.users as Array<UserInfo & { is_locked?: boolean }>
    total.value = data.total
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Không tải được danh sách người dùng.'
  } finally {
    loading.value = false
  }
}

async function handleRoleChange(user: UserInfo, event: Event): Promise<void> {
  const nextRole = (event.target as HTMLSelectElement).value
  if (!nextRole || nextRole === user.role) {
    return
  }

  pendingUserId.value = user.id
  try {
    await updateUserRole(user.id, nextRole)
    showNotice(`Đã đổi quyền của ${user.fullname} sang ${nextRole.toUpperCase()}.`, 'success')
    await loadUsers()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể cập nhật quyền người dùng.', 'error')
  } finally {
    pendingUserId.value = null
  }
}

async function lockAccount(user: UserInfo & { is_locked?: boolean }): Promise<void> {
  const reason = window.prompt(`Nhập lý do khóa tài khoản của ${user.fullname}:`, 'Vi phạm quy định')
  if (!reason || !reason.trim()) {
    return
  }

  pendingUserId.value = user.id
  try {
    await lockUser(user.id, reason.trim())
    showNotice(`Đã khóa tài khoản ${user.fullname}.`, 'success')
    await loadUsers()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể khóa tài khoản.', 'error')
  } finally {
    pendingUserId.value = null
  }
}

async function unlockAccount(user: UserInfo & { is_locked?: boolean }): Promise<void> {
  if (!window.confirm(`Mở khóa tài khoản ${user.fullname}?`)) {
    return
  }

  pendingUserId.value = user.id
  try {
    await unlockUser(user.id)
    showNotice(`Đã mở khóa tài khoản ${user.fullname}.`, 'success')
    await loadUsers()
  } catch (err) {
    showNotice(err instanceof Error ? err.message : 'Không thể mở khóa tài khoản.', 'error')
  } finally {
    pendingUserId.value = null
  }
}

function changePage(newPage: number): void {
  if (newPage < 1 || newPage === page.value) {
    return
  }
  page.value = newPage
}

watch([page, roleFilter], () => {
  loadUsers()
}, { immediate: true })

onMounted(() => {
  // initial load handled by watch
})
</script>
