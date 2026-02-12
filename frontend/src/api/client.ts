/**
 * API Client
 * Centralized HTTP client with error handling, timeouts, and retry logic
 */

import { API_BASE_URL, TIMEOUTS, RETRY_CONFIG } from './config'
import { ApiError, NetworkError, TimeoutError } from './errors'
import debug from '../utils/debug'

interface RequestOptions extends Omit<RequestInit, 'body'> {
  timeout?: number
  retries?: number
  body?: unknown
}

interface ApiResponse<T> {
  data: T
  status: number
  headers: Headers
}

/**
 * Sleep utility for retry delays
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * Create an AbortController with timeout
 */
function createTimeoutController(timeoutMs: number): {
  controller: AbortController
  timeoutId: ReturnType<typeof setTimeout>
} {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  return { controller, timeoutId }
}

/**
 * Core fetch wrapper with error handling
 */
async function fetchWithErrorHandling<T>(
  url: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const { timeout = TIMEOUTS.DEFAULT, retries: _retries = 0, body, ...fetchOptions } = options

  const { controller, timeoutId } = createTimeoutController(timeout)

  // Merge signals if one was provided
  const signal = options.signal ? anySignal([options.signal, controller.signal]) : controller.signal

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal,
      body: body ? JSON.stringify(body) : undefined,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions.headers,
      },
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      let errorData: unknown
      try {
        errorData = await response.json()
      } catch {
        // Response body is not JSON
      }
      throw new ApiError(response, errorData)
    }

    const data = (await response.json()) as T

    return {
      data,
      status: response.status,
      headers: response.headers,
    }
  } catch (error) {
    clearTimeout(timeoutId)

    if (error instanceof ApiError) {
      throw error
    }

    if (error instanceof Error) {
      if (error.name === 'AbortError') {
        // Check if it was our timeout or external abort
        if (controller.signal.aborted && !options.signal?.aborted) {
          throw new TimeoutError(timeout)
        }
        throw error // Re-throw if externally aborted
      }
      throw new NetworkError(`Failed to fetch ${url}`, error)
    }

    throw error
  }
}

/**
 * Combine multiple AbortSignals into one
 */
function anySignal(signals: (AbortSignal | undefined)[]): AbortSignal {
  const controller = new AbortController()

  for (const signal of signals) {
    if (!signal) continue
    if (signal.aborted) {
      controller.abort()
      break
    }
    signal.addEventListener('abort', () => controller.abort(), { once: true })
  }

  return controller.signal
}

/**
 * Fetch with automatic retry on failure
 */
async function fetchWithRetry<T>(
  url: string,
  options: RequestOptions = {},
): Promise<ApiResponse<T>> {
  const maxRetries = options.retries ?? RETRY_CONFIG.MAX_RETRIES
  let lastError: Error | undefined

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await fetchWithErrorHandling<T>(url, options)
    } catch (error) {
      lastError = error as Error

      // Don't retry on client errors (4xx) or abort
      if (error instanceof ApiError && error.status < 500) {
        throw error
      }

      if (error instanceof Error && error.name === 'AbortError') {
        throw error
      }

      // Wait before retry with exponential backoff
      if (attempt < maxRetries) {
        const delay =
          RETRY_CONFIG.RETRY_DELAY_MS * Math.pow(RETRY_CONFIG.RETRY_BACKOFF_MULTIPLIER, attempt)
        debug.warn(`Request failed, retrying in ${delay}ms (attempt ${attempt + 1}/${maxRetries})`)
        await sleep(delay)
      }
    }
  }

  throw lastError
}

/**
 * API Client with typed methods
 */
export const apiClient = {
  /**
   * GET request
   */
  async get<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    debug.apiRequest(`GET ${endpoint}`)

    const response = await fetchWithRetry<T>(url, {
      ...options,
      method: 'GET',
    })

    debug.apiResponse(`GET ${endpoint}`, response.data)
    return response.data
  },

  /**
   * POST request
   */
  async post<T, D = unknown>(endpoint: string, data: D, options?: RequestOptions): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    debug.apiRequest(`POST ${endpoint}`, data)

    const response = await fetchWithRetry<T>(url, {
      ...options,
      method: 'POST',
      body: data,
    })

    debug.apiResponse(`POST ${endpoint}`, response.data)
    return response.data
  },

  /**
   * PUT request
   */
  async put<T, D = unknown>(endpoint: string, data: D, options?: RequestOptions): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    debug.apiRequest(`PUT ${endpoint}`, data)

    const response = await fetchWithRetry<T>(url, {
      ...options,
      method: 'PUT',
      body: data,
    })

    debug.apiResponse(`PUT ${endpoint}`, response.data)
    return response.data
  },

  /**
   * DELETE request
   */
  async delete<T>(endpoint: string, options?: RequestOptions): Promise<T> {
    const url = `${API_BASE_URL}${endpoint}`
    debug.apiRequest(`DELETE ${endpoint}`)

    const response = await fetchWithRetry<T>(url, {
      ...options,
      method: 'DELETE',
    })

    debug.apiResponse(`DELETE ${endpoint}`, response.data)
    return response.data
  },
}

export default apiClient
