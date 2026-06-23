import type { CryptoAsset, CryptoSymbol } from '@/types/crypto'

export const DEFAULT_CRYPTO_SYMBOL: CryptoSymbol = 'BTCUSDT'
export const DEFAULT_TRADE_PATH = `/trade/${DEFAULT_CRYPTO_SYMBOL}`

export const CRYPTO_ASSETS: CryptoAsset[] = [
  {
    symbol: 'BTCUSDT',
    baseAsset: 'BTC',
    quoteAsset: 'USDT_TEST',
    displayName: 'Bitcoin / USDT_TEST',
    pricePrecision: 2,
    quantityPrecision: 6,
  },
  {
    symbol: 'ETHUSDT',
    baseAsset: 'ETH',
    quoteAsset: 'USDT_TEST',
    displayName: 'Ethereum / USDT_TEST',
    pricePrecision: 2,
    quantityPrecision: 5,
  },
  {
    symbol: 'SOLUSDT',
    baseAsset: 'SOL',
    quoteAsset: 'USDT_TEST',
    displayName: 'Solana / USDT_TEST',
    pricePrecision: 3,
    quantityPrecision: 3,
  },
]

export function findCryptoAsset(symbol: string) {
  return CRYPTO_ASSETS.find((asset) => asset.symbol === symbol)
}
