/**
 * Schedule Store — Zustand store for Master Schedule Timeline view.
 *
 * Manages:
 * - Visible time range (t_start, t_end)
 * - Zoom level (detail vs aggregate)
 * - Fetched master schedule data
 * - Selected acquisition for map focus
 * - Loading / error state
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

  /** Focus an acquisition (triggers map fly-to) */
  focusAcquisition: (id: string | null) => void

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

      focusAcquisition: (id) => {
        if (!id) {
          set(
            { focusedAcquisitionId: null, focusedTargetCoords: null },
            false,
            'focusAcquisition/clear',
          )
          return
        }

        // Find coordinates from items
        const item = get().items.find((i) => i.id === id)
        const coords =
          item?.target_lat != null && item?.target_lon != null
            ? { lat: item.target_lat, lon: item.target_lon }
            : null

        set(
          { focusedAcquisitionId: id, focusedTargetCoords: coords },
          false,
          'focusAcquisition',
        )
      },

      reset: () => {
        set(INITIAL_STATE, false, 'reset')
      },
    }),
    {
      name: 'ScheduleStore',
      enabled: import.meta.env?.DEV ?? false,
    },
  ),
)
