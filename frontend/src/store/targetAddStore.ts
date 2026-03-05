/**
 * Zustand store for managing target add mode state.
 *
 * PR-UI-036: Inline-add flow — clicking the map adds the target immediately
 * (auto-generated name, default priority) and opens the right-pane editor so
 * the operator can refine name + priority without a confirm modal.
 */

import { create } from 'zustand'
import { devtools } from 'zustand/middleware'

/** Reference to the target that was just added to an order, for editing. */
export interface LastAddedTarget {
  orderId: string
  targetIndex: number
  latitude: number
  longitude: number
}

interface TargetAddState {
  // Target add mode
  isAddMode: boolean

  /** The target that was just added via map click — open editor for it. */
  lastAddedTarget: LastAddedTarget | null

  // Actions
  enableAddMode: () => void
  disableAddMode: () => void
  toggleAddMode: () => void
  /** Record a just-added target so the editor can open. */
  setLastAddedTarget: (ref: LastAddedTarget) => void
  /** Close the editor (user finished editing or dismissed). */
  clearLastAddedTarget: () => void
}

export const useTargetAddStore = create<TargetAddState>()(
  devtools(
    (set, get) => ({
      // Initial state
      isAddMode: false,
      lastAddedTarget: null,

      // Actions
      enableAddMode: () => {
        set({ isAddMode: true })
      },

      disableAddMode: () => {
        set({
          isAddMode: false,
          lastAddedTarget: null,
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

      setLastAddedTarget: (ref: LastAddedTarget) => {
        set({ lastAddedTarget: ref })
      },

      clearLastAddedTarget: () => {
        set({ lastAddedTarget: null })
      },
    }),
    { name: 'TargetAddStore', enabled: import.meta.env?.DEV ?? false },
  ),
)
