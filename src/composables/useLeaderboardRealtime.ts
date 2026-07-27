import { onUnmounted, ref, watch, type Ref } from 'vue'

import { fetchLeaderboardSnapshot } from '@/services/cryptoContestApi'
import type { LeaderboardRow, LeaderboardSortBy, LeaderboardWsMessage } from '@/types/crypto'

export function useLeaderboardRealtime(contestId: Ref<string>) {
  const rows = ref<LeaderboardRow[]>([])
  const sortBy = ref<LeaderboardSortBy>('equity')
  const status = ref<'connecting' | 'connected' | 'error'>('connecting')

  let socket: WebSocket | null = null
  let pollIntervalId: any = null
  let isCleanedUp = false

  function getWsUrl(): string {
    const backend = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'
    const url = new URL(backend)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    url.pathname = `/api/leaderboard/ws/${encodeURIComponent(contestId.value)}`
    url.search = `?sort_by=${encodeURIComponent(sortBy.value)}`
    return url.toString()
  }

  function startPolling() {
    if (pollIntervalId) return
    void doPoll()
    pollIntervalId = setInterval(doPoll, 10000)
  }

  function stopPolling() {
    if (pollIntervalId) {
      clearInterval(pollIntervalId)
      pollIntervalId = null
    }
  }

  async function doPoll() {
    try {
      const freshRows = await fetchLeaderboardSnapshot(contestId.value, sortBy.value)
      if (!isCleanedUp && status.value === 'error') {
        rows.value = processRows(freshRows, sortBy.value)
      }
    } catch (err) {
      console.error('Leaderboard polling fallback failed:', err)
    }
  }

  function processRows(rawRows: any[], criterion: LeaderboardSortBy): LeaderboardRow[] {
    const mapped = rawRows.map((row) => ({
      rank: row.rank,
      user: row.user,
      equity: Number(row.equity),
      pnl: Number(row.pnl),
      roi: Number(row.roi),
      volume: Number(row.volume),
      tradeCount: row.tradeCount !== undefined ? row.tradeCount : row.trade_count,
      lastTrade: row.lastTrade !== undefined ? row.lastTrade : row.last_trade,
    }))

    // Sort descending by selected criterion
    mapped.sort((a, b) => b[criterion] - a[criterion])

    // Re-assign ranks to be 1..N based on sorted order
    return mapped.map((row, index) => ({
      ...row,
      rank: index + 1,
    }))
  }

  function connect() {
    disconnect()
    if (isCleanedUp) return

    status.value = 'connecting'
    try {
      const url = getWsUrl()
      socket = new WebSocket(url)

      socket.onopen = () => {
        // Socket opened successfully. We wait for snapshot message to set status = 'connected'
      }

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as LeaderboardWsMessage
          if (data.type === 'leaderboard_snapshot' || data.type === 'leaderboard_update') {
            status.value = 'connected'
            stopPolling()
            rows.value = processRows(data.rows, sortBy.value)
            lastUpdated.value = new Date()
          } else if (data.type === 'error') {
            console.error('Leaderboard WS error:', data.message)
          }
        } catch (err) {
          console.error('Error parsing WS message:', err)
        }
      }

      socket.onerror = (err) => {
        console.error('Leaderboard WS connection error:', err)
        handleFailure()
      }

      socket.onclose = () => {
        handleFailure()
      }
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
      handleFailure()
    }
  }

  function handleFailure() {
    if (status.value !== 'error') {
      status.value = 'error'
      startPolling()
    }
  }

  function disconnect() {
    if (socket) {
      socket.onopen = null
      socket.onmessage = null
      socket.onerror = null
      socket.onclose = null
      try {
        socket.close()
      } catch (err) {
        // ignore
      }
      socket = null
    }
  }

  function setSortBy(sort: LeaderboardSortBy) {
    if (sortBy.value === sort) return
    sortBy.value = sort

    if (socket && status.value === 'connected') {
      try {
        socket.send(JSON.stringify({ type: 'set_sort', sort_by: sort }))
      } catch (err) {
        console.error('Failed to send set_sort message:', err)
        connect()
      }
    } else {
      connect()
    }
  }

  // Watch for contestId change
  watch(contestId, () => {
    connect()
  })

  // Initial connection
  connect()

  onUnmounted(() => {
    isCleanedUp = true
    disconnect()
    stopPolling()
  })

  const lastUpdated = ref<Date>(new Date())

  async function refresh() {
    try {
      const freshRows = await fetchLeaderboardSnapshot(contestId.value, sortBy.value)
      rows.value = processRows(freshRows, sortBy.value)
      lastUpdated.value = new Date()
    } catch (err) {
      console.error('Leaderboard refresh failed:', err)
    }
  }

  return {
    rows,
    sortBy,
    status,
    lastUpdated,
    setSortBy,
    refresh,
  }
}
