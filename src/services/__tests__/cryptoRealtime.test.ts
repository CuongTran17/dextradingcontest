import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import {
  __resetCryptoRealtimeForTests,
  connectCryptoRealtime,
  cryptoRealtimeState,
  onCryptoRealtimeCandle,
  onCryptoRealtimeOrderBook,
  subscribeCryptoRealtimeSymbol,
} from '@/services/cryptoRealtime'
import type { Candle, CryptoOrderBook } from '@/types/crypto'

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onclose: (() => void) | null = null
  sent: string[] = []
  url: string

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(message: string) {
    this.sent.push(message)
  }

  close() {
    this.onclose?.()
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent<string>)
  }
}

describe('cryptoRealtime', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    __resetCryptoRealtimeForTests()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
    __resetCryptoRealtimeForTests()
  })

  it('opens one shared backend websocket connection', () => {
    connectCryptoRealtime()
    connectCryptoRealtime()

    expect(FakeWebSocket.instances).toHaveLength(1)
    expect(FakeWebSocket.instances[0].url).toBe('ws://localhost:8000/api/crypto/ws')
  })

  it('stores all-symbol prices from snapshot and prices events', () => {
    connectCryptoRealtime()
    const socket = FakeWebSocket.instances[0]

    socket.emit({
      type: 'snapshot',
      prices: { BTCUSDT: 60000, ETHUSDT: 1600 },
      connection: { status: 'connected' },
    })
    socket.emit({
      type: 'prices',
      prices: { SOLUSDT: 80 },
      event_time: 1710000000000,
    })

    expect(cryptoRealtimeState.prices.BTCUSDT).toBe(60000)
    expect(cryptoRealtimeState.prices.ETHUSDT).toBe(1600)
    expect(cryptoRealtimeState.prices.SOLUSDT).toBe(80)
    expect(cryptoRealtimeState.status).toBe('connected')
  })

  it('sends one active symbol subscription when the socket is open', () => {
    connectCryptoRealtime()
    const socket = FakeWebSocket.instances[0]
    socket.onopen?.()

    subscribeCryptoRealtimeSymbol('ETHUSDT')

    expect(socket.sent).toEqual([JSON.stringify({ type: 'subscribe', symbol: 'ETHUSDT' })])
  })

  it('routes candle and orderbook events to subscribers', () => {
    const candles: Candle[] = []
    const books: CryptoOrderBook[] = []
    onCryptoRealtimeCandle((event) => candles.push(event.candle))
    onCryptoRealtimeOrderBook((event) => books.push(event.orderbook))
    connectCryptoRealtime()
    const socket = FakeWebSocket.instances[0]

    socket.emit({
      type: 'candle',
      symbol: 'ETHUSDT',
      interval: '1m',
      closed: false,
      candle: { time: 1, open: 1, high: 2, low: 0.5, close: 1.5, volume: 10 },
    })
    socket.emit({
      type: 'orderbook',
      symbol: 'ETHUSDT',
      last_update_id: 1,
      bids: [{ price: 1, quantity: 2, total: 2 }],
      asks: [{ price: 2, quantity: 2, total: 4 }],
      spread: 1,
      mid_price: 1.5,
      source: 'binance-websocket',
    })

    expect(candles[0].close).toBe(1.5)
    expect(books[0].source).toBe('binance-websocket')
  })

  it('reconnects after close', () => {
    connectCryptoRealtime()
    FakeWebSocket.instances[0].close()

    vi.advanceTimersByTime(1000)

    expect(FakeWebSocket.instances).toHaveLength(2)
  })
})
