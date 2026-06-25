/**
 * JWT authentication, user profile, and user administration API.
 */

import { ApiError, backendFetch, normalizeBackendUrl } from './httpClient'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)
const TOKEN_KEY = 'crypto_contest_token'
const USER_KEY = 'crypto_contest_user'

export interface UserInfo {
  id: number
  email: string
  phone: string | null
  first_name?: string | null
  last_name?: string | null
  fullname: string
  avatar_data: string | null
  role: 'user' | 'premium' | 'admin'
  is_locked?: boolean
  locked_reason?: string | null
  created_at?: string
}

export interface AuthResponse {
  message: string
  token: string
  user: UserInfo
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function removeToken(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function getSavedUser(): UserInfo | null {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

export function saveUser(user: UserInfo): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function isLoggedIn(): boolean {
  return Boolean(getToken())
}

export function isAdmin(): boolean {
  return getSavedUser()?.role === 'admin'
}

export function logout(): void {
  removeToken()
}

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...((init?.headers as Record<string, string>) || {}),
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`
  }

  try {
    return await backendFetch<T>(BACKEND_URL, path, { ...init, headers })
  } catch (error) {
    if (!(error instanceof ApiError)) {
      throw error
    }

    if (error.status === 401) {
      removeToken()
      if (!path.includes('/auth/login') && !path.includes('/auth/register')) {
        window.location.href = '/signin'
      }
    } else if (error.status === 403 && error.message.toLowerCase().includes('lock')) {
      removeToken()
      window.location.href = '/signin?locked=1'
    }

    throw new Error(error.message)
  }
}

export async function register(
  email: string,
  password: string,
  fullname: string,
  phone?: string,
): Promise<AuthResponse> {
  const data = await authFetch<AuthResponse>('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password, fullname, phone: phone || null }),
  })
  setToken(data.token)
  saveUser(data.user)
  return data
}

export async function login(emailOrPhone: string, password: string): Promise<AuthResponse> {
  const data = await authFetch<AuthResponse>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email_or_phone: emailOrPhone, password }),
  })
  setToken(data.token)
  saveUser(data.user)
  return data
}

export async function getMe(): Promise<UserInfo> {
  const user = await authFetch<UserInfo>('/api/auth/me')
  saveUser(user)
  return user
}

export async function updateProfile(payload: {
  firstName?: string
  lastName?: string
  fullname?: string
  phone?: string
  avatarData?: string | null
}): Promise<AuthResponse> {
  const data = await authFetch<AuthResponse>('/api/auth/profile', {
    method: 'PUT',
    body: JSON.stringify({
      first_name: payload.firstName,
      last_name: payload.lastName,
      fullname: payload.fullname,
      phone: payload.phone,
      avatar_data: payload.avatarData,
    }),
  })
  setToken(data.token)
  saveUser(data.user)
  return data
}

export async function updatePassword(
  currentPassword: string,
  newPassword: string,
): Promise<{ message: string }> {
  return authFetch('/api/auth/password', {
    method: 'PUT',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

export async function getAdminUsers(
  page = 1,
  perPage = 20,
  role?: string,
): Promise<{ total: number; page: number; per_page: number; users: UserInfo[] }> {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  if (role) params.set('role', role)
  return authFetch(`/api/admin/users?${params}`)
}

export async function updateUserRole(userId: number, role: 'user' | 'admin'): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/role?role=${role}`, { method: 'PUT' })
}

export async function lockUser(userId: number, reason: string): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/lock?reason=${encodeURIComponent(reason)}`, {
    method: 'PUT',
  })
}

export async function unlockUser(userId: number): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/unlock`, { method: 'PUT' })
}
