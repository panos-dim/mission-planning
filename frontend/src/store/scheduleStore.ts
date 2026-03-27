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
  focusedTargetId: string | null
  focusedTargetCoords: { lat: number; lon: number } | null
  focusedStartTime: string | null
  focusedSatelliteId: string | null
  isolatedSatelliteId: string | null

  // Schedule viewer layer toggles (visual-only, no schedule filtering)
  schedLayerSatellites: boolean
  schedLayerGroundtracks: boolean
  schedLayerHighlight: boolean

  // Groundtrack sampling cadence (seconds); dev-only, reflected in sample-step selector
  groundtrackSampleStep: 60 | 120 | 300

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
    overrides?: {
      startTime?: string
      lat?: number
      lon?: number
      satelliteId?: string
      targetId?: string
    },
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

  /** Set the groundtrack polyline sampling cadence (dev-only). */
  setGroundtrackSampleStep: (step: 60 | 120 | 300) => void

  /** Isolate a single satellite in the schedule map review. */
  setIsolatedSatellite: (satelliteId: string | null) => void

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
  focusedTargetId: null,
  focusedTargetCoords: null,
  focusedStartTime: null,
  focusedSatelliteId: null,
  isolatedSatelliteId: null,
  schedLayerSatellites: true,
  schedLayerGroundtracks: true,
  schedLayerHighlight: true,
  groundtrackSampleStep: 120 as 60 | 120 | 300,
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

          // If the currently-focused acquisition was removed by this fetch,
          // clear all focus state so the map and timeline stay consistent.
          const { focusedAcquisitionId: currentFocusId } = get()
          const focusedStillExists =
            currentFocusId != null ? res.items.some((i) => i.id === currentFocusId) : false
          const isolatedSatelliteStillExists =
            get().isolatedSatelliteId != null
              ? res.items.some((item) => item.satellite_id === get().isolatedSatelliteId)
              : false
          const staleFields =
            currentFocusId != null && !focusedStillExists
              ? {
                  focusedAcquisitionId: null as string | null,
                  focusedTargetId: null as string | null,
                  focusedTargetCoords: null as { lat: number; lon: number } | null,
                  focusedStartTime: null as string | null,
                  focusedSatelliteId: null as string | null,
                }
              : {}
          const staleIsolation =
            get().isolatedSatelliteId != null && !isolatedSatelliteStillExists
              ? { isolatedSatelliteId: null as string | null }
              : {}

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
              ...staleFields,
              ...staleIsolation,
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
              focusedTargetId: null,
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
        const satelliteId = overrides?.satelliteId ?? item?.satellite_id ?? null
        const targetId = overrides?.targetId ?? item?.target_id ?? null
        const shouldFollowIsolation =
          satelliteId != null &&
          get().isolatedSatelliteId != null &&
          get().isolatedSatelliteId !== satelliteId

        set(
          {
            focusedAcquisitionId: id,
            focusedTargetId: targetId,
            focusedTargetCoords: coords,
            focusedStartTime: startTime,
            focusedSatelliteId: satelliteId,
            ...(shouldFollowIsolation ? { isolatedSatelliteId: satelliteId } : {}),
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

      setGroundtrackSampleStep: (step) => {
        set({ groundtrackSampleStep: step }, false, 'setGroundtrackSampleStep')
      },

      setIsolatedSatellite: (satelliteId) => {
        set({ isolatedSatelliteId: satelliteId }, false, 'setIsolatedSatellite')
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

        // Immediate first fetch so items are available without waiting a full interval
        tick()
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
