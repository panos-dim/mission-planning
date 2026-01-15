import { create } from "zustand";
import { JulianDate } from "cesium";

export type SceneMode = "2D" | "3D";
export type ViewMode = "single" | "split";

interface LayerVisibility {
  orbitLine: boolean;
  groundTrack: boolean;
  targets: boolean;
  footprints: boolean;
  labels: boolean;
  coverageAreas: boolean;
  pointingCone: boolean;
  dayNightLighting: boolean;
  sarSwaths: boolean;
}

interface VisStore {
  // View configuration
  sceneModePrimary: SceneMode;
  sceneModeSecondary: SceneMode;
  viewMode: ViewMode;

  // Sidebar state
  leftSidebarOpen: boolean;
  rightSidebarOpen: boolean;
  leftSidebarWidth: number;
  rightSidebarWidth: number;

  // Synchronization state
  clockTime: JulianDate | null;
  clockShouldAnimate: boolean;
  clockMultiplier: number;
  timeWindow: {
    start: JulianDate | null;
    stop: JulianDate | null;
  };
  selectedOpportunityId: string | null;
  activeLayers: LayerVisibility;

  // Camera synchronization
  cameraPosition: any | null; // Will hold camera state for sync

  // Actions
  setLeftSidebarOpen: (open: boolean) => void;
  setRightSidebarOpen: (open: boolean) => void;
  setLeftSidebarWidth: (width: number) => void;
  setRightSidebarWidth: (width: number) => void;
  setSceneModePrimary: (mode: SceneMode) => void;
  setSceneModeSecondary: (mode: SceneMode) => void;
  setViewMode: (mode: ViewMode) => void;
  setClockTime: (time: JulianDate | null) => void;
  setClockState: (
    time: JulianDate | null,
    shouldAnimate: boolean,
    multiplier: number
  ) => void;
  setTimeWindow: (start: JulianDate | null, stop: JulianDate | null) => void;
  setSelectedOpportunity: (id: string | null) => void;
  toggleLayer: (layer: keyof LayerVisibility) => void;
  setLayerVisibility: (layer: keyof LayerVisibility, visible: boolean) => void;
  setCameraPosition: (position: any) => void;

  // Bulk updates for initialization
  initializeLayers: (layers: Partial<LayerVisibility>) => void;
}

export const useVisStore = create<VisStore>((set) => ({
  // Initial state - 2D by default
  sceneModePrimary: "2D",
  sceneModeSecondary: "3D",
  viewMode: "single",

  // Sidebar state
  leftSidebarOpen: true,
  rightSidebarOpen: false,
  leftSidebarWidth: 432,
  rightSidebarWidth: 432,

  clockTime: null,
  clockShouldAnimate: false,
  clockMultiplier: 1,
  timeWindow: {
    start: null,
    stop: null,
  },
  selectedOpportunityId: null,
  activeLayers: {
    orbitLine: true, // Default ON (satellite path with dynamic trail)
    groundTrack: true, // Kept for compatibility
    targets: true,
    footprints: true,
    labels: true,
    coverageAreas: false,
    pointingCone: true,
    dayNightLighting: true,
    sarSwaths: true, // Default ON for SAR missions
  },
  cameraPosition: null,

  // Actions
  setLeftSidebarOpen: (open) => set({ leftSidebarOpen: open }),
  setRightSidebarOpen: (open) => set({ rightSidebarOpen: open }),
  setLeftSidebarWidth: (width) =>
    set({ leftSidebarWidth: Math.min(Math.max(width, 432), 864) }),
  setRightSidebarWidth: (width) =>
    set({ rightSidebarWidth: Math.min(Math.max(width, 432), 864) }),

  setSceneModePrimary: (mode) => set({ sceneModePrimary: mode }),

  setSceneModeSecondary: (mode) => set({ sceneModeSecondary: mode }),

  setViewMode: (mode) => set({ viewMode: mode }),
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

  initializeLayers: (layers) =>
    set((state) => ({
      activeLayers: {
        ...state.activeLayers,
        ...layers,
      },
    })),
}));
