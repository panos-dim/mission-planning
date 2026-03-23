/**
 * Debug logging utility for mission planning app.
 *
 * Set DEBUG_LEVEL in localStorage or here to control verbosity:
 * - 0: OFF (no logs)
 * - 1: API (only API requests/responses)
 * - 2: INFO (API + important state changes)
 * - 3: VERBOSE (everything)
 */

// Default to API-level logging in development
const DEFAULT_LEVEL = 1

type LogLevel = 'api' | 'info' | 'verbose' | 'warn' | 'error'

const LEVEL_MAP: Record<LogLevel, number> = {
  api: 1,
  info: 2,
  verbose: 3,
  warn: 1, // Always show warnings at level 1+
  error: 0, // Always show errors
}

function getDebugLevel(): number {
  if (typeof window === 'undefined') return DEFAULT_LEVEL
  const stored = localStorage.getItem('DEBUG_LEVEL')
  return stored ? parseInt(stored, 10) : DEFAULT_LEVEL
}

function shouldLog(level: LogLevel): boolean {
  const currentLevel = getDebugLevel()
  return currentLevel >= LEVEL_MAP[level]
}

// Styled console output
const styles = {
  api: 'color: #4CAF50; font-weight: bold',
  apiRequest: 'color: #2196F3; font-weight: bold',
  apiResponse: 'color: #4CAF50; font-weight: bold',
  info: 'color: #9C27B0',
  verbose: 'color: #607D8B',
  warn: 'color: #FF9800; font-weight: bold',
  error: 'color: #F44336; font-weight: bold',
  section: 'color: #00BCD4; font-weight: bold; font-size: 14px',
}

type DebugPayload = unknown

type OpportunityLike = {
  target?: string
  target_name?: string
  target_id?: string
  max_elevation_time?: string
  start_time?: string
  incidence_angle_deg?: number
  max_elevation?: number
}

type ScheduleItemLike = {
  target_id?: string
  value?: number
  incidence_angle?: number
  roll_angle?: number
  pitch_angle?: number
  start_time?: string
}

export const debug = {
  /**
   * Log API request
   */
  apiRequest: (endpoint: string, data?: DebugPayload) => {
    if (!shouldLog('api')) return
    console.log(`%c📤 API REQUEST: ${endpoint}`, styles.apiRequest)
    console.log(data ?? null)
  },

  /**
   * Log API response
   */
  apiResponse: (endpoint: string, data: DebugPayload, options?: { summary?: string }) => {
    if (!shouldLog('api')) return
    console.log(`%c📥 API RESPONSE: ${endpoint}`, styles.apiResponse)
    if (options?.summary) {
      console.log(`   ${options.summary}`)
    }
    console.log(data)
  },

  /**
   * Log API error
   */
  apiError: (endpoint: string, error: DebugPayload) => {
    console.log(`%c❌ API ERROR: ${endpoint}`, styles.error)
    console.error(error)
  },

  /**
   * Log important info (state changes, key events)
   */
  info: (message: string, data?: DebugPayload) => {
    if (!shouldLog('info')) return
    console.log(`%cℹ️ ${message}`, styles.info)
    if (data !== undefined) console.log(data)
  },

  /**
   * Log verbose/debug info (internal state, rendering, etc.)
   */
  verbose: (message: string, data?: DebugPayload) => {
    if (!shouldLog('verbose')) return
    console.log(`%c🔧 ${message}`, styles.verbose)
    if (data !== undefined) console.log(data)
  },

  /**
   * Log warning
   */
  warn: (message: string, data?: DebugPayload) => {
    if (!shouldLog('warn')) return
    console.log(`%c⚠️ ${message}`, styles.warn)
    if (data !== undefined) console.log(data)
  },

  /**
   * Log error
   */
  error: (message: string, data?: DebugPayload) => {
    console.log(`%c❌ ${message}`, styles.error)
    if (data !== undefined) console.error(data)
  },

  /**
   * Log section header for grouping related logs
   */
  section: (title: string) => {
    if (!shouldLog('api')) return
    console.log(`\n%c═══ ${title} ═══`, styles.section)
  },

  /**
   * Log mission opportunities in a clean table format
   */
  opportunities: (opportunities: OpportunityLike[]) => {
    if (!shouldLog('api')) return
    console.log(`%c📋 Mission Opportunities (${opportunities.length})`, styles.section)
    console.table(
      opportunities.map((opp, i) => ({
        '#': i + 1,
        Target: opp.target || opp.target_name || opp.target_id,
        Time: opp.max_elevation_time?.slice(0, 19) || opp.start_time?.slice(0, 19),
        'Off-Nadir°':
          typeof opp.incidence_angle_deg === 'number' ? opp.incidence_angle_deg.toFixed(1) : '-',
        'Max Elev°': typeof opp.max_elevation === 'number' ? opp.max_elevation.toFixed(1) : '-',
      })),
    )
  },

  /**
   * Log schedule results in a clean table format
   */
  schedule: (algorithmName: string, schedule: ScheduleItemLike[]) => {
    if (!shouldLog('api')) return
    console.log(`%c📋 ${algorithmName} Schedule (${schedule.length} items)`, styles.section)
    console.table(
      schedule.map((item, i) => ({
        '#': i + 1,
        Target: item.target_id,
        Value: item.value?.toFixed(3) || '-',
        'Off-Nadir°': Math.abs(item.incidence_angle || 0).toFixed(1),
        'Roll°': item.roll_angle?.toFixed(1) || '-',
        'Pitch°': item.pitch_angle?.toFixed(1) || '-',
        Time: item.start_time?.slice(11, 19) || '-',
      })),
    )
  },

  /**
   * Set debug level (0=off, 1=api, 2=info, 3=verbose)
   */
  setLevel: (level: number) => {
    localStorage.setItem('DEBUG_LEVEL', String(level))
    console.log(`Debug level set to ${level}`)
  },

  /**
   * Get current debug level
   */
  getLevel: (): number => getDebugLevel(),
}

// Expose to window for easy access in console
if (typeof window !== 'undefined') {
  window.debug = debug
}

export default debug
