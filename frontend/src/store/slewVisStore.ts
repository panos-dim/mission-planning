import { create } from 'zustand'
import { AlgorithmResult } from '../types'

export type ColorByMode = 'quality' | 'density' | 'none'
export type FilterMode = 'accepted' | 'rejected_feasible' | 'all'

interface SlewVisStore {
  // Visibility
  enabled: boolean
  showFootprints: boolean
  showSlewArcs: boolean
  showSlewLabels: boolean
  showRejected: boolean
  
  // Data
  activeSchedule: AlgorithmResult | null
  
  // Styling
  colorBy: ColorByMode
  filterMode: FilterMode
  
  // Interaction
  hoveredOpportunityId: string | null
  selectedOpportunityId: string | null
  
  // Actions
  setEnabled: (enabled: boolean) => void
  setActiveSchedule: (schedule: AlgorithmResult | null) => void
  setShowFootprints: (show: boolean) => void
  setShowSlewArcs: (show: boolean) => void
  setShowSlewLabels: (show: boolean) => void
  setShowRejected: (show: boolean) => void
  setColorBy: (mode: ColorByMode) => void
  setFilterMode: (mode: FilterMode) => void
  setHoveredOpportunity: (id: string | null) => void
  setSelectedOpportunity: (id: string | null) => void
  reset: () => void
}

const initialState = {
  enabled: false,
  activeSchedule: null,
  showFootprints: true,
  showSlewArcs: true,
  showSlewLabels: true,
  showRejected: false,
  colorBy: 'quality' as ColorByMode,
  filterMode: 'accepted' as FilterMode,
  hoveredOpportunityId: null,
  selectedOpportunityId: null,
}

export const useSlewVisStore = create<SlewVisStore>((set) => ({
  ...initialState,
  
  setEnabled: (enabled) => set({ enabled }),
  setActiveSchedule: (schedule) => set({ activeSchedule: schedule }),
  setShowFootprints: (show) => set({ showFootprints: show }),
  setShowSlewArcs: (show) => set({ showSlewArcs: show }),
  setShowSlewLabels: (show) => set({ showSlewLabels: show }),
  setShowRejected: (show) => set({ showRejected: show }),
  setColorBy: (mode) => set({ colorBy: mode }),
  setFilterMode: (mode) => set({ filterMode: mode }),
  setHoveredOpportunity: (id) => set({ hoveredOpportunityId: id }),
  setSelectedOpportunity: (id) => set({ selectedOpportunityId: id }),
  reset: () => set(initialState),
}))
