import { describe, expect, it } from 'vitest'
import { isBackendAvailableHealth } from '@/services/stockBackendApi'

describe('isBackendAvailableHealth', () => {
  it('treats degraded health as available when optional services are down', () => {
    expect(isBackendAvailableHealth({ status: 'degraded' })).toBe(true)
  })

  it('treats error health as unavailable', () => {
    expect(isBackendAvailableHealth({ status: 'error' })).toBe(false)
  })
})
