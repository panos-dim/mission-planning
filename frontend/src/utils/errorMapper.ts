/**
 * Error Message Mapper
 * Maps API errors to user-friendly messages with suggested actions
 * Per UX_MINIMAL_SPEC.md Section 6: Error Message Templates
 */

import { isApiError, isNetworkError, isTimeoutError } from '../api/errors'

export interface MappedError {
  code: string
  message: string
  suggestion: string
  severity: 'error' | 'warning' | 'info'
  technical?: string // Only logged in dev mode
}

/**
 * Error codes used throughout the application
 */
export const ERROR_CODES = {
  // Analysis errors
  NO_SATELLITES: 'NO_SATELLITES',
  NO_TARGETS: 'NO_TARGETS',
  INVALID_TIMERANGE: 'INVALID_TIMERANGE',
  NO_OPPORTUNITIES: 'NO_OPPORTUNITIES',
  ANALYSIS_FAILED: 'ANALYSIS_FAILED',

  // Planning errors
  PLANNING_FAILED: 'PLANNING_FAILED',
  NO_OPPORTUNITIES_TO_SCHEDULE: 'NO_OPPORTUNITIES_TO_SCHEDULE',

  // Commit errors
  CONFLICT_BLOCK: 'CONFLICT_BLOCK',
  HARD_LOCK_BLOCK: 'HARD_LOCK_BLOCK',
  ALREADY_COMMITTED: 'ALREADY_COMMITTED',

  // Generic errors
  NETWORK_ERROR: 'NETWORK_ERROR',
  TIMEOUT_ERROR: 'TIMEOUT_ERROR',
  SERVER_ERROR: 'SERVER_ERROR',
  UNKNOWN_ERROR: 'UNKNOWN_ERROR',
  NOT_FOUND: 'NOT_FOUND',
  VALIDATION_ERROR: 'VALIDATION_ERROR',
} as const

/**
 * Error message templates per UX_MINIMAL_SPEC.md
 */
const ERROR_TEMPLATES: Record<string, Omit<MappedError, 'code' | 'technical'>> = {
  // Analysis errors
  [ERROR_CODES.NO_SATELLITES]: {
    message: 'No satellites selected',
    suggestion: 'Go to Admin Panel to select satellites for your constellation.',
    severity: 'error',
  },
  [ERROR_CODES.NO_TARGETS]: {
    message: 'No targets configured',
    suggestion: 'Add at least one target location in the Feasibility Analysis panel.',
    severity: 'error',
  },
  [ERROR_CODES.INVALID_TIMERANGE]: {
    message: 'Invalid time window',
    suggestion: 'End time must be after start time. Please adjust your time range.',
    severity: 'error',
  },
  [ERROR_CODES.NO_OPPORTUNITIES]: {
    message: 'No imaging windows found',
    suggestion: 'Try extending the time range or adjusting satellite constraints.',
    severity: 'warning',
  },
  [ERROR_CODES.ANALYSIS_FAILED]: {
    message: 'Mission analysis failed',
    suggestion: 'Check your configuration and try again. Contact support if the issue persists.',
    severity: 'error',
  },

  // Planning errors
  [ERROR_CODES.NO_OPPORTUNITIES_TO_SCHEDULE]: {
    message: 'No opportunities to schedule',
    suggestion: 'Run Feasibility Analysis first to generate imaging opportunities.',
    severity: 'warning',
  },
  [ERROR_CODES.PLANNING_FAILED]: {
    message: 'Planning algorithm failed',
    suggestion: 'Check target constraints and try again with different parameters.',
    severity: 'error',
  },

  // Commit errors
  [ERROR_CODES.CONFLICT_BLOCK]: {
    message: 'Cannot apply: conflicts exist',
    suggestion: 'Use Repair mode to resolve scheduling conflicts before applying.',
    severity: 'error',
  },
  [ERROR_CODES.HARD_LOCK_BLOCK]: {
    message: 'Cannot modify hard-locked acquisition',
    suggestion: 'Contact administrator to unlock the acquisition.',
    severity: 'error',
  },
  [ERROR_CODES.ALREADY_COMMITTED]: {
    message: 'Plan already applied',
    suggestion: 'Generate a new plan to make additional changes.',
    severity: 'warning',
  },

  // Generic errors
  [ERROR_CODES.NETWORK_ERROR]: {
    message: 'Network connection error',
    suggestion: 'Check your internet connection and try again.',
    severity: 'error',
  },
  [ERROR_CODES.TIMEOUT_ERROR]: {
    message: 'Request timed out',
    suggestion: 'The server is taking too long to respond. Please try again.',
    severity: 'error',
  },
  [ERROR_CODES.SERVER_ERROR]: {
    message: 'Server error occurred',
    suggestion: 'Please try again later. Contact support if the issue persists.',
    severity: 'error',
  },
  [ERROR_CODES.NOT_FOUND]: {
    message: 'Resource not found',
    suggestion: 'The requested data could not be found. It may have been deleted.',
    severity: 'warning',
  },
  [ERROR_CODES.VALIDATION_ERROR]: {
    message: 'Invalid input provided',
    suggestion: 'Please check your input and correct any errors.',
    severity: 'error',
  },
  [ERROR_CODES.UNKNOWN_ERROR]: {
    message: 'An unexpected error occurred',
    suggestion: 'Please try again. Contact support if the issue persists.',
    severity: 'error',
  },
}

/**
 * Detect error code from API response or error object
 */
function detectErrorCode(error: unknown, context?: string): string {
  // Check for ApiError with specific status codes
  if (isApiError(error)) {
    if (error.isServerError) return ERROR_CODES.SERVER_ERROR
    if (error.isNotFound) return ERROR_CODES.NOT_FOUND

    // Check response data for specific error codes
    const data = error.data as { detail?: string; code?: string; message?: string } | undefined
    if (data?.code) return data.code

    // Parse error messages for known patterns
    const detail = data?.detail?.toLowerCase() || data?.message?.toLowerCase() || ''

    if (detail.includes('no satellites') || detail.includes('satellite')) {
      return ERROR_CODES.NO_SATELLITES
    }
    if (detail.includes('no targets') || detail.includes('target')) {
      return ERROR_CODES.NO_TARGETS
    }
    if (detail.includes('no opportunities') || detail.includes('no imaging')) {
      return ERROR_CODES.NO_OPPORTUNITIES
    }
    if (detail.includes('conflict')) {
      return ERROR_CODES.CONFLICT_BLOCK
    }
    if (detail.includes('hard lock') || detail.includes('hard-lock')) {
      return ERROR_CODES.HARD_LOCK_BLOCK
    }
    if (detail.includes('already committed')) {
      return ERROR_CODES.ALREADY_COMMITTED
    }
    if (detail.includes('invalid time') || detail.includes('time range')) {
      return ERROR_CODES.INVALID_TIMERANGE
    }
    if (error.status === 422) {
      return ERROR_CODES.VALIDATION_ERROR
    }
  }

  if (isNetworkError(error)) return ERROR_CODES.NETWORK_ERROR
  if (isTimeoutError(error)) return ERROR_CODES.TIMEOUT_ERROR

  // Context-based fallbacks
  if (context === 'analysis') return ERROR_CODES.ANALYSIS_FAILED
  if (context === 'planning') return ERROR_CODES.PLANNING_FAILED

  return ERROR_CODES.UNKNOWN_ERROR
}

/**
 * Map any error to a user-friendly message with suggestions
 */
export function mapError(error: unknown, context?: string): MappedError {
  const code = detectErrorCode(error, context)
  const template = ERROR_TEMPLATES[code] || ERROR_TEMPLATES[ERROR_CODES.UNKNOWN_ERROR]

  const mapped: MappedError = {
    code,
    ...template,
  }

  // Add technical details for dev mode logging
  if (import.meta.env.DEV) {
    if (error instanceof Error) {
      mapped.technical = error.message
    } else if (typeof error === 'string') {
      mapped.technical = error
    } else {
      mapped.technical = JSON.stringify(error)
    }
  }

  return mapped
}

/**
 * Get user-friendly error message string
 */
export function getErrorMessage(error: unknown, context?: string): string {
  const mapped = mapError(error, context)
  return mapped.message
}

/**
 * Get error message with suggestion
 */
export function getErrorWithSuggestion(error: unknown, context?: string): string {
  const mapped = mapError(error, context)
  return `${mapped.message}. ${mapped.suggestion}`
}

/**
 * Log error details to console (only technical details in dev mode)
 */
export function logError(error: unknown, context?: string): void {
  const mapped = mapError(error, context)

  if (import.meta.env.DEV && mapped.technical) {
    console.error(`[${mapped.code}] ${mapped.message}`, {
      technical: mapped.technical,
      context,
      severity: mapped.severity,
    })
  } else {
    console.error(`[${mapped.code}] ${mapped.message}`)
  }
}

/**
 * Create a formatted error for display in UI components
 */
export function formatErrorForUI(
  error: unknown,
  context?: string,
): {
  title: string
  description: string
  severity: 'error' | 'warning' | 'info'
} {
  const mapped = mapError(error, context)
  return {
    title: mapped.message,
    description: mapped.suggestion,
    severity: mapped.severity,
  }
}
