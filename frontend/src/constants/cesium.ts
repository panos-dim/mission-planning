/**
 * Cesium Constants
 * Centralized Cesium-related configuration
 */

// Timeouts
export const CESIUM_TIMEOUTS = {
  IMAGERY_FALLBACK_MS: 8000,
  CLOCK_SYNC_INTERVAL_MS: 200,
  ENTITY_RENDER_DELAY_MS: 500,
  SCENE_RENDER_SEQUENCE: [100, 200, 500, 1000, 2000],
} as const

// Camera settings
export const CAMERA = {
  MIN_ZOOM_DISTANCE: 1,
  MAX_ZOOM_DISTANCE: 100000000,
  DEFAULT_ZOOM_2D: 30000000,
  DEFAULT_ZOOM_3D: 20000000,
  FLY_TO_DURATION: 2,
  FLY_TO_OFFSET: 1000000,
} as const

// Entity styling
export const ENTITY_STYLE = {
  TARGET_POINT_SIZE: 12,
  TARGET_OUTLINE_WIDTH: 2,
  SATELLITE_POINT_SIZE: 15,
  LABEL_FONT: '14px sans-serif',
  LABEL_OFFSET_Y: -20,
  GROUND_STATION_SIZE: 28,
} as const

// Coverage visualization
export const COVERAGE = {
  FILL_ALPHA: 0.2,
  OUTLINE_WIDTH: 2,
  DEFAULT_COLOR: '#3B82F6',
} as const

// Cone visualization
export const POINTING_CONE = {
  FILL_ALPHA: 0.15,
  OUTLINE_ALPHA: 0.4,
  COLOR: '#FFA500', // Orange
  POLYGON_SIDES: 24,
  TIME_SAMPLES: 60,
} as const
