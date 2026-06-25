import { backendFetch } from './httpClient'

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || ''

export interface DnseTick {
  symbol: string
  price: number | null
  volume: number | null
  trade_time: string | null
  trade_time_local?: string | null
  trade_time_raw?: string | null
  source: 'dnse'
  storage_source?: 'cache' | 'parquet'
  latency_ms?: number
  raw?: Record<string, unknown>
}

export interface MarketSession {
  status:
    | 'pre_open'
    | 'open'
    | 'lunch_break'
    | 'closing'
    | 'closed'
    | 'weekend'
    | 'holiday'
    | 'unknown'
  is_polling_allowed: boolean
  reason: string
  timezone: string
  local_time: string
  next_open_at: string | null
  next_close_at: string | null
}

export interface DnseTickResponse {
  status: 'ok' | 'error' | 'not_configured' | 'market_closed'
  source: 'dnse'
  data_source?: 'dnse_live' | 'cached_last_tick'
  is_stale?: boolean
  requested_at?: string
  symbols: string[]
  ticks: DnseTick[]
  missing_symbols?: string[]
  errors: Record<string, string>
  latency_ms: number
  market_session?: MarketSession
}

export interface DnseTickStatus {
  status: 'configured' | 'not_configured'
  configured: boolean
  base_url: string
  board_id: string
  poll_interval_ms: number
  closed_heartbeat_seconds: number
  endpoint: string
  auth: string
  market_session: MarketSession
}

export async function getLatestTicks(symbols: string): Promise<DnseTickResponse> {
  const query = new URLSearchParams({ symbols })
  return backendFetch<DnseTickResponse>(BACKEND_URL, `/api/dnse/ticks/latest?${query.toString()}`, undefined, {
    timeoutMs: 12000,
    retries: 0,
  })
}

export async function getDnseTickStatus(): Promise<DnseTickStatus> {
  return backendFetch<DnseTickStatus>(BACKEND_URL, '/api/dnse/ticks/status', undefined, {
    timeoutMs: 8000,
    retries: 1,
  })
}
