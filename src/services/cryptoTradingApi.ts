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
  order_type?: string
  status: string
  requested_quantity?: number
  filled_quantity: number
  average_fill_price: number
  executed_notional: number
  fee: number
  limit_price?: number | null
  stop_loss_price?: number | null
  take_profit_price?: number | null
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

interface BackendContestWallet {
  contest_id: string
  wallet_address: string | null
  wallet_type: string | null
  join_tx_signature: string | null
  joined_onchain_at: string | null
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

export async function confirmSolanaJoin(input: {
  contestId: string
  walletAddress: string
  joinTxSignature: string
}): Promise<BackendContestWallet> {
  return cryptoAuthFetch<BackendContestWallet>(
    `/api/crypto/contests/${encodeURIComponent(input.contestId)}/join/confirm`,
    {
      method: 'POST',
      body: JSON.stringify({
        wallet_address: input.walletAddress,
        join_tx_signature: input.joinTxSignature,
      }),
    },
  )
}

export async function fetchContestWallet(contestId: string): Promise<BackendContestWallet> {
  return cryptoAuthFetch<BackendContestWallet>(
    `/api/crypto/contests/${encodeURIComponent(contestId)}/wallet`,
  )
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
      order_type: input.orderType || 'market',
      limit_price: input.limitPrice ?? null,
      stop_loss_price: input.stopLossPrice ?? null,
      take_profit_price: input.takeProfitPrice ?? null,
    }),
  })
  return mapOrder(order, input.contestId)
}

export async function cancelCryptoOrder(
  contestId: string,
  orderId: string,
): Promise<SimulatedOrder> {
  const order = await cryptoAuthFetch<BackendOrder>(
    `/api/crypto/orders/${encodeURIComponent(orderId)}/cancel?contest_id=${encodeURIComponent(contestId)}`,
    { method: 'POST' },
  )
  return mapOrder(order, contestId)
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
    orderType: (order.order_type as 'market' | 'limit') || 'market',
    status: order.status,
    limitPrice: order.limit_price ?? undefined,
    stopLossPrice: order.stop_loss_price ?? undefined,
    takeProfitPrice: order.take_profit_price ?? undefined,
    quantity: order.requested_quantity ?? order.filled_quantity,
    filledQuantity: order.filled_quantity,
    executionPrice: order.average_fill_price,
    notional: order.executed_notional,
    fee: order.fee,
    slippage: 0,
    createdAt: order.created_at,
  }
}
