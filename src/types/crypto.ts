export type CryptoSymbol = 'BTCUSDT' | 'ETHUSDT' | 'SOLUSDT'
export type ContestStatus = 'practice' | 'upcoming' | 'active' | 'ended'
export type OrderSide = 'buy' | 'sell'
export type Timeframe = '1m' | '5m' | '15m' | '1h' | '4h' | '1D'

export interface Candle {
  time: number
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface CryptoAsset {
  symbol: CryptoSymbol
  baseAsset: 'BTC' | 'ETH' | 'SOL'
  quoteAsset: 'USDT_TEST'
  displayName: string
  pricePrecision: number
  quantityPrecision: number
}

export interface Contest {
  id: string
  title: string
  status: ContestStatus
  mode: 'practice' | 'contest'
  initialCapital: number
  symbols: CryptoSymbol[]
  startsAt: string
  endsAt: string
  participantCount: number
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

export interface VirtualPortfolio {
  contestId: string
  cash: number
  positions: Position[]
  orders: SimulatedOrder[]
}
