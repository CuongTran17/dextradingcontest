import type {
  MarketIndexHistoryResponse,
  TechnicalResponse,
  TradingSignals,
} from '@/services/stockBackendApi'
import { stockBackendApi } from '@/services/stockBackendApi'

function round(value: number, digits = 2): number {
  if (!Number.isFinite(value)) return 0
  return Number(value.toFixed(digits))
}

function rollingAverage(values: number[], period: number): number[] {
  return values.map((_, index) => {
    const start = Math.max(0, index - period + 1)
    const window = values.slice(start, index + 1)
    return round(window.reduce((sum, value) => sum + value, 0) / window.length)
  })
}

function exponentialAverage(values: number[], period: number): number[] {
  const multiplier = 2 / (period + 1)
  const output: number[] = []
  values.forEach((value, index) => {
    if (index === 0) {
      output.push(round(value))
      return
    }
    output.push(round((value - output[index - 1]) * multiplier + output[index - 1]))
  })
  return output
}

function standardDeviation(values: number[]): number {
  if (!values.length) return 0
  const mean = values.reduce((sum, value) => sum + value, 0) / values.length
  const variance = values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / values.length
  return Math.sqrt(variance)
}

function bollingerBands(values: number[], period: number): { middle: number[]; upper: number[]; lower: number[] } {
  const middle = rollingAverage(values, period)
  const upper: number[] = []
  const lower: number[] = []
  values.forEach((_, index) => {
    const start = Math.max(0, index - period + 1)
    const window = values.slice(start, index + 1)
    const deviation = standardDeviation(window)
    upper.push(round(middle[index] + deviation * 2))
    lower.push(round(middle[index] - deviation * 2))
  })
  return { middle, upper, lower }
}

function rsi(values: number[], period: number): number[] {
  return values.map((_, index) => {
    if (index === 0) return 50
    const start = Math.max(1, index - period + 1)
    let gains = 0
    let losses = 0
    for (let i = start; i <= index; i += 1) {
      const delta = values[i] - values[i - 1]
      if (delta >= 0) gains += delta
      else losses += Math.abs(delta)
    }
    if (losses === 0) return gains > 0 ? 100 : 50
    const relativeStrength = gains / losses
    return round(100 - 100 / (1 + relativeStrength))
  })
}

function trueRange(high: number[], low: number[], close: number[], index: number): number {
  if (index === 0) return high[index] - low[index]
  return Math.max(
    high[index] - low[index],
    Math.abs(high[index] - close[index - 1]),
    Math.abs(low[index] - close[index - 1]),
  )
}

function atr(high: number[], low: number[], close: number[], period: number): number[] {
  const ranges = close.map((_, index) => trueRange(high, low, close, index))
  return rollingAverage(ranges, period)
}

function obv(close: number[], volume: number[]): number[] {
  const output: number[] = []
  close.forEach((value, index) => {
    if (index === 0) {
      output.push(volume[index] || 0)
      return
    }
    const previous = output[index - 1]
    if (value > close[index - 1]) output.push(previous + (volume[index] || 0))
    else if (value < close[index - 1]) output.push(previous - (volume[index] || 0))
    else output.push(previous)
  })
  return output
}

function stochastic(close: number[], high: number[], low: number[], period: number): { k: number[]; d: number[] } {
  const k = close.map((value, index) => {
    const start = Math.max(0, index - period + 1)
    const highest = Math.max(...high.slice(start, index + 1))
    const lowest = Math.min(...low.slice(start, index + 1))
    if (highest === lowest) return 50
    return round(((value - lowest) / (highest - lowest)) * 100)
  })
  return { k, d: rollingAverage(k, 3) }
}

function buildSignals(close: number[], sma200: number[], rsi14: number[], macdLine: number[], macdSignal: number[]): TradingSignals {
  const lastClose = close.at(-1) || 0
  const lastSma200 = sma200.at(-1) || 0
  const lastRsi = rsi14.at(-1) || 50
  const lastMacd = macdLine.at(-1) || 0
  const lastSignal = macdSignal.at(-1) || 0
  const previousSma50 = rollingAverage(close, 50).at(-2) || 0
  const previousSma200 = sma200.at(-2) || 0
  const currentSma50 = rollingAverage(close, 50).at(-1) || 0

  const rsiSignal = lastRsi >= 70 ? 'overbought' : lastRsi <= 30 ? 'oversold' : 'neutral'
  const macd = lastMacd >= lastSignal ? 'bullish' : 'bearish'
  const priceVsSma200 = lastClose >= lastSma200 ? 'above' : 'below'
  const goldenCross = previousSma50 <= previousSma200 && currentSma50 > lastSma200
  let score = 0
  if (macd === 'bullish') score += 1
  else score -= 1
  if (priceVsSma200 === 'above') score += 1
  else score -= 1
  if (rsiSignal === 'oversold') score += 1
  if (rsiSignal === 'overbought') score -= 1
  if (goldenCross) score += 1

  const summary: TradingSignals['summary'] =
    score >= 3 ? 'strong_buy' :
    score === 2 ? 'buy' :
    score <= -3 ? 'strong_sell' :
    score === -2 ? 'sell' :
    'neutral'

  return {
    rsi: rsiSignal,
    macd,
    golden_cross: goldenCross,
    price_vs_sma200: priceVsSma200,
    summary,
  }
}

export function buildMarketIndexTechnicalResponse(history: MarketIndexHistoryResponse): TechnicalResponse {
  const rows = [...history.data].sort((a, b) => String(a.time).localeCompare(String(b.time)))
  const time = rows.map((row) => String(row.time))
  const open = rows.map((row) => round(Number(row.open)))
  const high = rows.map((row) => round(Number(row.high)))
  const low = rows.map((row) => round(Number(row.low)))
  const close = rows.map((row) => round(Number(row.close)))
  const volume = rows.map((row) => Number(row.volume) || 0)
  const ema12 = exponentialAverage(close, 12)
  const ema26 = exponentialAverage(close, 26)
  const macdLine = close.map((_, index) => round(ema12[index] - ema26[index]))
  const macdSignal = exponentialAverage(macdLine, 9)
  const macdHistogram = macdLine.map((value, index) => round(value - macdSignal[index]))
  const bands = bollingerBands(close, 20)
  const stochasticSeries = stochastic(close, high, low, 14)
  const sma200 = rollingAverage(close, 200)
  const rsi14 = rsi(close, 14)

  return {
    symbol: history.symbol.toUpperCase(),
    count: rows.length,
    source: history.source,
    last_synced_at: history.last_synced_at,
    data_status: history.data_status,
    ohlcv: { time, open, high, low, close, volume },
    indicators: {
      sma_20: rollingAverage(close, 20),
      sma_50: rollingAverage(close, 50),
      sma_200: sma200,
      ema_12: ema12,
      ema_26: ema26,
      rsi_14: rsi14,
      macd_line: macdLine,
      macd_signal: macdSignal,
      macd_histogram: macdHistogram,
      bb_upper: bands.upper,
      bb_middle: bands.middle,
      bb_lower: bands.lower,
      stoch_k: stochasticSeries.k,
      stoch_d: stochasticSeries.d,
      atr_14: atr(high, low, close, 14),
      obv: obv(close, volume),
    },
    signals: buildSignals(close, sma200, rsi14, macdLine, macdSignal),
  }
}

export async function fetchMarketIndexTechnicalAnalysis(
  indexSymbol: string,
  limit: number,
  refresh: boolean = false,
): Promise<TechnicalResponse | null> {
  const response = await stockBackendApi.getMarketIndexHistory(
    indexSymbol,
    undefined,
    undefined,
    limit,
    refresh,
  )
  if (response.count === 0 || response.data_status === 'NO_DATA_IN_SNAPSHOT') {
    return null
  }
  return buildMarketIndexTechnicalResponse(response)
}
