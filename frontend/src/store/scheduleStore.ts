/**
 * Schedule Store — Zustand store for Master Schedule Timeline view.
 *
 * Manages:
 * - Visible time range (t_start, t_end)
 * - Zoom level (detail vs aggregate)
 * - Fetched master schedule data
 * - Selected acquisition for map focus
 * - Loading / error state
 * - Live polling (PR-UI-030)
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import {
  getMasterSchedule,
  type MasterScheduleItem,
  type MasterScheduleBucket,
} from '../api/scheduleApi'

// =============================================================================
// Types
// =============================================================================

export type MasterZoom = 'detail' | 'aggregate'

interface ScheduleState {
  // Time range
  tStart: string | null
  tEnd: string | null

  // Data
  items: MasterScheduleItem[]
  buckets: MasterScheduleBucket[]
  total: number
  zoom: MasterZoom

  // Fetch state
  loading: boolean
  error: string | null
  fetchMs: number | null
  lastFetchedAt: number | null

  // Selection (for map sync)
  focusedAcquisitionId: string | null
  focusedTargetCoords: { lat: number; lon: number } | null
  focusedStartTime: string | null
  focusedSatelliteId: string | null

  // Schedule viewer layer toggles (visual-only, no schedule filtering)
  schedLayerSatellites: boolean
  schedLayerGroundtracks: boolean
  schedLayerHighlight: boolean

  // Polling state (PR-UI-030)
  pollingWorkspaceId: string | null
  pollingIntervalMs: number
}

interface ScheduleActions {
  /** Fetch master schedule from backend */
  fetchMaster: (params: {
    workspace_id: string
    t_start?: string
    t_end?: string
    zoom?: MasterZoom
  }) => Promise<void>

  /** Set visible time range */
  setRange: (tStart: string, tEnd: string) => void

  /** Set zoom mode */
  setZoom: (zoom: MasterZoom) => void

  /**
   * Focus an acquisition (triggers map fly-to + clock sync).
   * Coords/startTime are resolved from loaded items; pass overrides when
   * calling from orders-derived data where items may not be loaded yet.
   */
  focusAcquisition: (
    id: string | null,
    overrides?: { startTime?: string; lat?: number; lon?: number },
  ) => void

  /**
   * Start live polling the master schedule every `intervalMs` ms.
   * Pauses automatically when the document is hidden; resumes when visible.
   * Safe to call multiple times — stops any previous polling first.
   */
  startPolling: (workspaceId: string, intervalMs?: number) => void

  /** Stop live polling and clean up listeners. */
  stopPolling: () => void

  /**
   * Toggle a schedule-view visual layer.
   * These are viewer-only and do NOT affect schedule timeline contents.
   */
  setSchedLayer: (key: 'satellites' | 'groundtracks' | 'highlight', visible: boolean) => void

  /** Clear all data */
  reset: () => void
}

export type ScheduleStore = ScheduleState & ScheduleActions

// =============================================================================
// Initial state
// =============================================================================

const INITIAL_STATE: ScheduleState = {
  tStart: null,
  tEnd: null,
  items: [],
  buckets: [],
  total: 0,
  zoom: 'detail',
  loading: false,
  error: null,
  fetchMs: null,
  lastFetchedAt: null,
  focusedAcquisitionId: null,
  focusedTargetCoords: null,
  focusedStartTime: null,
  focusedSatelliteId: null,
  schedLayerSatellites: true,
  schedLayerGroundtracks: true,
  schedLayerHighlight: true,
  pollingWorkspaceId: null,
  pollingIntervalMs: 15000,
}

// =============================================================================
// Module-level refs for polling (outside Zustand state to avoid re-renders)
// =============================================================================

let _pollingTimerId: ReturnType<typeof setInterval> | null = null
let _visibilityHandler: (() => void) | null = null

function _clearPolling() {
  if (_pollingTimerId !== null) {
    clearInterval(_pollingTimerId)
    _pollingTimerId = null
  }
  if (_visibilityHandler !== null) {
    document.removeEventListener('visibilitychange', _visibilityHandler)
    _visibilityHandler = null
  }
}

// =============================================================================
// Store
// =============================================================================

export const useScheduleStore = create<ScheduleStore>()(
  devtools(
    (set, get) => ({
      ...INITIAL_STATE,

      fetchMaster: async (params) => {
        set({ loading: true, error: null }, false, 'fetchMaster/start')

        try {
          const res = await getMasterSchedule({
            workspace_id: params.workspace_id,
            t_start: params.t_start ?? get().tStart ?? undefined,
            t_end: params.t_end ?? get().tEnd ?? undefined,
            zoom: params.zoom ?? get().zoom,
          })

          set(
            {
              items: res.items,
              buckets: res.buckets,
              total: res.total,
              zoom: res.zoom,
              tStart: res.t_start,
              tEnd: res.t_end,
              fetchMs: res.fetch_ms ?? null,
              loading: false,
              lastFetchedAt: Date.now(),
            },
            false,
            'fetchMaster/success',
          )
        } catch (err) {
          const message = err instanceof Error ? err.message : 'Failed to fetch master schedule'
          set({ loading: false, error: message }, false, 'fetchMaster/error')
        }
      },

      setRange: (tStart, tEnd) => {
        set({ tStart, tEnd }, false, 'setRange')
      },

      setZoom: (zoom) => {
        set({ zoom }, false, 'setZoom')
      },

      focusAcquisition: (id, overrides) => {
        if (!id) {
          set(
            {
              focusedAcquisitionId: null,
              focusedTargetCoords: null,
              focusedStartTime: null,
              focusedSatelliteId: null,
            },
            false,
            'focusAcquisition/clear',
          )
          return
        }

        // Resolve coords, start time, and satellite ID from loaded items; fall back to overrides
        const item = get().items.find((i) => i.id === id)
        const lat = overrides?.lat ?? item?.target_lat
        const lon = overrides?.lon ?? item?.target_lon
        const startTime = overrides?.startTime ?? item?.start_time ?? null
        const coords = lat != null && lon != null ? { lat, lon } : null
        const satelliteId = item?.satellite_id ?? null

        set(
          {
            focusedAcquisitionId: id,
            focusedTargetCoords: coords,
            focusedStartTime: startTime,
            focusedSatelliteId: satelliteId,
          },
          false,
          'focusAcquisition',
        )
      },

      setSchedLayer: (key, visible) => {
        const keyMap = {
          satellites: 'schedLayerSatellites',
          groundtracks: 'schedLayerGroundtracks',
          highlight: 'schedLayerHighlight',
        } as const
        set({ [keyMap[key]]: visible }, false, `setSchedLayer/${key}`)
      },

      startPolling: (workspaceId, intervalMs = 15000) => {
        _clearPolling()

        set(
          { pollingWorkspaceId: workspaceId, pollingIntervalMs: intervalMs },
          false,
          'startPolling',
        )

        const tick = () => {
          if (document.hidden) return
          const { tStart, tEnd, zoom } = get()
          get().fetchMaster({
            workspace_id: workspaceId,
            t_start: tStart ?? undefined,
            t_end: tEnd ?? undefined,
            zoom,
          })
        }

        // Visibility-aware resume: restart interval when tab becomes visible
        _visibilityHandler = () => {
          if (!document.hidden) {
            tick()
          }
        }
        document.addEventListener('visibilitychange', _visibilityHandler)

        _pollingTimerId = setInterval(tick, intervalMs)
      },

      stopPolling: () => {
        _clearPolling()
        set({ pollingWorkspaceId: null }, false, 'stopPolling')
      },

      reset: () => {
        _clearPolling()
        set(INITIAL_STATE, false, 'reset')
      },
    }),
    {
      name: 'ScheduleStore',
      enabled: import.meta.env?.DEV ?? false,
    },
  ),
)
