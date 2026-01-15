/**
 * UI Constants
 * Centralized UI-related magic numbers and configuration
 */

// Sidebar dimensions
export const SIDEBAR = {
  MIN_WIDTH: 432,
  MAX_WIDTH: 864,
  DEFAULT_WIDTH: 432,
  ICON_BAR_WIDTH: 48,
} as const

// Animation durations (milliseconds)
export const ANIMATION = {
  SIDEBAR_TRANSITION: 300,
  MODAL_TRANSITION: 200,
  TOOLTIP_DELAY: 500,
  DEBOUNCE_DEFAULT: 300,
  THROTTLE_DEFAULT: 100,
} as const

// Z-index layers
export const Z_INDEX = {
  SIDEBAR: 40,
  HEADER: 50,
  MODAL: 60,
  TOOLTIP: 70,
  NOTIFICATION: 80,
} as const

// Breakpoints
export const BREAKPOINTS = {
  SM: 640,
  MD: 768,
  LG: 1024,
  XL: 1280,
  '2XL': 1536,
} as const

// Colors (for programmatic use)
export const COLORS = {
  PRIMARY: '#3B82F6', // blue-500
  SUCCESS: '#22C55E', // green-500
  WARNING: '#F59E0B', // amber-500
  ERROR: '#EF4444', // red-500
  INFO: '#06B6D4', // cyan-500
} as const
