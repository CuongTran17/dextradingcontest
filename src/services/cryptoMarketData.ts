import type { Candle, CryptoSymbol, Timeframe } from '@/types/crypto'

const BASE_PRICES: Record<CryptoSymbol, number> = {
  BTCUSDT: 64250,
  ETHUSDT: 3420,
  SOLUSDT: 148,
}

const TIMEFRAME_SECONDS: Record<Timeframe, number> = {
  '1m': 60,
  '5m': 300,
  '15m': 900,
  '1h': 3600,
  '4h': 14400,
  '1D': 86400,
}

function getSymbolPhase(symbol: CryptoSymbol): number {
  return symbol.split('').reduce((sum, char) => sum + char.charCodeAt(0), 0)
}

export function getLatestCryptoPrice(symbol: CryptoSymbol): number {
  return BASE_PRICES[symbol]
}

export function getCryptoCandles(
  symbol: CryptoSymbol,
  timeframe: Timeframe,
  count: number,
): Candle[] {
  const safeCount = Math.max(0, Math.floor(count))
  const basePrice = BASE_PRICES[symbol]
  const stepSeconds = TIMEFRAME_SECONDS[timeframe]
  const phase = getSymbolPhase(symbol)
  const lastClosedTime = Math.floor(Date.now() / 1000 / stepSeconds) * stepSeconds
  const firstTime = lastClosedTime - (safeCount - 1) * stepSeconds

  return Array.from({ length: safeCount }, (_, index) => {
    const wave = Math.sin((index + phase) / 4)
    const trend = (index - safeCount / 2) * basePrice * 0.0007
    const open = basePrice + trend + wave * basePrice * 0.006
    const close = open + Math.cos((index + phase) / 3) * basePrice * 0.003
    const high = Math.max(open, close) * 1.002
    const low = Math.min(open, close) * 0.998

    return {
      time: firstTime + index * stepSeconds,
      open,
      high,
      low,
      close,
      volume: 1000 + Math.abs(wave) * 5000 + index * 25,
    }
  })
}
