/**
 * API Configuration
 * Centralized configuration for all API endpoints
 */

// Base URL from environment variable with fallback.
// Default to '' (same-origin) so requests use the Vite dev proxy (/api → localhost:8000)
// and avoid CORS preflight overhead. Set VITE_API_URL explicitly for production builds.
export const API_BASE_URL = import.meta.env.VITE_API_URL ?? ''

// API Endpoints
export const API_ENDPOINTS = {
  // Mission endpoints
  MISSION_ANALYZE: '/api/v1/mission/analyze',
  MISSION_PLAN: '/api/v1/mission/plan',

  // TLE endpoints
  TLE_VALIDATE: '/api/v1/tle/validate',
  TLE_SOURCES: '/api/v1/tle/sources',
  TLE_SEARCH: '/api/v1/tle/search',
  TLE_CATALOG: (sourceId: string) => `/api/v1/tle/catalog/${sourceId}`,

  // Config endpoints
  CONFIG_GROUND_STATIONS: '/api/v1/config/ground-stations',
  CONFIG_MISSION_SETTINGS: '/api/v1/config/mission-settings',
  CONFIG_SATELLITES: '/api/v1/config/satellites',
  CONFIG_SATELLITE_CONFIG_SUMMARY: '/api/v1/config/satellite-config-summary',
  CONFIG_SAR_MODES: '/api/v1/config/sar-modes',

  // Managed satellites endpoints (CRUD)
  SATELLITES: '/api/v1/satellites',
  SATELLITE_BY_ID: (id: string) => `/api/v1/satellites/${id}`,

  // Planning endpoints
  PLANNING_OPPORTUNITIES: '/api/v1/planning/opportunities',
  PLANNING_SCHEDULE: '/api/v1/planning/schedule',
  PLANNING_CONFIG: '/api/v1/planning/config',

  // Schedule endpoints
  SCHEDULE_COMMIT_DIRECT: '/api/v1/schedule/commit/direct',
  SCHEDULE_HORIZON: '/api/v1/schedule/horizon',
  SCHEDULE_STATE: '/api/v1/schedule/state',
  SCHEDULE_CONFLICTS: '/api/v1/schedule/conflicts',
  SCHEDULE_CONFLICTS_RECOMPUTE: '/api/v1/schedule/conflicts/recompute',
  SCHEDULE_PLAN: '/api/v1/schedule/plan',
  SCHEDULE_REPAIR: '/api/v1/schedule/repair',
  SCHEDULE_REPAIR_COMMIT: '/api/v1/schedule/repair/commit',
  SCHEDULE_COMMIT_HISTORY: '/api/v1/schedule/commit-history',
  SCHEDULE_ACQUISITION_LOCK: (id: string) => `/api/v1/schedule/acquisition/${id}/lock`,
  SCHEDULE_ACQUISITION_DELETE: (id: string) => `/api/v1/schedule/acquisition/${id}`,
  SCHEDULE_BULK_LOCK: '/api/v1/schedule/acquisitions/bulk-lock',
  SCHEDULE_BULK_DELETE: '/api/v1/schedule/acquisitions/bulk-delete',
  SCHEDULE_HARD_LOCK_COMMITTED: '/api/v1/schedule/acquisitions/hard-lock-committed',
  SCHEDULE_TARGET_LOCATIONS: '/api/v1/schedule/target-locations',
  SCHEDULE_MASTER: '/api/v1/schedule/master',

  // Orders endpoints
  ORDERS: '/api/v1/orders',
  ORDERS_INBOX: '/api/v1/orders/inbox',
  ORDERS_IMPORT: '/api/v1/orders/import',
  ORDER_BY_ID: (id: string) => `/api/v1/orders/${id}`,
  ORDER_REJECT: (id: string) => `/api/v1/orders/${id}/reject`,
  ORDER_DEFER: (id: string) => `/api/v1/orders/${id}/defer`,

  // Dev endpoints (demo runner)
  DEV_SCHEDULE_SNAPSHOT: '/api/v1/dev/schedule-snapshot',
  DEV_WRITE_ARTIFACTS: '/api/v1/dev/write-artifacts',
  DEV_METRICS: '/api/v1/dev/metrics',

  // Batching endpoints
  BATCHES: '/api/v1/batches',
  BATCHES_POLICIES: '/api/v1/batches/policies',
  BATCHES_CREATE: '/api/v1/batches/create',
  BATCH_BY_ID: (id: string) => `/api/v1/batches/${id}`,
  BATCH_PLAN: (id: string) => `/api/v1/batches/${id}/plan`,
  BATCH_COMMIT: (id: string) => `/api/v1/batches/${id}/commit`,
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
