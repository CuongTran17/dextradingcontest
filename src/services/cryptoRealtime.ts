import { reactive } from 'vue'

import type { Candle, CryptoOrderBook, CryptoSymbol } from '@/types/crypto'

type ConnectionStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'unavailable'

interface CandleEvent {
  symbol: CryptoSymbol
  interval: '1m'
  closed: boolean
  candle: Candle
}

interface OrderBookEvent {
  symbol: CryptoSymbol
  orderbook: CryptoOrderBook
}

interface SnapshotMessage {
  type: 'snapshot'
  prices?: Partial<Record<CryptoSymbol, number>>
  connection?: { status?: ConnectionStatus }
}

interface PricesMessage {
  type: 'prices'
  prices: Partial<Record<CryptoSymbol, number>>
  event_time?: number
}

interface CandleMessage extends CandleEvent {
  type: 'candle'
}

interface OrderBookMessage extends CryptoOrderBook {
  type: 'orderbook'
}

type RealtimeMessage = SnapshotMessage | PricesMessage | CandleMessage | OrderBookMessage

export const cryptoRealtimeState = reactive({
  status: 'idle' as ConnectionStatus,
  lastMessageAt: 0,
  prices: {} as Partial<Record<CryptoSymbol, number>>,
  selectedSymbol: null as CryptoSymbol | null,
})

const candleHandlers = new Set<(event: CandleEvent) => void>()
const orderBookHandlers = new Set<(event: OrderBookEvent) => void>()

let socket: WebSocket | null = null
let socketOpen = false
let reconnectTimer: number | undefined

export function connectCryptoRealtime(): void {
  if (socket) return
  cryptoRealtimeState.status = cryptoRealtimeState.status === 'idle' ? 'connecting' : 'reconnecting'
  socket = new WebSocket(getRealtimeUrl())
  socketOpen = false
  socket.onopen = () => {
    socketOpen = true
    cryptoRealtimeState.status = 'connected'
    if (cryptoRealtimeState.selectedSymbol) {
      sendSubscription(cryptoRealtimeState.selectedSymbol)
    }
  }
  socket.onmessage = (event) => {
    handleMessage(JSON.parse(event.data) as RealtimeMessage)
  }
  socket.onclose = () => {
    socket = null
    socketOpen = false
    cryptoRealtimeState.status = 'reconnecting'
    scheduleReconnect()
  }
}

export function subscribeCryptoRealtimeSymbol(symbol: CryptoSymbol): void {
  cryptoRealtimeState.selectedSymbol = symbol
  connectCryptoRealtime()
  if (socketOpen) {
    sendSubscription(symbol)
  }
}

export function onCryptoRealtimeCandle(handler: (event: CandleEvent) => void): () => void {
  candleHandlers.add(handler)
  return () => candleHandlers.delete(handler)
}

export function onCryptoRealtimeOrderBook(handler: (event: OrderBookEvent) => void): () => void {
  orderBookHandlers.add(handler)
  return () => orderBookHandlers.delete(handler)
}

export function __resetCryptoRealtimeForTests(): void {
  if (reconnectTimer) window.clearTimeout(reconnectTimer)
  reconnectTimer = undefined
  socket = null
  socketOpen = false
  candleHandlers.clear()
  orderBookHandlers.clear()
  cryptoRealtimeState.status = 'idle'
  cryptoRealtimeState.lastMessageAt = 0
  cryptoRealtimeState.selectedSymbol = null
  for (const key of Object.keys(cryptoRealtimeState.prices) as CryptoSymbol[]) {
    delete cryptoRealtimeState.prices[key]
  }
}

function handleMessage(message: RealtimeMessage): void {
  cryptoRealtimeState.lastMessageAt = Date.now()
  if (message.type === 'snapshot') {
    Object.assign(cryptoRealtimeState.prices, message.prices ?? {})
    cryptoRealtimeState.status = message.connection?.status ?? 'connected'
    return
  }
  if (message.type === 'prices') {
    Object.assign(cryptoRealtimeState.prices, message.prices)
    return
  }
  if (message.type === 'candle') {
    candleHandlers.forEach((handler) => handler(message))
    return
  }
  if (message.type === 'orderbook') {
    const { type, ...orderbook } = message
    void type
    orderBookHandlers.forEach((handler) =>
      handler({ symbol: message.symbol, orderbook: orderbook as CryptoOrderBook }),
    )
  }
}

function sendSubscription(symbol: CryptoSymbol): void {
  socket?.send(JSON.stringify({ type: 'subscribe', symbol }))
}

function scheduleReconnect(): void {
  if (reconnectTimer) return
  reconnectTimer = window.setTimeout(() => {
    reconnectTimer = undefined
    connectCryptoRealtime()
  }, 1000)
}

function getRealtimeUrl(): string {
  const backend = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
  const url = new URL(backend)
  url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
  url.pathname = '/api/crypto/ws'
  url.search = ''
  return url.toString()
}
