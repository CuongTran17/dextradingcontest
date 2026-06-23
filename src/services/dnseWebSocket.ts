/**
 * DNSE Lightspeed WebSocket Service
 * ====================================
 * Kết nối WebSocket real-time cho giá cổ phiếu.
 * Sử dụng STOMP over WebSocket hoặc native WebSocket.
 */

export interface RealtimeQuote {
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

type QuoteCallback = (quote: RealtimeQuote) => void
type ConnectionCallback = (status: 'connected' | 'disconnected' | 'error' | 'fallback') => void

const _backendBase = (import.meta.env.VITE_BACKEND_URL || '').trim().replace(/\/+$/, '')
const WS_URL = (() => {
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1'
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss' : 'ws'
  if (_backendBase) {
    let wsBase = _backendBase.replace(/^http/, 'ws')
    if (wsBase.includes('localhost')) {
      wsBase = wsBase.replace('localhost', hostname)
    } else if (wsBase.includes('127.0.0.1')) {
      wsBase = wsBase.replace('127.0.0.1', hostname)
    }
    return wsBase + '/api/ws/dnse'
  }
  return `${protocol}://${window.location.host}/api/ws/dnse`
})()
const RECONNECT_DELAY = 3000
const MAX_RECONNECT_ATTEMPTS = 2
const HEARTBEAT_INTERVAL = 30000
const DEBUG_WS = import.meta.env.VITE_DEBUG_WS === 'true'

function debugWs(message: string): void {
  if (DEBUG_WS) {
    console.debug(message)
  }
}

export class DnseWebSocketService {
  private ws: WebSocket | null = null
  private subscribers: Map<string, Set<QuoteCallback>> = new Map()
  private connectionCallbacks: Set<ConnectionCallback> = new Set()
  private reconnectAttempts = 0
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null
  private isConnecting = false
  private token: string | null = null
  private subscribedSymbols: Set<string> = new Set()
  private fallbackMode = false

  /**
   * Kết nối WebSocket
   */
  connect(token?: string): void {
    if (this.fallbackMode) {
      this.notifyConnectionStatus('fallback')
      return
    }

    if (this.ws?.readyState === WebSocket.OPEN || this.isConnecting) return

    this.token = token || this.token
    this.isConnecting = true

    try {
      this.ws = new WebSocket(WS_URL)

      this.ws.onopen = () => {
        this.isConnecting = false
        this.reconnectAttempts = 0
        debugWs('[DNSE WS] Connected via wrapper')
        this.notifyConnectionStatus('connected')
        this.startHeartbeat()

        // Resubscribe symbols after reconnecting
        this.subscribedSymbols.forEach((symbol) => {
          this.sendSubscribe(symbol)
        })
      }

      this.ws.onclose = (event) => {
        this.isConnecting = false
        this.ws = null
        this.stopHeartbeat()
        debugWs(`[DNSE WS] Disconnected. Code: ${event.code}, Reason: ${event.reason}`)
        this.notifyConnectionStatus('disconnected')
        this.scheduleReconnect()
      }

      this.ws.onerror = (error) => {
        console.error('[DNSE WS] WebSocket error:', error)
        this.ws?.close() // Force close and trigger onclose handler
      }

      this.ws.onmessage = (event) => {
        this.handleMessage(event.data)
      }
    } catch (err) {
      this.isConnecting = false
      console.error('[DNSE WS] Connection exception:', err)
      this.scheduleReconnect()
    }
  }

  /**
   * Ngắt kết nối
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    this.stopHeartbeat()
    this.reconnectAttempts = MAX_RECONNECT_ATTEMPTS // Prevent reconnect
    this.isConnecting = false
    this.fallbackMode = false

    if (this.ws) {
      this.ws.onclose = null // Prevent reconnect trigger
      this.ws.close()
      this.ws = null
    }

  }

  retryConnection(): void {
    this.fallbackMode = false
    this.reconnectAttempts = 0
    this.connect()
  }

  destroy(): void {
    this.disconnect()
    this.subscribers.clear()
    this.subscribedSymbols.clear()
    this.connectionCallbacks.clear()
  }

  /**
   * Đăng ký nhận giá real-time cho 1 mã
   */
  subscribe(symbol: string, callback: QuoteCallback): () => void {
    const upperSymbol = symbol.toUpperCase()

    if (!this.subscribers.has(upperSymbol)) {
      this.subscribers.set(upperSymbol, new Set())
    }
    this.subscribers.get(upperSymbol)!.add(callback)
    this.subscribedSymbols.add(upperSymbol)

    // Gửi subscribe nếu đã kết nối
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendSubscribe(upperSymbol)
    }

    // Trả về hàm unsubscribe
    return () => {
      const subs = this.subscribers.get(upperSymbol)
      if (subs) {
        subs.delete(callback)
        if (subs.size === 0) {
          this.subscribers.delete(upperSymbol)
          this.subscribedSymbols.delete(upperSymbol)
          this.sendUnsubscribe(upperSymbol)
        }
      }
    }
  }

  /**
   * Đăng ký nhiều mã cùng lúc
   */
  subscribeMultiple(symbols: string[], callback: QuoteCallback): () => void {
    const unsubscribers = symbols.map((s) => this.subscribe(s, callback))
    return () => unsubscribers.forEach((unsub) => unsub())
  }

  /**
   * Lắng nghe trạng thái kết nối
   */
  onConnectionChange(callback: ConnectionCallback): () => void {
    this.connectionCallbacks.add(callback)
    return () => this.connectionCallbacks.delete(callback)
  }

  /**
   * Kiểm tra đã kết nối chưa
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }

  get connectionState(): 'connected' | 'connecting' | 'fallback' | 'disconnected' {
    if (this.isConnected) return 'connected'
    if (this.isConnecting) return 'connecting'
    if (this.fallbackMode) return 'fallback'
    return 'disconnected'
  }

  // --- Private methods ---

  private sendSubscribe(symbol: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return

    // DNSE sử dụng STOMP-like protocol
    const message = JSON.stringify({
      action: 'subscribe',
      data: { symbol, channel: 'stock' },
    })
    this.ws.send(message)
  }

  private sendUnsubscribe(symbol: string): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return

    const message = JSON.stringify({
      action: 'unsubscribe',
      data: { symbol, channel: 'stock' },
    })
    this.ws.send(message)
  }

  private handleMessage(rawData: string): void {
    try {
      const data = JSON.parse(rawData)

      // Bỏ qua heartbeat/pong
      if (data.type === 'pong' || data.type === 'heartbeat') return

      const quote = this.parseQuoteMessage(data)
      if (quote && this.subscribers.has(quote.symbol)) {
        this.subscribers.get(quote.symbol)!.forEach((cb) => cb(quote))
      }
    } catch {
      // Binary message or non-JSON — skip
    }
  }

  private parseQuoteMessage(data: any): RealtimeQuote | null {
    // Xử lý nhiều format response từ DNSE
    const symbol = data.symbol || data.code || data.s
    if (!symbol) return null

    return {
      symbol: symbol.toUpperCase(),
      price: data.matchedPrice || data.lastPrice || data.price || data.p || 0,
      change: data.change || data.priceChange || 0,
      changePercent: data.changePercent || data.pctChange || 0,
      volume: data.volume || data.matchedVolume || data.v || 0,
      high: data.high || data.highPrice || data.h || 0,
      low: data.low || data.lowPrice || data.l || 0,
      open: data.open || data.openPrice || data.o || 0,
      time: data.time || data.t || new Date().toISOString(),
    }
  }

  private scheduleReconnect(): void {
    if (this.fallbackMode) return

    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      this.enableFallbackMode('Max reconnect attempts reached')
      return
    }

    const delay = RECONNECT_DELAY * Math.pow(1.5, this.reconnectAttempts)
    this.reconnectAttempts++

    debugWs(`[DNSE WS] Reconnecting in ${Math.round(delay / 1000)}s (attempt ${this.reconnectAttempts})`)
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null
      this.connect()
    }, delay)
  }

  private enableFallbackMode(reason: string): void {
    this.fallbackMode = true

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }

    console.warn(`[DNSE WS] ${reason}. Switching to polling fallback`)
    this.notifyConnectionStatus('fallback')
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, HEARTBEAT_INTERVAL)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private notifyConnectionStatus(status: 'connected' | 'disconnected' | 'error' | 'fallback'): void {
    this.connectionCallbacks.forEach((cb) => cb(status))
  }
}

// Singleton instance
export const dnseWebSocket = new DnseWebSocketService()
export default dnseWebSocket
