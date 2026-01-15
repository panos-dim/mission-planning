/**
 * API Error Classes
 * Structured error handling for API operations
 */

export class ApiError extends Error {
  public readonly status: number
  public readonly statusText: string
  public readonly url: string
  public readonly data?: unknown

  constructor(response: Response, data?: unknown) {
    super(`API Error: ${response.status} ${response.statusText}`)
    this.name = 'ApiError'
    this.status = response.status
    this.statusText = response.statusText
    this.url = response.url
    this.data = data
  }

  get isNotFound(): boolean {
    return this.status === 404
  }

  get isUnauthorized(): boolean {
    return this.status === 401
  }

  get isForbidden(): boolean {
    return this.status === 403
  }

  get isServerError(): boolean {
    return this.status >= 500
  }

  get isNetworkError(): boolean {
    return this.status === 0
  }
}

export class NetworkError extends Error {
  public readonly originalError: Error

  constructor(message: string, originalError: Error) {
    super(message)
    this.name = 'NetworkError'
    this.originalError = originalError
  }
}

export class TimeoutError extends Error {
  public readonly timeoutMs: number

  constructor(timeoutMs: number) {
    super(`Request timed out after ${timeoutMs}ms`)
    this.name = 'TimeoutError'
    this.timeoutMs = timeoutMs
  }
}

export class ValidationError extends Error {
  public readonly errors: unknown

  constructor(message: string, errors: unknown) {
    super(message)
    this.name = 'ValidationError'
    this.errors = errors
  }
}

/**
 * Type guard to check if an error is an ApiError
 */
export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

/**
 * Type guard to check if an error is a NetworkError
 */
export function isNetworkError(error: unknown): error is NetworkError {
  return error instanceof NetworkError
}

/**
 * Type guard to check if an error is a TimeoutError
 */
export function isTimeoutError(error: unknown): error is TimeoutError {
  return error instanceof TimeoutError
}

/**
 * Extract user-friendly error message from any error
 */
export function getErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.isServerError) {
      return 'Server error. Please try again later.'
    }
    if (error.isNotFound) {
      return 'Resource not found.'
    }
    return error.message
  }
  
  if (isNetworkError(error)) {
    return 'Network error. Please check your connection.'
  }
  
  if (isTimeoutError(error)) {
    return 'Request timed out. Please try again.'
  }
  
  if (error instanceof Error) {
    return error.message
  }
  
  return 'An unexpected error occurred.'
}
