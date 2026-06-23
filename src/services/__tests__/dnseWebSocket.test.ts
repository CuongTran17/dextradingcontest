import { beforeEach, describe, expect, it, vi } from 'vitest'
import { DnseWebSocketService } from '@/services/dnseWebSocket'

class MockWebSocket {
  static OPEN = 1
  static instances: MockWebSocket[] = []
  readyState = 0
  onopen: (() => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: (() => void) | null = null
  onmessage: (() => void) | null = null
  send = vi.fn()
  close = vi.fn()

  constructor() {
    MockWebSocket.instances.push(this)
  }

  disconnect(): void {
    this.onclose?.({ code: 1006, reason: 'test' } as CloseEvent)
  }
}

describe('DnseWebSocketService', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.spyOn(console, 'warn').mockImplementation(() => {})
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  it('can retry a connection after reconnect attempts enter fallback', async () => {
    const service = new DnseWebSocketService()
    const statuses: string[] = []
    service.onConnectionChange((status) => statuses.push(status))

    service.connect()
    MockWebSocket.instances[0].disconnect()
    await vi.advanceTimersByTimeAsync(3000)
    MockWebSocket.instances[1].disconnect()
    await vi.advanceTimersByTimeAsync(4500)
    MockWebSocket.instances[2].disconnect()

    expect(statuses).toContain('fallback')
    service.retryConnection()
    expect(MockWebSocket.instances).toHaveLength(4)
  })
})
