import { getToken } from '@/services/authApi'
import { backendFetch, normalizeBackendUrl } from '@/services/httpClient'
import type {
  AdminAccountDetail,
  AdminAccountOrder,
  AdminAccountPosition,
  AdminAccountSummary,
  AdminOverview,
  TradingAccountStatus,
} from '@/types/crypto'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)

interface BackendAdminOverview {
  users: {
    total: number
    locked: number
    admins: number
  }
  contests: {
    total: number
    active: number
    participants: number
  }
  accounts: {
    total: number
    active: number
    total_equity: number
  }
}

interface BackendAdminAccountSummary {
  account_id: number
  status: TradingAccountStatus
  participant_status: AdminAccountSummary['participantStatus']
  user: {
    id: number
    email: string
    fullname: string
    role: AdminAccountSummary['user']['role']
    is_locked: boolean
  }
  contest: {
    id: string
    title: string
    status: AdminAccountSummary['contest']['status']
  }
  cash: number
  locked_cash: number
  initial_equity: number
  equity: number
  realized_pnl: number
  unrealized_pnl: number
  roi: number
  position_count: number
  order_count: number
  updated_at: string | null
}

interface BackendAdminAccountDetail extends BackendAdminAccountSummary {
  balances: Array<{
    asset: string
    available: number
    locked: number
  }>
  positions: Array<{
    symbol: AdminAccountPosition['symbol']
    quantity: number
    average_entry_price: number
    cost_basis: number
    realized_pnl: number
    updated_at: string | null
  }>
  orders: Array<{
    order_id: number
    client_order_id: string
    symbol: AdminAccountOrder['symbol']
    side: AdminAccountOrder['side']
    order_type: string
    status: string
    requested_quantity: number
    filled_quantity: number
    average_fill_price: number
    executed_notional: number
    fee_amount: number
    fee_asset: string
    submitted_at: string | null
    completed_at: string | null
    fills: Array<{
      fill_sequence: number
      price: number
      quantity: number
      notional: number
      fee_amount: number
      fee_asset: string
      executed_at: string | null
    }>
  }>
}

interface BackendAdminAccountsResponse {
  total: number
  page: number
  per_page: number
  accounts: BackendAdminAccountSummary[]
}

export interface AdminAccountFilters {
  contestId?: string
  q?: string
  status?: TradingAccountStatus | ''
  page?: number
  perPage?: number
}

export interface AdminAccountsResponse {
  total: number
  page: number
  perPage: number
  accounts: AdminAccountSummary[]
}

function adminHeaders(): HeadersInit {
  const token = getToken()
  if (!token) throw new Error('Please sign in as admin')
  return { Authorization: `Bearer ${token}` }
}

export async function fetchAdminOverview(): Promise<AdminOverview> {
  const overview = await backendFetch<BackendAdminOverview>(
    BACKEND_URL,
    '/api/admin/crypto/overview',
    { headers: adminHeaders() },
  )
  return {
    users: overview.users,
    contests: overview.contests,
    accounts: {
      total: overview.accounts.total,
      active: overview.accounts.active,
      totalEquity: overview.accounts.total_equity,
    },
  }
}

export async function fetchAdminAccounts(
  filters: AdminAccountFilters = {},
): Promise<AdminAccountsResponse> {
  const params = new URLSearchParams()
  if (filters.contestId) params.set('contest_id', filters.contestId)
  if (filters.q) params.set('q', filters.q)
  if (filters.status) params.set('status', filters.status)
  params.set('page', String(filters.page ?? 1))
  params.set('per_page', String(filters.perPage ?? 20))

  const result = await backendFetch<BackendAdminAccountsResponse>(
    BACKEND_URL,
    `/api/admin/crypto/accounts?${params}`,
    { headers: adminHeaders() },
  )
  return {
    total: result.total,
    page: result.page,
    perPage: result.per_page,
    accounts: result.accounts.map(mapAccountSummary),
  }
}

export async function fetchAdminAccountDetail(accountId: number): Promise<AdminAccountDetail> {
  const detail = await backendFetch<BackendAdminAccountDetail>(
    BACKEND_URL,
    `/api/admin/crypto/accounts/${accountId}`,
    { headers: adminHeaders() },
  )
  return {
    ...mapAccountSummary(detail),
    balances: detail.balances,
    positions: detail.positions.map((position) => ({
      symbol: position.symbol,
      quantity: position.quantity,
      averageEntryPrice: position.average_entry_price,
      costBasis: position.cost_basis,
      realizedPnl: position.realized_pnl,
      updatedAt: position.updated_at,
    })),
    orders: detail.orders.map((order) => ({
      orderId: order.order_id,
      clientOrderId: order.client_order_id,
      symbol: order.symbol,
      side: order.side,
      orderType: order.order_type,
      status: order.status,
      requestedQuantity: order.requested_quantity,
      filledQuantity: order.filled_quantity,
      averageFillPrice: order.average_fill_price,
      executedNotional: order.executed_notional,
      feeAmount: order.fee_amount,
      feeAsset: order.fee_asset,
      submittedAt: order.submitted_at,
      completedAt: order.completed_at,
      fills: order.fills.map((fill) => ({
        fillSequence: fill.fill_sequence,
        price: fill.price,
        quantity: fill.quantity,
        notional: fill.notional,
        feeAmount: fill.fee_amount,
        feeAsset: fill.fee_asset,
        executedAt: fill.executed_at,
      })),
    })),
  }
}

function mapAccountSummary(account: BackendAdminAccountSummary): AdminAccountSummary {
  return {
    accountId: account.account_id,
    status: account.status,
    participantStatus: account.participant_status,
    user: {
      id: account.user.id,
      email: account.user.email,
      fullname: account.user.fullname,
      role: account.user.role,
      isLocked: account.user.is_locked,
    },
    contest: account.contest,
    cash: account.cash,
    lockedCash: account.locked_cash,
    initialEquity: account.initial_equity,
    equity: account.equity,
    realizedPnl: account.realized_pnl,
    unrealizedPnl: account.unrealized_pnl,
    roi: account.roi,
    positionCount: account.position_count,
    orderCount: account.order_count,
    updatedAt: account.updated_at,
  }
}
