import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { JulianDate } from 'cesium'

export type SceneMode = '2D' | '3D'
export type ViewMode = 'single' | 'split'
export type UIMode = 'simple' | 'developer'

interface LayerVisibility {
  // Entity layers
  orbitLine: boolean
  groundTrack: boolean
  targets: boolean
  footprints: boolean
  labels: boolean
  coverageAreas: boolean
  pointingCone: boolean
  dayNightLighting: boolean
  sarSwaths: boolean
  // Globe settings
  terrain: boolean
  atmosphere: boolean
  gridLines: boolean
  fog: boolean
  // Post-processing
  bloom: boolean
  fxaa: boolean
}

export type BaseMapType = 'cesium_ion' | 'osm' | 'dark'

interface VisStore {
  // View configuration
  sceneModePrimary: SceneMode
  sceneModeSecondary: SceneMode
  viewMode: ViewMode

  // UI Mode (simple = mission planner, developer = all panels)
  uiMode: UIMode

  // Sidebar state
  leftSidebarOpen: boolean
  rightSidebarOpen: boolean
  leftSidebarWidth: number
  rightSidebarWidth: number
  activeLeftPanel: string | null

  // Synchronization state
  clockTime: JulianDate | null
  clockShouldAnimate: boolean
  clockMultiplier: number
  timeWindow: {
    start: JulianDate | null
    stop: JulianDate | null
  }
  selectedOpportunityId: string | null
  activeLayers: LayerVisibility

  // Camera synchronization
  cameraPosition: any | null // Will hold camera state for sync

  // Actions
  setLeftSidebarOpen: (open: boolean) => void
  setRightSidebarOpen: (open: boolean) => void
  setLeftSidebarWidth: (width: number) => void
  setRightSidebarWidth: (width: number) => void
  setActiveLeftPanel: (panel: string | null) => void
  setSceneModePrimary: (mode: SceneMode) => void
  setSceneModeSecondary: (mode: SceneMode) => void
  setViewMode: (mode: ViewMode) => void
  setUIMode: (mode: UIMode) => void
  toggleUIMode: () => void
  setClockTime: (time: JulianDate | null) => void
  setClockState: (time: JulianDate | null, shouldAnimate: boolean, multiplier: number) => void
  setTimeWindow: (start: JulianDate | null, stop: JulianDate | null) => void
  setSelectedOpportunity: (id: string | null) => void
  toggleLayer: (layer: keyof LayerVisibility) => void
  setLayerVisibility: (layer: keyof LayerVisibility, visible: boolean) => void
  setCameraPosition: (position: any) => void

  // Imperative panel open signal — consumed once by RightSidebar
  requestedRightPanel: string | null
  openRightPanel: (panelId: string) => void
  clearRequestedRightPanel: () => void

  // Bulk updates for initialization
  initializeLayers: (layers: Partial<LayerVisibility>) => void
}

export const useVisStore = create<VisStore>()(
  devtools(
    (set) => ({
      // Initial state - 2D by default
      sceneModePrimary: '2D',
      sceneModeSecondary: '3D',
      viewMode: 'single',

      // UI Mode - simple (mission planner) by default
      uiMode: 'simple',

      // Sidebar state
      leftSidebarOpen: true,
      rightSidebarOpen: false,
      leftSidebarWidth: 432,
      rightSidebarWidth: 432,
      activeLeftPanel: 'mission',

      clockTime: null,
      clockShouldAnimate: false,
      clockMultiplier: 1,
      timeWindow: {
        start: null,
        stop: null,
      },
      selectedOpportunityId: null,
      activeLayers: {
        // Entity layers
        orbitLine: true,
        groundTrack: true,
        targets: true,
        footprints: true,
        labels: true,
        coverageAreas: false,
        pointingCone: true,
        dayNightLighting: true,
        sarSwaths: true,
        // Globe settings
        terrain: false, // Off by default for performance
        atmosphere: true,
        gridLines: false,
        fog: false,
        // Post-processing
        bloom: false,
        fxaa: true, // Anti-aliasing on by default
      },
      cameraPosition: null,

      requestedRightPanel: null,

      // Actions
      setLeftSidebarOpen: (open) => set({ leftSidebarOpen: open }),
      setRightSidebarOpen: (open) => set({ rightSidebarOpen: open }),
      setActiveLeftPanel: (panel) => set({ activeLeftPanel: panel }),
      setLeftSidebarWidth: (width) =>
        set({ leftSidebarWidth: Math.min(Math.max(width, 432), 864) }),
      setRightSidebarWidth: (width) =>
        set({ rightSidebarWidth: Math.min(Math.max(width, 432), 864) }),

      setSceneModePrimary: (mode) => set({ sceneModePrimary: mode }),

      setSceneModeSecondary: (mode) => set({ sceneModeSecondary: mode }),

      setViewMode: (mode) => set({ viewMode: mode }),
      setUIMode: (mode) => set({ uiMode: mode }),
      toggleUIMode: () =>
        set((state) => ({
          uiMode: state.uiMode === 'simple' ? 'developer' : 'simple',
        })),
      setClockTime: (time) => set({ clockTime: time }),
      setClockState: (time, shouldAnimate, multiplier) =>
        set({
          clockTime: time,
          clockShouldAnimate: shouldAnimate,
          clockMultiplier: multiplier,
        }),
      setTimeWindow: (start, stop) =>
        set({
          timeWindow: { start, stop },
        }),
      setSelectedOpportunity: (id) => set({ selectedOpportunityId: id }),

      toggleLayer: (layer) =>
        set((state) => ({
          activeLayers: {
            ...state.activeLayers,
            [layer]: !state.activeLayers[layer],
          },
        })),

      setLayerVisibility: (layer, visible) =>
        set((state) => ({
          activeLayers: {
            ...state.activeLayers,
            [layer]: visible,
          },
        })),

      setCameraPosition: (position) => set({ cameraPosition: position }),

      openRightPanel: (panelId) => set({ requestedRightPanel: panelId }),
      clearRequestedRightPanel: () => set({ requestedRightPanel: null }),

      initializeLayers: (layers) =>
        set((state) => ({
          activeLayers: {
            ...state.activeLayers,
            ...layers,
          },
        })),
    }),
    { name: 'VisStore', enabled: import.meta.env?.DEV ?? false },
  ),
)
