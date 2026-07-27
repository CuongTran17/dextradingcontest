import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, h, nextTick, toRef } from 'vue'

import { fetchLeaderboardSnapshot } from '@/services/cryptoContestApi'
import { useLeaderboardRealtime } from '../useLeaderboardRealtime'

vi.mock('@/services/cryptoContestApi', () => ({
  fetchLeaderboardSnapshot: vi.fn(),
}))

class FakeWebSocket {
  static instances: FakeWebSocket[] = []

  onopen: (() => void) | null = null
  onmessage: ((event: MessageEvent<string>) => void) | null = null
  onerror: ((err: any) => void) | null = null
  onclose: (() => void) | null = null
  sent: string[] = []
  url: string
  closed = false

  constructor(url: string) {
    this.url = url
    FakeWebSocket.instances.push(this)
  }

  send(message: string) {
    this.sent.push(message)
  }

  close() {
    this.closed = true
    this.onclose?.()
  }

  emit(message: unknown) {
    this.onmessage?.({ data: JSON.stringify(message) } as MessageEvent<string>)
  }

  triggerError() {
    this.onerror?.(new Error('WS connection error'))
    this.onclose?.()
  }
}

const TestComponent = defineComponent({
  props: {
    contestId: { type: String, required: true },
  },
  setup(props) {
    const { rows, sortBy, status, setSortBy } = useLeaderboardRealtime(toRef(props, 'contestId'))
    return { rows, sortBy, status, setSortBy }
  },
  render() {
    return h('div')
  },
})

describe('useLeaderboardRealtime composable', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.mocked(fetchLeaderboardSnapshot).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('connects to WebSocket and handles snapshot message', async () => {
    const wrapper = mount(TestComponent, {
      props: { contestId: 'my-contest' },
    })

    expect(FakeWebSocket.instances).toHaveLength(1)
    const ws = FakeWebSocket.instances[0]
    expect(ws.url).toContain('/api/leaderboard/ws/my-contest')
    expect(ws.url).toContain('sort_by=equity')
    expect(wrapper.vm.status).toBe('connecting')

    ws.emit({
      type: 'leaderboard_snapshot',
      contest_id: 'my-contest',
      sort_by: 'equity',
      updated_at: '2026-07-01T12:00:00Z',
      rows: [
        {
          rank: 1,
          user: 'Alice',
          equity: 12000,
          pnl: 2000,
          roi: 20,
          volume: 5000,
          trade_count: 5,
          last_trade: 'BTCUSDT buy',
        },
      ],
    })

    expect(wrapper.vm.status).toBe('connected')
    expect(wrapper.vm.rows).toHaveLength(1)
    expect(wrapper.vm.rows[0]).toMatchObject({
      user: 'Alice',
      tradeCount: 5,
      lastTrade: 'BTCUSDT buy',
    })
  })

  it('sends set_sort message when setSortBy is called', async () => {
    const wrapper = mount(TestComponent, {
      props: { contestId: 'my-contest' },
    })

    const ws = FakeWebSocket.instances[0]
    ws.emit({
      type: 'leaderboard_snapshot',
      contest_id: 'my-contest',
      sort_by: 'equity',
      updated_at: '2026-07-01T12:00:00Z',
      rows: [],
    })

    wrapper.vm.setSortBy('roi')
    expect(wrapper.vm.sortBy).toBe('roi')
    expect(ws.sent).toContain(JSON.stringify({ type: 'set_sort', sort_by: 'roi' }))
  })

  it('falls back to polling on WS error', async () => {
    vi.mocked(fetchLeaderboardSnapshot).mockResolvedValue([
      {
        rank: 1,
        user: 'Bob',
        equity: 11000,
        pnl: 1000,
        roi: 10,
        volume: 3000,
        tradeCount: 2,
        lastTrade: 'ETHUSDT buy',
      },
    ])

    const wrapper = mount(TestComponent, {
      props: { contestId: 'my-contest' },
    })

    const ws = FakeWebSocket.instances[0]
    ws.triggerError()

    expect(wrapper.vm.status).toBe('error')

    // Fast-forward timers to trigger polling
    await vi.advanceTimersByTimeAsync(0)
    expect(fetchLeaderboardSnapshot).toHaveBeenCalledWith('my-contest', 'equity')

    await nextTick()
    expect(wrapper.vm.rows).toHaveLength(1)
    expect(wrapper.vm.rows[0].user).toBe('Bob')
  })

  it('closes WebSocket on unmount', () => {
    const wrapper = mount(TestComponent, {
      props: { contestId: 'my-contest' },
    })

    const ws = FakeWebSocket.instances[0]
    expect(ws.closed).toBe(false)

    wrapper.unmount()
    expect(ws.closed).toBe(true)
  })
})
