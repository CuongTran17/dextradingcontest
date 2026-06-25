/**
 * DNSE Lightspeed API Service
 * ============================
 * REST API client for DNSE market data.
 * Docs: https://docs.lightspeed.dnse.com.vn/
 */

// In development the Vite dev server proxies /dnse-proxy/* to services.entrade.com.vn,
// removing CORS restrictions. In production the FastAPI backend is the primary
// data source; direct DNSE calls are a last-resort fallback and may be blocked
// by the browser if the backend is unavailable.
const _DNSE_ORIGIN = import.meta.env.DEV ? '' : 'https://services.entrade.com.vn'
const AUTH_URL = `${_DNSE_ORIGIN}/dnse-proxy/dnse-user-service/api`

export interface StockQuote {
  symbol: string
  companyName: string
  price: number
  change: number
  changePercent: number
  open: number
  high: number
  low: number
  close: number
  volume: number
  refPrice: number
  ceilingPrice: number
  floorPrice: number
  totalValue: number
  updatedAt: string
}

export interface OHLCVData {
  time: string
  open: number
  high: number
  low: number
  close: number
  volume: number
}

export interface DividendData {
  symbol: string
  exDate: string
  payDate: string
  amount: number
  type: string // 'cash' | 'stock'
}

export interface AuthTokens {
  accessToken: string
  refreshToken: string
  expiresIn: number
}

/**
 * @deprecated Direct DNSE browser calls are not part of the production data path.
 * Use backend-backed services such as stockBackendApi or dnseTickSandboxApi instead.
 */
class DnseApiService {
  private accessToken: string | null = null
  private tokenExpiry: number = 0

  /**
   * Đăng nhập DNSE để lấy token
   */
  async login(username: string, password: string): Promise<AuthTokens> {
    const response = await fetch(`${AUTH_URL}/auth`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })

    if (!response.ok) {
      throw new Error(`Login failed: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()
    this.accessToken = data.accessToken || data.token
    this.tokenExpiry = Date.now() + (data.expiresIn || 3600) * 1000
    return data
  }

  /**
   * Set token thủ công (khi đã có token)
   */
  setToken(token: string): void {
    this.accessToken = token
    this.tokenExpiry = Date.now() + 3600 * 1000
  }

  /**
   * Headers chung cho API calls
   */
  private getHeaders(): Record<string, string> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    }
    if (this.accessToken) {
      headers['Authorization'] = `Bearer ${this.accessToken}`
    }
    return headers
  }

  async getStockQuote(symbol: string): Promise<StockQuote> {
    // API is offline (404), throw immediately to trigger fallback without console errors
    throw new Error(`DNSE API Offline. Failed to fetch quote for ${symbol}`);
  }

  async getStockList(_market: string = 'VN30'): Promise<StockQuote[]> {
    throw new Error(`DNSE API Offline. Failed to fetch stock list`);
  }

  async getHistoricalData(
    symbol: string,
    _resolution: string = '1D',
    _from?: number,
    _to?: number,
  ): Promise<OHLCVData[]> {
    throw new Error(`DNSE API Offline. Failed to fetch historical data for ${symbol}`);
  }

  /**
   * Lấy nhiều cổ phiếu cùng lúc
   */
  async getMultipleQuotes(symbols: string[]): Promise<StockQuote[]> {
    const promises = symbols.map((symbol) =>
      this.getStockQuote(symbol).catch(() => {
        // console.warn(`Failed to fetch ${symbol}:`, err)
        return null
      }),
    )
    const results = await Promise.all(promises)
    return results.filter((r): r is StockQuote => r !== null)
  }

  /**
   * Map API response sang StockQuote interface
   */
  private mapToStockQuote(data: any, symbol: string): StockQuote {
    return {
      symbol: data.symbol || data.code || symbol,
      companyName: data.companyName || data.name || data.stockName || symbol,
      price: data.matchedPrice || data.lastPrice || data.price || 0,
      change: data.change || data.priceChange || 0,
      changePercent: data.changePercent || data.pctChange || data.percentChange || 0,
      open: data.open || data.openPrice || 0,
      high: data.high || data.highPrice || 0,
      low: data.low || data.lowPrice || 0,
      close: data.close || data.matchedPrice || data.lastPrice || 0,
      volume: data.volume || data.matchedVolume || data.totalVolume || 0,
      refPrice: data.refPrice || data.referencePrice || 0,
      ceilingPrice: data.ceilingPrice || data.ceiling || 0,
      floorPrice: data.floorPrice || data.floor || 0,
      totalValue: data.totalValue || data.value || 0,
      updatedAt: data.updatedAt || data.time || new Date().toISOString(),
    }
  }

  /**
   * Map OHLCV response
   */
  private mapToOHLCV(data: any): OHLCVData[] {
    // DNSE trả về dạng arrays: t[], o[], h[], l[], c[], v[]
    if (data.t && Array.isArray(data.t)) {
      return data.t.map((timestamp: number, i: number) => ({
        time: new Date(timestamp * 1000).toISOString(),
        open: data.o[i],
        high: data.h[i],
        low: data.l[i],
        close: data.c[i],
        volume: data.v[i],
      }))
    }

    // Fallback: array of objects
    if (Array.isArray(data)) {
      return data.map((item: any) => ({
        time: item.time || item.date,
        open: item.open || item.o,
        high: item.high || item.h,
        low: item.low || item.l,
        close: item.close || item.c,
        volume: item.volume || item.v,
      }))
    }

    return []
  }
}

// Singleton instance
export const dnseApi = new DnseApiService()
export default dnseApi
