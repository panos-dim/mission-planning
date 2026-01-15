/**
 * Utility functions for UI components
 */

import { type ClassValue, clsx } from 'clsx'

/**
 * Merge class names with conditional support
 * Uses clsx for conditional classes
 */
export function cn(...inputs: ClassValue[]): string {
  return clsx(inputs)
}

/**
 * Generate a unique ID for accessibility
 */
export function generateId(prefix: string = 'ui'): string {
  return `${prefix}-${Math.random().toString(36).substr(2, 9)}`
}

/**
 * Format number with proper precision
 */
export function formatNumber(value: number, decimals: number = 2): string {
  return value.toFixed(decimals)
}
