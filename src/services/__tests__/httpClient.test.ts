import { afterEach, describe, expect, it, vi } from 'vitest'

import { backendFetch } from '@/services/httpClient'

describe('httpClient', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('reports a clear timeout message instead of raw abort reason', async () => {
    vi.useFakeTimers()
    vi.spyOn(window, 'fetch').mockImplementation(
      (_input, init) => new Promise<Response>((_resolve, reject) => {
        const signal = init?.signal as AbortSignal | undefined
        signal?.addEventListener('abort', () => {
          reject(signal.reason || new DOMException('signal is aborted without reason', 'AbortError'))
        })
      }),
    )

    const request = backendFetch('http://localhost:8000', '/api/admin/crypto/overview', undefined, {
      retries: 0,
      timeoutMs: 25,
    })
    const expectation = expect(request).rejects.toThrow('Request timed out after 25ms')
    await vi.advanceTimersByTimeAsync(25)

    await expectation
  })
})
