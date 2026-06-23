export class ApiError extends Error {
  status: number
  body: unknown

  constructor(status: number, message: string, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

export interface BackendFetchOptions {
  timeoutMs?: number
  retries?: number
}

const DEFAULT_TIMEOUT_MS = 15000
const RETRY_STATUS_CODES = new Set([408, 429, 500, 502, 503, 504])

export function normalizeBackendUrl(rawUrl?: string): string {
  const value = (rawUrl || '').trim()
  const hostname = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1'
  if (!value) {
    return `http://${hostname}:8000`
  }
  if (/^https?:\/\//i.test(value)) {
    let url = value.replace(/\/+$/, '')
    if (url.includes('localhost')) {
      url = url.replace('localhost', hostname)
    } else if (url.includes('127.0.0.1')) {
      url = url.replace('127.0.0.1', hostname)
    }
    return url
  }
  if (value.startsWith(':')) {
    return `http://${hostname}${value}`
  }
  let url = `http://${value}`.replace(/\/+$/, '')
  if (url.includes('localhost')) {
    url = url.replace('localhost', hostname)
  } else if (url.includes('127.0.0.1')) {
    url = url.replace('127.0.0.1', hostname)
  }
  return url
}

function isRetryableMethod(method?: string): boolean {
  return !method || method.toUpperCase() === 'GET'
}

function wait(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms)
  })
}

async function readResponseBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get('content-type') || ''
  if (contentType.includes('application/json')) {
    return response.json().catch(() => null)
  }

  return response.text().catch(() => '')
}

function errorMessageFromBody(status: number, statusText: string, body: unknown): string {
  if (body && typeof body === 'object') {
    const record = body as Record<string, unknown>
    const detail = record.detail || record.error || record.message
    if (typeof detail === 'string' && detail.trim()) {
      return detail
    }
  }

  if (typeof body === 'string' && body.trim()) {
    return body
  }

  return statusText || `Error ${status}`
}

export async function backendFetch<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
  options: BackendFetchOptions = {},
): Promise<T> {
  const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
  const retries = isRetryableMethod(init?.method) ? (options.retries ?? 1) : 0
  let lastError: unknown = null

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    const controller = new AbortController()
    const timeout = window.setTimeout(() => controller.abort(), timeoutMs)

    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...init,
        signal: init?.signal || controller.signal,
        headers: {
          'Content-Type': 'application/json',
          ...(init?.headers || {}),
        },
      })

      const body = await readResponseBody(response)

      if (!response.ok) {
        const error = new ApiError(
          response.status,
          errorMessageFromBody(response.status, response.statusText, body),
          body,
        )
        if (attempt < retries && RETRY_STATUS_CODES.has(response.status)) {
          lastError = error
          await wait(250 * (attempt + 1))
          continue
        }
        throw error
      }

      return body as T
    } catch (error) {
      lastError = error
      if (attempt >= retries || error instanceof ApiError) {
        throw error
      }
      await wait(250 * (attempt + 1))
    } finally {
      window.clearTimeout(timeout)
    }
  }

  throw lastError
}
