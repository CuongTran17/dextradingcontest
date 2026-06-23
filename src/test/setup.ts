import { afterEach, vi } from 'vitest'

afterEach(() => {
  vi.useRealTimers()
  window.localStorage.clear()
})
