/**
 * API Configuration
 * Centralized configuration for all API endpoints
 */

// Base URL from environment variable with fallback
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// API Endpoints
export const API_ENDPOINTS = {
  // Mission endpoints
  MISSION_ANALYZE: '/api/mission/analyze',
  MISSION_PLAN: '/api/mission/plan',
  
  // TLE endpoints
  TLE_VALIDATE: '/api/tle/validate',
  TLE_SOURCES: '/api/tle/sources',
  TLE_SEARCH: '/api/tle/search',
  TLE_CATALOG: (sourceId: string) => `/api/tle/catalog/${sourceId}`,
  
  // Config endpoints
  CONFIG_GROUND_STATIONS: '/api/config/ground-stations',
  CONFIG_MISSION_SETTINGS: '/api/config/mission-settings',
  CONFIG_SATELLITES: '/api/config/satellites',
} as const

// Request timeouts (milliseconds)
export const TIMEOUTS = {
  DEFAULT: 30000,
  MISSION_ANALYSIS: 60000, // Mission analysis can take longer
  TLE_SEARCH: 15000,
} as const

// Retry configuration
export const RETRY_CONFIG = {
  MAX_RETRIES: 3,
  RETRY_DELAY_MS: 1000,
  RETRY_BACKOFF_MULTIPLIER: 2,
} as const
