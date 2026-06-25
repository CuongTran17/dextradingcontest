/**
 * Stock Backend API Service
 * =========================
 * Kết nối Vue frontend với FastAPI backend.
 */

import { backendFetch, normalizeBackendUrl, type BackendFetchOptions } from './httpClient'

const BACKEND_URL = normalizeBackendUrl(import.meta.env.VITE_BACKEND_URL)

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  checked_at?: string
  checks?: Record<string, { status: string; optional?: boolean }>
}

export function isBackendAvailableHealth(health: { status: string }): boolean {
  return health.status !== 'error'
}

interface ApiMeta {
  source?: string
  last_synced_at?: string
  data_status?: MarketDataStatus
  run_id?: string | null
  stale?: boolean
  message?: string | null
  dnse_realtime?: DnseRealtimeMeta
}

export interface DnseRealtimeMeta {
  status: string
  requested_symbols?: string[]
  fetched_symbols?: string[]
  fetched_count?: number
  ingested_count?: number
  latency_ms?: number
  errors?: Record<string, string>
}

export type MarketDataStatus =
  | 'DATA_AVAILABLE'
  | 'NO_DATA_IN_SNAPSHOT'
  | 'SNAPSHOT_NOT_BUILT'
  | 'REFRESH_DISABLED_IN_SNAPSHOT_MODE'
  | 'ETL_RUNNING'
  | 'ETL_FAILED'
  | 'STALE_SNAPSHOT'

export interface HistoricalRecord {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface TechnicalIndicators {
  sma_20: number[]
  sma_50: number[]
  sma_200: number[]
  ema_12: number[]
  ema_26: number[]
  rsi_14: number[]
  macd_line: number[]
  macd_signal: number[]
  macd_histogram: number[]
  bb_upper: number[]
  bb_middle: number[]
  bb_lower: number[]
  stoch_k: number[]
  stoch_d: number[]
  atr_14: number[]
  obv: number[]
}

export interface TradingSignals {
  rsi: 'oversold' | 'overbought' | 'neutral'
  macd: 'bullish' | 'bearish'
  golden_cross: boolean
  price_vs_sma200: 'above' | 'below'
  summary: 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'strong_sell'
}

export interface TechnicalResponse extends ApiMeta {
  symbol: string
  count: number
  ohlcv: {
    time: string[]
    open: number[]
    high: number[]
    low: number[]
    close: number[]
    volume: number[]
  }
  indicators: TechnicalIndicators
  signals: TradingSignals
}

export interface HistoryResponse extends ApiMeta {
  symbol: string
  count: number
  data: HistoricalRecord[]
}

export interface IntradayResponse extends ApiMeta {
  symbol: string
  count: number
  ticks_count: number
  data: HistoricalRecord[]
  is_in_session: boolean
  refreshed: boolean
  forced: boolean
}

export interface OrderTick {
  id: string
  symbol: string
  time: string
  price: number
  volume: number
  match_type: string
  side_source?: 'dnse' | 'price_tick' | 'missing' | string
  side_confidence?: 'source' | 'inferred' | 'unknown' | string
}

export interface TicksResponse extends ApiMeta {
  symbol: string
  count: number
  ticks: OrderTick[]
  is_in_session: boolean
  refreshed: boolean
}

export interface FinancialsResponse extends ApiMeta {
  symbol: string
  type: 'income' | 'balance' | 'cashflow' | 'ratios'
  count: number
  data: Record<string, unknown>[]
}

export interface MarketIndicesResponse extends ApiMeta {
  count: number
  data: MarketIndexQuote[]
}

export interface MarketIndexQuote {
  symbol: string
  name: string
  price: number
  change: number
  changePercent: number
  volume: number
  time: string
}

export interface MarketIndexHistoryResponse extends ApiMeta {
  symbol: string
  name: string
  count: number
  data: HistoricalRecord[]
}

export interface StockSnapshot {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  volume: number
  high: number
  low: number
  open: number
  refPrice: number
  lastUpdate: string
  syncedAt?: string
  priceSource?: 'dnse_live' | 'dnse_last_tick' | 'eod_snapshot' | 'no_data' | string
  dataStatus?: 'DATA_AVAILABLE' | 'NO_DATA_IN_SNAPSHOT' | string
}

export interface SnapshotsResponse extends ApiMeta {
  count: number
  data: StockSnapshot[]
  cached_at: string
}

export interface MarketNewsItem {
  id: string
  symbol: string
  symbols: string[]
  source: string
  title: string
  summary: string
  publish_time: string
  time: string
  url: string
  impact: 'high' | 'medium' | 'low'
}

export interface MarketNewsResponse extends ApiMeta {
  count: number
  symbols: string[]
  data: MarketNewsItem[]
  cached_at: string
}

export interface MarketEventItem {
  id: string
  symbol: string
  date: string
  title: string
  description: string
}

export interface MarketEventsResponse extends ApiMeta {
  count: number
  symbols: string[]
  data: MarketEventItem[]
  cached_at: string
}

export interface SaveQuotePayload {
  symbol: string
  price: number
  change: number
  changePercent: number
  volume: number
  high: number
  low: number
  open: number
  time: string
}

export type CompanyOverview = Record<string, unknown>

export interface AiAnalysisResponse {
  status: 'ok'
  analysis_id: string
  symbol: string
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number
  reasoning: string
  raw_output: string
  key_factors: string[]
  model_version: string
  prompt_version: string
  context_hash: string
  request_hash: string
  response_hash: string
  analysis: {
    data_source: string
    market_feature_run_id?: string | null
    data_date?: string | null
  }
}

export interface AiAnalysisHistoryItem {
  analysis_id: string
  symbol: string
  analysis_date: string | null
  horizon_days: number
  model_version: string
  prompt_version: string
  current_price: number | null
  decision: 'BUY' | 'SELL' | 'HOLD'
  confidence: number | null
  reasoning: string | null
  key_factors: string[]
  raw_output?: string | null
  normalized_output?: Record<string, unknown>
  status: string
  created_at: string | null
  completed_at: string | null
  outcomes: {
    horizon_days: number
    entry_price: number | null
    exit_date: string | null
    exit_price: number | null
    future_return_pct: number | null
    actual_direction: string | null
    is_correct: boolean | null
  }[]
}

export interface AiAnalysisHistoryResponse {
  symbol: string
  count: number
  data: AiAnalysisHistoryItem[]
  source: string
}

export interface AiAnalysisJobResponse {
  job_id: string
  symbol: string
  status: 'queued' | 'running' | 'success' | 'failed'
  analysis_id?: string | null
  result?: AiAnalysisResponse | Record<string, never>
  error_message?: string | null
  created_at?: string | null
  started_at?: string | null
  completed_at?: string | null
}

class StockBackendApi {
  private baseUrl: string

  constructor(baseUrl: string = BACKEND_URL) {
    this.baseUrl = baseUrl
  }

  private async fetch<T>(
    path: string,
    init?: RequestInit,
    options?: BackendFetchOptions,
  ): Promise<T> {
    return backendFetch<T>(this.baseUrl, path, init, options)
  }

  private buildQuery(params: Record<string, string | number | boolean | undefined>): string {
    const query = new URLSearchParams()
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== '') {
        query.set(key, String(value))
      }
    })
    const str = query.toString()
    return str ? `?${str}` : ''
  }

  async checkHealth(): Promise<HealthResponse> {
    return this.fetch<HealthResponse>('/api/health')
  }

  async getStockList(): Promise<string[]> {
    const data = await this.fetch<{ tickers: string[] }>('/api/stocks')
    return data.tickers
  }

  async getCompanyOverview(
    symbol: string,
    refresh: boolean = false,
  ): Promise<CompanyOverview> {
    void refresh
    return this.fetch<CompanyOverview>(`/api/stocks/${symbol.toUpperCase()}/overview`)
  }

  async getHistory(
    symbol: string,
    startDate?: string,
    endDate?: string,
    limit: number = 365,
    refresh: boolean = false,
  ): Promise<HistoryResponse> {
    void refresh
    const query = this.buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit,
    })

    return this.fetch<HistoryResponse>(`/api/stocks/${symbol.toUpperCase()}/history${query}`)
  }

  async getIntraday(
    symbol: string,
    limit: number = 320,
    refresh: boolean = false,
    force: boolean = false,
    intervalMinutes: number = 1,
  ): Promise<IntradayResponse> {
    void refresh
    void force
    const query = this.buildQuery({
      limit,
      interval_minutes: intervalMinutes,
    })

    return this.fetch<IntradayResponse>(`/api/stocks/${symbol.toUpperCase()}/intraday${query}`)
  }

  async getOrderLog(
    symbol: string,
    limit: number = 100,
    refresh: boolean = false,
    force: boolean = false,
  ): Promise<TicksResponse> {
    void refresh
    void force
    const query = this.buildQuery({
      limit,
    })

    return this.fetch<TicksResponse>(`/api/stocks/${symbol.toUpperCase()}/ticks${query}`)
  }

  async getTechnicalAnalysis(
    symbol: string,
    startDate?: string,
    endDate?: string,
    limit: number = 365,
    refresh: boolean = false,
  ): Promise<TechnicalResponse> {
    void refresh
    const query = this.buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit,
    })

    return this.fetch<TechnicalResponse>(`/api/stocks/${symbol.toUpperCase()}/technical${query}`)
  }

  async getFinancials(
    symbol: string,
    reportType: 'income' | 'balance' | 'cashflow' | 'ratios' = 'income',
    refresh: boolean = false,
  ): Promise<FinancialsResponse> {
    void refresh
    const query = this.buildQuery({ report_type: reportType })
    return this.fetch<FinancialsResponse>(`/api/stocks/${symbol.toUpperCase()}/financials${query}`)
  }

  async getMarketIndices(
    startDate?: string,
    endDate?: string,
    limit: number = 365,
    refresh: boolean = false,
  ): Promise<MarketIndicesResponse> {
    void refresh
    const query = this.buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit,
    })

    return this.fetch<MarketIndicesResponse>(`/api/market-indices${query}`)
  }

  async getMarketIndexHistory(
    indexSymbol: string,
    startDate?: string,
    endDate?: string,
    limit: number = 365,
    refresh: boolean = false,
  ): Promise<MarketIndexHistoryResponse> {
    void refresh
    const query = this.buildQuery({
      start_date: startDate,
      end_date: endDate,
      limit,
    })

    return this.fetch<MarketIndexHistoryResponse>(`/api/market-indices/${indexSymbol.toUpperCase()}/history${query}`)
  }

  async getSnapshots(
    symbols: string[],
    refresh: boolean = false,
  ): Promise<SnapshotsResponse> {
    void refresh
    const normalized = symbols
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => symbol.length > 0)

    const query = this.buildQuery({
      symbols: normalized.length > 0 ? normalized.join(',') : undefined,
    })

    return this.fetch<SnapshotsResponse>(`/api/stocks/snapshots${query}`)
  }

  async getMarketNews(
    symbols?: string[],
    limit: number = 24,
    refresh: boolean = false,
  ): Promise<MarketNewsResponse> {
    void refresh
    const normalized = (symbols || [])
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => symbol.length > 0)

    const query = this.buildQuery({
      symbols: normalized.length > 0 ? normalized.join(',') : undefined,
      limit,
    })

    return this.fetch<MarketNewsResponse>(`/api/news${query}`)
  }

  async getGoogleNews(
    symbols?: string[],
    limit: number = 12,
  ): Promise<MarketNewsResponse> {
    const normalized = (symbols || [])
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => symbol.length > 0)

    const query = this.buildQuery({
      symbols: normalized.length > 0 ? normalized.join(',') : undefined,
      limit,
    })

    return this.fetch<MarketNewsResponse>(`/api/google-news${query}`)
  }

  async getMarketEvents(
    symbols?: string[],
    limit: number = 24,
    refresh: boolean = false,
  ): Promise<MarketEventsResponse> {
    void refresh
    const normalized = (symbols || [])
      .map((symbol) => symbol.trim().toUpperCase())
      .filter((symbol) => symbol.length > 0)

    const query = this.buildQuery({
      symbols: normalized.length > 0 ? normalized.join(',') : undefined,
      limit,
    })

    return this.fetch<MarketEventsResponse>(`/api/events${query}`)
  }

  async saveRealtimeQuotes(quotes: SaveQuotePayload[]): Promise<{ saved: number }> {
    return this.fetch<{ saved: number }>('/api/dnse/save-quotes', {
      method: 'POST',
      body: JSON.stringify(quotes),
    })
  }

  async generateAnalysis(symbol: string, force: boolean = false): Promise<AiAnalysisResponse> {
    const job = await this.enqueueAnalysis(symbol, force)
    if (job.status === 'success' && job.result && 'decision' in job.result) {
      return job.result as AiAnalysisResponse
    }
    throw new Error(`Analysis generation is asynchronous. Poll job ${job.job_id}.`)
  }

  async enqueueAnalysis(symbol: string, force: boolean = false): Promise<AiAnalysisJobResponse> {
    const query = this.buildQuery({ force })
    return this.fetch<AiAnalysisJobResponse>(`/api/analysis/${symbol.toUpperCase()}/generate${query}`, {
      method: 'POST',
    }, {
      timeoutMs: 15000,
      retries: 0,
    })
  }

  async getAnalysisJob(jobId: string): Promise<AiAnalysisJobResponse> {
    return this.fetch<AiAnalysisJobResponse>(
      `/api/analysis/jobs/${encodeURIComponent(jobId)}`,
      undefined,
      {
        timeoutMs: 15000,
        retries: 1,
      },
    )
  }

  async getAnalysisHistory(
    symbol: string,
    limit: number = 24,
  ): Promise<AiAnalysisHistoryResponse> {
    const query = this.buildQuery({ limit })
    return this.fetch<AiAnalysisHistoryResponse>(`/api/analysis/${symbol.toUpperCase()}/history${query}`)
  }
}

export const stockBackendApi = new StockBackendApi()
export default stockBackendApi
