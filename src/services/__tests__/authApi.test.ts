import { beforeEach, describe, expect, it, vi } from 'vitest'

import { backendFetch } from '@/services/httpClient'
import { getSavedUser, getToken, register } from '@/services/authApi'

vi.mock('@/services/httpClient', () => ({
  backendFetch: vi.fn(),
  normalizeBackendUrl: () => 'http://backend',
}))

describe('authApi', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(backendFetch).mockReset()
  })

  it('registers with the backend and saves the auth session', async () => {
    vi.mocked(backendFetch).mockResolvedValue({
      message: 'registered',
      token: 'token-123',
      user: {
        id: 7,
        email: 'student@example.edu',
        phone: null,
        fullname: 'Nguyen An',
        avatar_data: null,
        role: 'user',
      },
    })

    const response = await register('student@example.edu', 'secret123', 'Nguyen An')

    expect(backendFetch).toHaveBeenCalledWith(
      'http://backend',
      '/api/auth/register',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          email: 'student@example.edu',
          password: 'secret123',
          fullname: 'Nguyen An',
          phone: null,
        }),
      }),
    )
    expect(response.token).toBe('token-123')
    expect(getToken()).toBe('token-123')
    expect(getSavedUser()?.email).toBe('student@example.edu')
  })
})
