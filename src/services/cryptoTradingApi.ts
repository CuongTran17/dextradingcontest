import { getToken } from '@/services/authApi'
import { backendFetch, normalizeBackendUrl } from '@/services/httpClient'
import type {
  MarketOrderInput,
  SimulatedOrder,
  TradingAccount,
} from '@/types/crypto'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)

interface BackendPosition {
  symbol: TradingAccount['positions'][number]['symbol']
  quantity: number
  average_entry: number
  realized_pnl: number
}

interface BackendOrder {
  order_id: number
  client_order_id: string
  symbol: SimulatedOrder['symbol']
  side: SimulatedOrder['side']
  status: string
  filled_quantity: number
  average_fill_price: number
  executed_notional: number
  fee: number
  created_at: string
}

interface BackendTradingAccount {
  account_id: number
  contest_id: string
  status: TradingAccount['status']
  cash: number
  initial_equity: number
  equity: number
  realized_pnl: number
  unrealized_pnl: number
  positions: BackendPosition[]
  orders: BackendOrder[]
}

async function cryptoAuthFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getToken()
  if (!token) {
    throw new Error('Please sign in to trade')
  }

  return backendFetch<T>(BACKEND_URL, path, {
    ...init,
    headers: {
      ...(init?.headers || {}),
      Authorization: `Bearer ${token}`,
    },
  })
}

export async function joinCryptoContest(contestId: string): Promise<TradingAccount> {
  const account = await cryptoAuthFetch<BackendTradingAccount>(
    `/api/crypto/contests/${encodeURIComponent(contestId)}/join`,
    { method: 'POST' },
  )
  return mapAccount(account)
}

export async function getCryptoAccount(contestId: string): Promise<TradingAccount> {
  const account = await cryptoAuthFetch<BackendTradingAccount>(
    `/api/crypto/accounts/${encodeURIComponent(contestId)}`,
  )
  return mapAccount(account)
}

export async function placeCryptoMarketOrder(
  input: MarketOrderInput,
): Promise<SimulatedOrder> {
  const order = await cryptoAuthFetch<BackendOrder>('/api/crypto/orders/market', {
    method: 'POST',
    body: JSON.stringify({
      contest_id: input.contestId,
      client_order_id: input.clientOrderId,
      symbol: input.symbol,
      side: input.side,
      quantity: input.quantity,
    }),
  })
  return mapOrder(order, input.contestId)
}

function mapAccount(account: BackendTradingAccount): TradingAccount {
  return {
    accountId: account.account_id,
    contestId: account.contest_id,
    status: account.status,
    cash: account.cash,
    initialEquity: account.initial_equity,
    equity: account.equity,
    realizedPnl: account.realized_pnl,
    unrealizedPnl: account.unrealized_pnl,
    positions: account.positions.map((position) => ({
      symbol: position.symbol,
      quantity: position.quantity,
      averageEntry: position.average_entry,
    })),
    orders: account.orders.map((order) => mapOrder(order, account.contest_id)),
  }
}

function mapOrder(order: BackendOrder, contestId: string): SimulatedOrder {
  return {
    id: String(order.order_id),
    contestId,
    symbol: order.symbol,
    side: order.side,
    quantity: order.filled_quantity,
    executionPrice: order.average_fill_price,
    notional: order.executed_notional,
    fee: order.fee,
    slippage: 0,
    createdAt: order.created_at,
  }
}
