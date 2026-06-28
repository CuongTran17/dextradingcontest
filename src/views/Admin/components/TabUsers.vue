<template>
  <section class="rounded-lg border border-gray-200 bg-white p-5 dark:border-gray-800 dark:bg-white/[0.03]">
    <div class="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
      <div>
        <h2 class="text-lg font-semibold text-gray-900 dark:text-white">Users</h2>
        <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">Search users, change roles, and lock accounts.</p>
      </div>
      <div class="grid gap-2 sm:grid-cols-4">
        <input
          v-model="search"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
          placeholder="Search email/name"
          @keyup.enter="loadUsers"
        >
        <select
          v-model="role"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        >
          <option value="">All roles</option>
          <option value="user">user</option>
          <option value="admin">admin</option>
        </select>
        <select
          v-model="locked"
          class="rounded-lg border border-gray-300 px-3 py-2 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
        >
          <option value="">All status</option>
          <option value="false">unlocked</option>
          <option value="true">locked</option>
        </select>
        <button
          class="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
          :disabled="loading"
          @click="loadUsers"
        >
          Search
        </button>
      </div>
    </div>

    <p v-if="error" class="mt-3 text-sm text-rose-600">{{ error }}</p>
    <p v-if="loading" class="mt-4 text-sm text-gray-500 dark:text-gray-400">Loading users...</p>

    <div v-else class="mt-4 overflow-x-auto">
      <table class="min-w-full divide-y divide-gray-200 text-sm dark:divide-gray-800">
        <thead class="text-left text-xs uppercase text-gray-500 dark:text-gray-400">
          <tr>
            <th class="px-3 py-2">User</th>
            <th class="px-3 py-2">Role</th>
            <th class="px-3 py-2">Status</th>
            <th class="px-3 py-2">Created</th>
            <th class="px-3 py-2">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-gray-100 dark:divide-gray-800">
          <tr v-for="user in users" :key="user.id">
            <td class="px-3 py-3">
              <p class="font-medium text-gray-900 dark:text-white">{{ user.fullname }}</p>
              <p class="text-xs text-gray-500 dark:text-gray-400">{{ user.email }}</p>
            </td>
            <td class="px-3 py-3">
              <select
                class="rounded border border-gray-300 bg-white px-2 py-1 text-sm dark:border-gray-700 dark:bg-gray-900 dark:text-white"
                :value="user.role"
                @change="changeRole(user, ($event.target as HTMLSelectElement).value as 'user' | 'admin')"
              >
                <option value="user">user</option>
                <option value="admin">admin</option>
              </select>
            </td>
            <td class="px-3 py-3 text-gray-700 dark:text-gray-300">
              <span :class="user.is_locked ? 'text-rose-600' : 'text-emerald-600'">
                {{ user.is_locked ? 'locked' : 'active' }}
              </span>
              <span v-if="user.locked_reason" class="block text-xs text-gray-500">{{ user.locked_reason }}</span>
            </td>
            <td class="px-3 py-3 text-gray-500 dark:text-gray-400">{{ formatDate(user.created_at) }}</td>
            <td class="px-3 py-3">
              <div class="flex flex-wrap gap-2">
                <button
                  v-if="user.is_locked"
                  class="rounded border border-emerald-300 px-2 py-1 text-xs font-medium text-emerald-700 dark:border-emerald-700 dark:text-emerald-300"
                  @click="unlock(user.id)"
                >
                  Unlock
                </button>
                <button
                  v-else
                  class="rounded border border-amber-300 px-2 py-1 text-xs font-medium text-amber-700 dark:border-amber-700 dark:text-amber-300"
                  @click="lock(user.id)"
                >
                  Lock
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-if="users.length === 0" class="py-6 text-center text-sm text-gray-500">No users found.</p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { getAdminUsers, lockUser, unlockUser, updateUserRole, type UserInfo } from '@/services/authApi'

const users = ref<UserInfo[]>([])
const loading = ref(false)
const error = ref('')
const search = ref('')
const role = ref('')
const locked = ref('')

async function loadUsers() {
  loading.value = true
  error.value = ''
  try {
    const response = await getAdminUsers(
      1,
      50,
      role.value || undefined,
      search.value || undefined,
      locked.value === '' ? undefined : locked.value === 'true',
    )
    users.value = response.users
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to load users'
  } finally {
    loading.value = false
  }
}

async function changeRole(user: UserInfo, nextRole: 'user' | 'admin') {
  if (user.role === nextRole) return
  error.value = ''
  try {
    await updateUserRole(user.id, nextRole)
    users.value = users.value.map((item) => (item.id === user.id ? { ...item, role: nextRole } : item))
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to update role'
  }
}

async function lock(userId: number) {
  error.value = ''
  try {
    await lockUser(userId, 'Admin lock')
    await loadUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to lock user'
  }
}

async function unlock(userId: number) {
  error.value = ''
  try {
    await unlockUser(userId)
    await loadUsers()
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Unable to unlock user'
  }
}

function formatDate(value?: string): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(new Date(value))
}

onMounted(loadUsers)
</script>
