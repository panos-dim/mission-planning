/**
 * Simple Mode Configuration
 * Controls which UI panels are visible in the default "Mission Planner" mode
 * vs. advanced/debug modes for developers and admins.
 */

// Check URL params for debug flags
const getUrlParams = () => {
  if (typeof window === 'undefined') return new URLSearchParams()
  return new URLSearchParams(window.location.search)
}

// URL-based debug flags (legacy support)
export const isDebugExplorerEnabled = () => getUrlParams().get('debug') === 'explorer'
export const isDebugModeFromUrl = () => getUrlParams().has('debug')
export const isAdvancedPlanningEnabled = () =>
  getUrlParams().get('debug') === 'planning' || getUrlParams().get('debug') === 'all'

// Combined check: URL debug OR UI toggle set to developer
// Note: For store-based check, import useVisStore and check uiMode === "developer"
// This function only checks URL - components should also check uiMode from store
export const isDebugMode = () => isDebugModeFromUrl()

/**
 * Left Sidebar Panel Configuration
 * In Simple Mode, only 4 panels are visible by default
 */
export const LEFT_SIDEBAR_PANELS = {
  // Simple Mode panels (visible by default)
  WORKSPACES: 'workspaces',
  MISSION_ANALYSIS: 'mission',
  PLANNING: 'planning',
  SCHEDULE: 'schedule',
  EXPLORER: 'explorer', // Object Explorer - useful for planners to browse mission data
} as const

export const SIMPLE_MODE_LEFT_PANELS = [
  LEFT_SIDEBAR_PANELS.WORKSPACES,
  LEFT_SIDEBAR_PANELS.MISSION_ANALYSIS,
  LEFT_SIDEBAR_PANELS.PLANNING,
  LEFT_SIDEBAR_PANELS.SCHEDULE,
  LEFT_SIDEBAR_PANELS.EXPLORER, // Now visible to planners
] as const

export const DEBUG_LEFT_PANELS = [] as const // No debug-only left panels

/**
 * Right Sidebar Panel Configuration
 * In Simple Mode, only 3 panels are visible
 */
export const RIGHT_SIDEBAR_PANELS = {
  // Core panels (always visible)
  INSPECTOR: 'inspector',
  LAYERS: 'layers',
  MISSION_RESULTS: 'mission',
  AI_ASSISTANT: 'ai_assistant',
} as const

export const SIMPLE_MODE_RIGHT_PANELS = [
  RIGHT_SIDEBAR_PANELS.MISSION_RESULTS,
  RIGHT_SIDEBAR_PANELS.INSPECTOR,
  RIGHT_SIDEBAR_PANELS.LAYERS,
  RIGHT_SIDEBAR_PANELS.AI_ASSISTANT,
] as const

/**
 * Schedule Panel Tab Configuration
 */
// PR-OPS-REPAIR-DEFAULT-01: Added TIMELINE tab
export const SCHEDULE_TABS = {
  COMMITTED: 'committed',
  TIMELINE: 'timeline',
  HISTORY: 'history', // Admin only
} as const

export const SIMPLE_MODE_SCHEDULE_TABS = [SCHEDULE_TABS.COMMITTED, SCHEDULE_TABS.TIMELINE] as const

/**
 * Table Pagination Configuration
 */
export const TABLE_CONFIG = {
  DEFAULT_PAGE_SIZE: 50,
  PAGE_SIZE_OPTIONS: [25, 50, 100, 200],
  VIRTUALIZATION_THRESHOLD: 100, // Use virtualization above this row count
} as const

/**
 * Default collapsed sections in Simple Mode
 */
export const COLLAPSED_BY_DEFAULT = {
  planningAdvanced: true,
  weightSliders: true,
  repairSettings: true,
  satelliteConfig: true, // Collapse if pre-selected
} as const
