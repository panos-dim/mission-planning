/**
 * API Response Validation Utilities
 * Validates API responses at runtime using Zod schemas
 */

import { z } from 'zod'
import { ValidationError } from './errors'
import debug from '../utils/debug'

/**
 * Validate API response against a Zod schema
 * In development, logs warnings but still returns data
 * In production, throws ValidationError on failure
 */
export function validateResponse<T extends z.ZodTypeAny>(
  schema: T,
  data: unknown,
  context?: string
): z.infer<T> {
  const result = schema.safeParse(data)
  
  if (!result.success) {
    const errorMessage = `API Response Validation Failed${context ? ` (${context})` : ''}`
    const errors = result.error.format()
    
    // Always log validation errors
    debug.warn(errorMessage, {
      errors,
      receivedData: data,
    })
    
    // In development, return data as-is to not break the app
    // In production, you might want to throw or handle differently
    if (import.meta.env.DEV) {
      debug.warn('Returning unvalidated data in development mode')
      return data as z.infer<T>
    }
    
    throw new ValidationError(errorMessage, errors)
  }
  
  return result.data
}

/**
 * Create a validated API response handler
 * Returns a function that validates and returns typed data
 */
export function createValidator<T extends z.ZodTypeAny>(schema: T, context?: string) {
  return (data: unknown): z.infer<T> => validateResponse(schema, data, context)
}

/**
 * Partial validation - only validates if schema is provided
 * Useful for gradual migration to strict validation
 */
export function optionalValidate<T extends z.ZodTypeAny>(
  schema: T | undefined,
  data: unknown,
  context?: string
): z.infer<T> | unknown {
  if (!schema) {
    return data
  }
  return validateResponse(schema, data, context)
}
