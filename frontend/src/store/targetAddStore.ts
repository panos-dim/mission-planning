/**
 * Zustand store for managing target add mode state
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

interface PendingTarget {
  id: string
  latitude: number
  longitude: number
  name?: string
  description?: string
}

interface TargetAddState {
  // Target add mode
  isAddMode: boolean
  pendingTarget: PendingTarget | null
  isDetailsSheetOpen: boolean

  // Live preview state — synced from form for real-time globe updates
  pendingLabel: string
  pendingColor: string

  // Actions
  enableAddMode: () => void
  disableAddMode: () => void
  toggleAddMode: () => void
  setPendingTarget: (target: PendingTarget | null) => void
  setPendingPreview: (label: string, color: string) => void
  openDetailsSheet: () => void
  closeDetailsSheet: () => void
  clearPendingTarget: () => void
}

export const useTargetAddStore = create<TargetAddState>()(
  devtools(
    (set, get) => ({
      // Initial state
      isAddMode: false,
      pendingTarget: null,
      isDetailsSheetOpen: false,
      pendingLabel: '',
      pendingColor: '#3B82F6',

      // Actions
      enableAddMode: () => {
        set({ isAddMode: true })
      },

      disableAddMode: () => {
        // Clear pending target when exiting add mode
        set({
          isAddMode: false,
          pendingTarget: null,
          isDetailsSheetOpen: false,
          pendingLabel: '',
          pendingColor: '#3B82F6',
        })
      },

      toggleAddMode: () => {
        const { isAddMode, disableAddMode, enableAddMode } = get()
        if (isAddMode) {
          disableAddMode()
        } else {
          enableAddMode()
        }
      },

      setPendingTarget: (target: PendingTarget | null) => {
        set({ pendingTarget: target, pendingLabel: '', pendingColor: '#3B82F6' })
      },

      setPendingPreview: (label: string, color: string) => {
        set({ pendingLabel: label, pendingColor: color })
      },

      openDetailsSheet: () => {
        set({ isDetailsSheetOpen: true })
      },

      closeDetailsSheet: () => {
        set({ isDetailsSheetOpen: false })
      },

      clearPendingTarget: () => {
        set({
          pendingTarget: null,
          isDetailsSheetOpen: false,
          pendingLabel: '',
          pendingColor: '#3B82F6',
        })
      },
    }),
    { name: 'TargetAddStore', enabled: import.meta.env?.DEV ?? false },
  ),
)
