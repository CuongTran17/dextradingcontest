export type CryptoSymbol = 'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT' | 'XRPUSDT' | 'BNBUSDT'
export type ContestStatus = 'practice' | 'upcoming' | 'active' | 'ended'
export type RawContestStatus = 'draft' | 'scheduled' | 'active' | 'settling' | 'completed' | 'cancelled'
export type OrderSide = 'buy' | 'sell'
export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1D'
export type CryptoIndicator = 'MACD'

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export type MarketDataSource = 'binance' | 'binance-websocket'

export interface OrderBookLevel {
  price: number
  quantity: number
  total: number
}

export interface CryptoOrderBook {
  symbol: CryptoSymbol
  last_update_id: number | null
  bids: OrderBookLevel[]
  asks: OrderBookLevel[]
  spread: number
  mid_price: number
  source: MarketDataSource
}

export interface MacdPoint {
  time: number
  macd: number
  signal: number
  histogram: number
}

export interface CryptoIndicatorResponse {
  symbol: CryptoSymbol
  timeframe: Exclude<Timeframe, '1D'>
  indicator: CryptoIndicator
  params: {
    fast: number
    slow: number
    signal: number
  }
  points: MacdPoint[]
}

export interface CryptoAsset {
  symbol: CryptoSymbol
  baseAsset: 'BTC' | 'ETH' | 'SOL' | 'XRP' | 'BNB'
  quoteAsset: 'USDT_TEST'
  displayName: string
  pricePrecision: number
  quantityPrecision: number
}

export interface Contest {
  id: string
  title: string
  status: ContestStatus
  rawStatus?: RawContestStatus
  mode: 'practice' | 'contest'
  initialCapital: number
  symbols: CryptoSymbol[]
  startsAt: string
  endsAt: string
  participantCount: number
}

export interface LeaderboardRow {
  rank: number
  user: string
  equity: number
  pnl: number
  roi: number
  volume: number
  tradeCount: number
  lastTrade: string | null
}

export interface ContestCreateInput {
  slug: string
  title: string
  mode: 'practice' | 'contest'
  status: 'draft' | 'scheduled' | 'active'
  initialBalance: number
  symbols: CryptoSymbol[]
  startsAt?: string | null
  endsAt?: string | null
}

export interface ContestUpdateInput {
  title?: string
  status?: RawContestStatus
  symbols?: CryptoSymbol[]
  startsAt?: string | null
  endsAt?: string | null
}

export interface Position {
  symbol: CryptoSymbol
  quantity: number
  averageEntry: number
}

export interface SimulatedOrder {
  id: string
  contestId: string
  symbol: CryptoSymbol
  side: OrderSide
  quantity: number
  executionPrice: number
  notional: number
  fee: number
  slippage: number
  createdAt: string
}

export interface TradingAccount {
  accountId: number
  contestId: string
  status: 'active' | 'frozen' | 'closed'
  cash: number
  initialEquity: number
  equity: number
  realizedPnl: number
  unrealizedPnl: number
  positions: Position[]
  orders: SimulatedOrder[]
}

export interface MarketOrderInput {
  contestId: string
  clientOrderId: string
  symbol: CryptoSymbol
  side: OrderSide
  quantity: number
}
