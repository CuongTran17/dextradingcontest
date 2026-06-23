import { describe, expect, it, vi } from 'vitest'
import { createSymbolRegistry } from '@/realtime/symbolRegistry'
import { createStockPriceStore } from '@/stores/stockPriceStore'
import { createRealtimeManager } from '@/realtime/realtimeManager'

function createWebSocketStub() {
  let connectionListener: ((status: 'connected' | 'disconnected' | 'error' | 'fallback') => void) | null = null
  return {
    connect: vi.fn(),
    retryConnection: vi.fn(),
    destroy: vi.fn(),
    subscribe: vi.fn(() => vi.fn()),
    onConnectionChange: vi.fn((listener) => {
      connectionListener = listener
      return vi.fn()
    }),
    emit(status: 'connected' | 'disconnected' | 'error' | 'fallback') {
      connectionListener?.(status)
    },
  }
}

describe('realtimeManager', () => {
  it('starts once and synchronizes active symbols', async () => {
    const registry = createSymbolRegistry()
    const webSocket = createWebSocketStub()
    const manager = createRealtimeManager({
      registry,
      priceStore: createStockPriceStore(),
      webSocketService: webSocket,
      snapshotApi: { checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }), getSnapshots: vi.fn() },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()
    await manager.start()
    registry.replaceSymbols('page', ['FPT'])

    expect(webSocket.connect).toHaveBeenCalledTimes(1)
    expect(webSocket.subscribe).toHaveBeenCalledWith('FPT', expect.any(Function))
  })

  it('polls only active symbols after fallback without overlapping requests', async () => {
    vi.useFakeTimers()
    const registry = createSymbolRegistry()
    registry.replaceSymbols('page', ['FPT', 'VCB'])
    const webSocket = createWebSocketStub()
    let resolveSnapshots!: (value: { data: never[] }) => void
    const getSnapshots = vi.fn(() => new Promise<{ data: never[] }>((resolve) => {
      resolveSnapshots = resolve
    }))
    const manager = createRealtimeManager({
      registry,
      priceStore: createStockPriceStore(),
      webSocketService: webSocket,
      snapshotApi: { checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }), getSnapshots },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()
    webSocket.emit('fallback')
    const first = manager.pollNow()
    const second = manager.pollNow()

    expect(getSnapshots).toHaveBeenCalledTimes(1)
    expect(getSnapshots).toHaveBeenCalledWith(['FPT', 'VCB'])
    resolveSnapshots({ data: [] })
    await Promise.all([first, second])
  })

  it('does not connect after being stopped while the health check is pending', async () => {
    const registry = createSymbolRegistry()
    const webSocket = createWebSocketStub()
    let resolveHealth!: (value: { status: string }) => void
    const manager = createRealtimeManager({
      registry,
      priceStore: createStockPriceStore(),
      webSocketService: webSocket,
      snapshotApi: {
        checkHealth: vi.fn(() => new Promise<{ status: string }>((resolve) => {
          resolveHealth = resolve
        })),
        getSnapshots: vi.fn(),
      },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    const starting = manager.start()
    manager.stop()
    resolveHealth({ status: 'ok' })
    await starting

    expect(webSocket.connect).toHaveBeenCalledTimes(1)
    expect(webSocket.destroy).toHaveBeenCalledTimes(1)
  })

  it('connects WebSocket without waiting for the health check', async () => {
    const registry = createSymbolRegistry()
    const webSocket = createWebSocketStub()
    let resolveHealth!: (value: { status: string }) => void
    const manager = createRealtimeManager({
      registry,
      priceStore: createStockPriceStore(),
      webSocketService: webSocket,
      snapshotApi: {
        checkHealth: vi.fn(() => new Promise<{ status: string }>((resolve) => {
          resolveHealth = resolve
        })),
        getSnapshots: vi.fn(),
      },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    const starting = manager.start()
    expect(webSocket.connect).toHaveBeenCalledTimes(1)

    resolveHealth({ status: 'ok' })
    await starting
  })

  it('keeps the backend available when health is degraded by optional services', async () => {
    const registry = createSymbolRegistry()
    const webSocket = createWebSocketStub()
    const priceStore = createStockPriceStore()
    const manager = createRealtimeManager({
      registry,
      priceStore,
      webSocketService: webSocket,
      snapshotApi: {
        checkHealth: vi.fn().mockResolvedValue({ status: 'degraded' }),
        getSnapshots: vi.fn(),
      },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()

    expect(priceStore.backendAvailable.value).toBe(true)
  })

  it('polls active symbols immediately when WebSocket enters fallback', async () => {
    const registry = createSymbolRegistry()
    registry.replaceSymbols('page', ['FPT'])
    const webSocket = createWebSocketStub()
    const getSnapshots = vi.fn().mockResolvedValue({ data: [] })
    const manager = createRealtimeManager({
      registry,
      priceStore: createStockPriceStore(),
      webSocketService: webSocket,
      snapshotApi: { checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }), getSnapshots },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()
    webSocket.emit('fallback')
    await vi.waitFor(() => expect(getSnapshots).toHaveBeenCalledWith(['FPT']))
  })

  it('returns to polling mode after a polling request recovers', async () => {
    const registry = createSymbolRegistry()
    registry.replaceSymbols('page', ['FPT'])
    const webSocket = createWebSocketStub()
    const priceStore = createStockPriceStore()
    const getSnapshots = vi.fn()
      .mockRejectedValueOnce(new Error('temporary failure'))
      .mockResolvedValueOnce({ data: [] })
    const manager = createRealtimeManager({
      registry,
      priceStore,
      webSocketService: webSocket,
      snapshotApi: { checkHealth: vi.fn().mockResolvedValue({ status: 'ok' }), getSnapshots },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()
    webSocket.emit('fallback')
    await vi.waitFor(() => expect(priceStore.connectionMode.value).toBe('offline'))

    await manager.pollNow()
    expect(priceStore.connectionMode.value).toBe('polling')
  })

  it('ignores a polling response that finishes after the manager stops', async () => {
    const registry = createSymbolRegistry()
    registry.replaceSymbols('page', ['FPT'])
    const webSocket = createWebSocketStub()
    const priceStore = createStockPriceStore()
    let resolveSnapshots!: (value: { data: never[] }) => void
    const manager = createRealtimeManager({
      registry,
      priceStore,
      webSocketService: webSocket,
      snapshotApi: {
        checkHealth: vi.fn().mockRejectedValue(new Error('offline')),
        getSnapshots: vi.fn(() => new Promise<{ data: never[] }>((resolve) => {
          resolveSnapshots = resolve
        })),
      },
      pollingMs: 5000,
      retryRealtimeMs: 30000,
    })

    await manager.start()
    webSocket.emit('fallback')
    manager.stop()
    resolveSnapshots({ data: [] })
    await vi.waitFor(() => expect(priceStore.connectionMode.value).toBe('idle'))

    expect(priceStore.backendAvailable.value).toBe(false)
    expect(priceStore.lastRefreshAt.value).toBeNull()
  })
})
