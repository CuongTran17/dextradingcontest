/**
 * Auth API Service
 * ================
 * Manages JWT authentication, user state, and API calls for auth/payment/portfolio.
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

export interface PaymentInfo {
  bank_name: string
  account_number: string
  account_name: string
  amount: number
  transfer_content: string
  qr_url: string
}

export interface PremiumCheckoutResponse {
  message: string
  checkoutURL: string
  checkoutFormFields: Record<string, string>
  amount: number
  transfer_content: string
  original_amount: number
  discount_amount: number
  promo_code?: string | null
  flash_sale_id?: number | null
  flash_sale_title?: string | null
}

export interface SubscriptionStatus {
  is_premium: boolean
  role: string
  active_subscription: {
    plan: string
    expires_at: string | null
  } | null
}

export interface PortfolioItem {
  id: number
  symbol: string
  quantity: number
  avg_price: number | null
  tp_price: number | null
  sl_price: number | null
  note: string | null
  created_at?: string
  updated_at?: string
}

export interface SalesStats {
  total_revenue: number
  total_subscriptions: number
  active_premium_count: number
  total_users: number
  pending_count: number
  monthly_revenue: { month: string; revenue: number; count: number }[]
}

export interface AdminUserPortfolio {
  user: { id: number; email: string; fullname: string; role: string }
  holdings: {
    symbol: string
    quantity: number
    avg_price: number | null
    tp_price: number | null
    sl_price: number | null
    note: string | null
  }[]
  total_symbols: number
}

export interface PromotionCode {
  id: number
  code: string
  title: string
  description: string | null
  discount_type: 'percentage' | 'fixed'
  discount_value: number
  min_order_amount: number | null
  max_discount_amount: number | null
  usage_limit: number | null
  used_count: number
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  created_by: number | null
  created_at: string | null
  updated_at: string | null
}

export interface PromotionPayload {
  code: string
  title: string
  description?: string | null
  discount_type: 'percentage' | 'fixed'
  discount_value: number
  min_order_amount?: number | null
  max_discount_amount?: number | null
  usage_limit?: number | null
  starts_at?: string | null
  ends_at?: string | null
  is_active: boolean
}

export interface FlashSaleConfig {
  id: number
  title: string
  description: string | null
  discount_percentage: number
  starts_at: string | null
  ends_at: string | null
  is_active: boolean
  created_by: number | null
  created_at: string | null
  updated_at: string | null
}

export interface FlashSalePayload {
  title: string
  description?: string | null
  discount_percentage: number
  starts_at?: string | null
  ends_at?: string | null
  is_active: boolean
}

export type MarketDataStatus =
  | 'DATA_AVAILABLE'
  | 'NO_DATA_IN_SNAPSHOT'
  | 'SNAPSHOT_NOT_BUILT'
  | 'REFRESH_DISABLED_IN_SNAPSHOT_MODE'
  | 'ETL_RUNNING'
  | 'ETL_FAILED'
  | 'STALE_SNAPSHOT'

export interface EtlRunMetadata {
  run_id: string
  started_at: string
  completed_at: string | null
  status: 'running' | 'success' | 'failed' | string
  symbols: string[]
  row_count: number
  errors: Record<string, string>
  duration_seconds: number
  output_file?: string | null
  run_mode?: string
  effective_start_date?: string | null
  effective_end_date?: string | null
  phase_durations?: Record<string, number>
  row_counts?: Record<string, number>
  extract_errors?: Record<string, string>
  symbol_status?: Record<string, string>
  quality_report?: EtlQualitySummary
  artifacts?: Record<string, string>
}

export interface EtlQualitySummary {
  status?: string
  row_count?: number
  symbol_count?: number
  symbols?: string[]
  missing_expected_symbols?: string[]
  date_range?: { min?: string | null; max?: string | null }
  null_critical_counts?: Record<string, number>
  duplicate_symbol_date_rows?: number
  invalid_date_rows?: number
  non_positive_close_rows?: number
  negative_volume_rows?: number
  invalid_ohlc_rows?: number
  outlier_count?: number
  duplicate_rows?: number
  columns_with_missing?: number
  top_missing_columns?: Record<string, number>
  errors?: string[]
  warnings?: string[]
}

export interface EtlSnapshotMetadata {
  run_id?: string
  row_count?: number
  columns?: string[]
  date_range?: { min?: string | null; max?: string | null }
  symbols?: string[]
  schema_version?: number
  quality_summary?: EtlQualitySummary
  checksum_sha256?: string
  _path?: string
  _mtime?: string
}

export interface EtlStatusResponse {
  status: string
  data_status?: MarketDataStatus
  details: string
  last_run_id?: string | null
  last_run_time?: string | null
  row_count?: number | null
  symbols: string[]
}

export interface EtlHealthResponse {
  status: string
  data_status?: MarketDataStatus
  details: string
  age_hours?: number | null
  missing_symbols: string[]
  disk?: {
    total_bytes: number
    used_bytes: number
    free_bytes: number
    free_ratio?: number | null
  } | null
  latest_run?: EtlRunMetadata | null
  latest_snapshot?: EtlSnapshotMetadata | null
}

export interface EtlRunsResponse {
  count: number
  runs: EtlRunMetadata[]
}

export interface EtlTriggerPayload {
  symbols?: string[]
  start_date?: string
  end_date?: string
  disable_mysql_load?: boolean
  disable_tick_eod?: boolean
}

export interface EtlTriggerResponse {
  run_id: string
  status: string
  data_status?: MarketDataStatus
  symbols: string[]
}

// ── Token Management ────────────────────────────────────────────────

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
  return !!getToken()
}

export function isAdmin(): boolean {
  const user = getSavedUser()
  return user?.role === 'admin'
}

export function isPremium(): boolean {
  const user = getSavedUser()
  return user?.role === 'premium' || user?.role === 'admin'
}

export function logout(): void {
  removeToken()
}

// ── API Fetch Helper ────────────────────────────────────────────────

async function authFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> || {}),
  }
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
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
    } else if (error.status === 403 && error.message.includes('khóa')) {
      // Locked account — clear token so UI doesn't keep retrying
      removeToken()
      window.location.href = '/signin?locked=1'
    }

    throw new Error(error.message)
  }

}

// ── Auth Endpoints ──────────────────────────────────────────────────

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

export async function updateProfile(
  payload: {
    firstName?: string
    lastName?: string
    fullname?: string
    phone?: string
    avatarData?: string | null
  },
): Promise<AuthResponse> {
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

export async function updatePassword(currentPassword: string, newPassword: string): Promise<{ message: string }> {
  return authFetch('/api/auth/password', {
    method: 'PUT',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

// ── Payment Endpoints ───────────────────────────────────────────────

export async function getPremiumPaymentInfo(): Promise<PaymentInfo> {
  return authFetch<PaymentInfo>('/api/payment/premium-info')
}

export async function createPremiumSePayCheckout(payload?: { promo_code?: string | null }): Promise<PremiumCheckoutResponse> {
  return authFetch<PremiumCheckoutResponse>('/api/payment/create-checkout', {
    method: 'POST',
    body: JSON.stringify({ promo_code: payload?.promo_code || null }),
  })
}

export async function getSubscriptionStatus(): Promise<SubscriptionStatus> {
  return authFetch<SubscriptionStatus>('/api/payment/subscription-status')
}

// ── Portfolio Endpoints ─────────────────────────────────────────────

export async function getMyPortfolio(): Promise<{ count: number; items: PortfolioItem[] }> {
  return authFetch('/api/portfolio/')
}

export async function addToPortfolio(
  symbol: string,
  quantity: number = 0,
  avgPrice?: number,
  tpPrice?: number,
  slPrice?: number,
  note?: string,
): Promise<{ message: string; item: PortfolioItem }> {
  return authFetch('/api/portfolio/', {
    method: 'POST',
    body: JSON.stringify({ symbol, quantity, avg_price: avgPrice, tp_price: tpPrice, sl_price: slPrice, note }),
  })
}

export async function updatePortfolioItem(
  symbol: string,
  data: { quantity?: number; avg_price?: number; tp_price?: number; sl_price?: number; note?: string },
): Promise<{ message: string; item: PortfolioItem }> {
  return authFetch(`/api/portfolio/${symbol.toUpperCase()}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function removeFromPortfolio(symbol: string): Promise<{ message: string }> {
  return authFetch(`/api/portfolio/${symbol.toUpperCase()}`, { method: 'DELETE' })
}

// ── Admin Endpoints ─────────────────────────────────────────────────

export async function getAdminSalesStats(): Promise<SalesStats> {
  return authFetch<SalesStats>('/api/admin/sales-stats')
}

export async function getAdminUsers(
  page: number = 1,
  perPage: number = 20,
  role?: string,
): Promise<{ total: number; page: number; per_page: number; users: UserInfo[] }> {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  if (role) params.set('role', role)
  return authFetch(`/api/admin/users?${params}`)
}

export async function getAdminUserPortfolios(
  page: number = 1,
  perPage: number = 50,
): Promise<{ total: number; portfolios: AdminUserPortfolio[] }> {
  const params = new URLSearchParams({ page: String(page), per_page: String(perPage) })
  return authFetch(`/api/admin/user-portfolios?${params}`)
}

export async function updateUserRole(userId: number, role: string): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/role?role=${role}`, { method: 'PUT' })
}

export async function lockUser(userId: number, reason: string): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/lock?reason=${encodeURIComponent(reason)}`, { method: 'PUT' })
}

export async function unlockUser(userId: number): Promise<{ message: string }> {
  return authFetch(`/api/admin/users/${userId}/unlock`, { method: 'PUT' })
}

export async function getAdminPromotions(): Promise<{ promotions: PromotionCode[] }> {
  return authFetch('/api/admin/promotions')
}

export async function createPromotion(payload: PromotionPayload): Promise<{ message: string; promotion: PromotionCode }> {
  return authFetch('/api/admin/promotions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updatePromotion(
  promotionId: number,
  payload: PromotionPayload,
): Promise<{ message: string; promotion: PromotionCode }> {
  return authFetch(`/api/admin/promotions/${promotionId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function setPromotionStatus(
  promotionId: number,
  isActive: boolean,
): Promise<{ message: string; promotion: PromotionCode }> {
  return authFetch(`/api/admin/promotions/${promotionId}/status?is_active=${isActive}`, {
    method: 'PATCH',
  })
}

export async function deletePromotion(promotionId: number): Promise<{ message: string }> {
  return authFetch(`/api/admin/promotions/${promotionId}`, { method: 'DELETE' })
}

export async function getAdminFlashSales(): Promise<{ flash_sales: FlashSaleConfig[] }> {
  return authFetch('/api/admin/flash-sales')
}

export async function createFlashSale(payload: FlashSalePayload): Promise<{ message: string; flash_sale: FlashSaleConfig }> {
  return authFetch('/api/admin/flash-sales', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export async function updateFlashSale(
  flashSaleId: number,
  payload: FlashSalePayload,
): Promise<{ message: string; flash_sale: FlashSaleConfig }> {
  return authFetch(`/api/admin/flash-sales/${flashSaleId}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export async function setFlashSaleStatus(
  flashSaleId: number,
  isActive: boolean,
): Promise<{ message: string; flash_sale: FlashSaleConfig }> {
  return authFetch(`/api/admin/flash-sales/${flashSaleId}/status?is_active=${isActive}`, {
    method: 'PATCH',
  })
}

export async function deleteFlashSale(flashSaleId: number): Promise<{ message: string }> {
  return authFetch(`/api/admin/flash-sales/${flashSaleId}`, { method: 'DELETE' })
}

// ── ETL Admin Endpoints ─────────────────────────────────────────────

export async function getEtlStatus(): Promise<EtlStatusResponse> {
  return authFetch<EtlStatusResponse>('/api/etl/status')
}

export async function getEtlHealth(): Promise<EtlHealthResponse> {
  return authFetch<EtlHealthResponse>('/api/etl/health')
}

export async function getEtlRuns(limit: number = 10): Promise<EtlRunsResponse> {
  return authFetch<EtlRunsResponse>(`/api/etl/runs?limit=${encodeURIComponent(String(limit))}`)
}

export async function triggerEtlRun(payload: EtlTriggerPayload = {}): Promise<EtlTriggerResponse> {
  return authFetch<EtlTriggerResponse>('/api/etl/trigger', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
