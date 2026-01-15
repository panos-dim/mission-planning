/**
 * Store for managing preview targets that are displayed on the map
 * before mission analysis is run. This allows users to see targets
 * on the map as they add them to the UI.
 */

import { create } from 'zustand'
import { TargetData } from '../types'

interface PreviewTargetsState {
  // Targets to display on map before mission analysis
  targets: TargetData[]
  
  // Set all preview targets
  setTargets: (targets: TargetData[]) => void
  
  // Clear all preview targets (called when mission analysis runs)
  clearTargets: () => void
  
  // Flag to indicate if preview targets should be hidden (after CZML loads)
  hidePreview: boolean
  setHidePreview: (hide: boolean) => void
}

export const usePreviewTargetsStore = create<PreviewTargetsState>((set) => ({
  targets: [],
  hidePreview: false,
  
  setTargets: (targets) => set({ targets }),
  
  clearTargets: () => set({ targets: [] }),
  
  setHidePreview: (hide) => set({ hidePreview: hide }),
}))
