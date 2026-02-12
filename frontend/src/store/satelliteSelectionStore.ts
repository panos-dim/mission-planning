/**
 * Satellite Selection Store
 *
 * Zustand store with persist middleware for satellite/constellation selection.
 * Replaces the raw localStorage + CustomEvent bridge between AdminPanel and MissionControls.
 *
 * Architecture (per TanStack Query best practices):
 *   - Server state (satellite list) → React Query (useManagedSatellites hook)
 *   - Client state (selection)      → This Zustand store (persisted to localStorage)
 *   - Derived state (selected TLEs) → useMemo in consuming components
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { TLEData } from '../types'

export interface SelectedSatelliteData {
  name: string
  line1: string
  line2: string
  sensor_fov_half_angle_deg?: number
  imaging_type?: string
}

interface SatelliteSelectionState {
  /** IDs of selected satellites (constellation) */
  selectedIds: string[]

  /** Full TLE data for selected satellites (derived from server data on selection) */
  selectedSatellites: SelectedSatelliteData[]

  /** Toggle a satellite in/out of the constellation */
  toggleSatellite: (id: string, satelliteData: SelectedSatelliteData) => void

  /** Set the full selection (bulk update) */
  setSelection: (ids: string[], satellites: SelectedSatelliteData[]) => void

  /** Clear all selections */
  clearSelection: () => void

  /** Remove a satellite by ID */
  removeSatellite: (id: string) => void
}

export const useSatelliteSelectionStore = create<SatelliteSelectionState>()(
  persist(
    (set, get) => ({
      selectedIds: [],
      selectedSatellites: [],

      toggleSatellite: (id, satelliteData) => {
        const { selectedIds, selectedSatellites } = get()
        const isSelected = selectedIds.includes(id)

        if (isSelected) {
          set({
            selectedIds: selectedIds.filter((sid) => sid !== id),
            selectedSatellites: selectedSatellites.filter(
              (s) => !(s.name === satelliteData.name && s.line1 === satelliteData.line1),
            ),
          })
        } else {
          set({
            selectedIds: [...selectedIds, id],
            selectedSatellites: [...selectedSatellites, satelliteData],
          })
        }
      },

      setSelection: (ids, satellites) => {
        set({ selectedIds: ids, selectedSatellites: satellites })
      },

      clearSelection: () => {
        set({ selectedIds: [], selectedSatellites: [] })
      },

      removeSatellite: (id) => {
        const { selectedIds, selectedSatellites } = get()
        const idx = selectedIds.indexOf(id)
        if (idx >= 0) {
          const newIds = selectedIds.filter((sid) => sid !== id)
          // Remove by index position to keep arrays in sync
          const newSats = selectedSatellites.filter((_, i) => i !== idx)
          set({ selectedIds: newIds, selectedSatellites: newSats })
        }
      },
    }),
    {
      name: 'satellite-selection',
      // Migrate from legacy localStorage keys on first load
      onRehydrateStorage: () => {
        return (state) => {
          if (state && state.selectedIds.length === 0) {
            // One-time migration from legacy localStorage keys
            try {
              const legacyIds = localStorage.getItem('selectedSatelliteIds')
              const legacySats = localStorage.getItem('selectedSatellites')
              if (legacyIds && legacySats) {
                const ids = JSON.parse(legacyIds) as string[]
                const sats = JSON.parse(legacySats) as SelectedSatelliteData[]
                if (ids.length > 0 && sats.length > 0) {
                  state.selectedIds = ids
                  state.selectedSatellites = sats
                }
              }
            } catch {
              // Ignore migration errors
            }
          }
        }
      },
    },
  ),
)

/**
 * Helper: Convert selected satellites to TLEData format for MissionControls form.
 */
export function toTLEDataArray(satellites: SelectedSatelliteData[]): TLEData[] {
  return satellites.map((s) => ({
    name: s.name,
    line1: s.line1,
    line2: s.line2,
    sensor_fov_half_angle_deg: s.sensor_fov_half_angle_deg,
    imaging_type: s.imaging_type as TLEData['imaging_type'],
  }))
}
