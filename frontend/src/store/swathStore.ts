/**
 * Swath Store
 *
 * Manages SAR swath visualization state including:
 * - Selection state (selected swath/opportunity)
 * - Hover state
 * - Layer visibility modes (Off | Selected Plan | Filtered | All)
 * - LOD/virtualization settings
 * - Debug overlay state
 */

import { create } from "zustand";
import { devtools } from "zustand/middleware";

// Swath visibility modes for the Layers toggle group
export type SwathVisibilityMode = "off" | "selected_plan" | "filtered" | "all";

// Swath data extracted from CZML properties
export interface SwathProperties {
  opportunity_id: string;
  run_id: string;
  target_id: string;
  pass_index: number;
  look_side: "LEFT" | "RIGHT";
  pass_direction: "ASCENDING" | "DESCENDING";
  incidence_deg: number;
  swath_width_km: number;
  imaging_time: string;
  entity_type: string;
}

// Debug info structure
export interface SwathDebugInfo {
  currentRunId: string | null;
  renderedSwathCount: number;
  selectedOpportunityId: string | null;
  hoveredOpportunityId: string | null;
  pickingHitType: string | null;
  lastPickTime: number | null;
  visibilityMode: SwathVisibilityMode;
  lodLevel: "full" | "simplified" | "hidden";
  filterActive: boolean;
}

// LOD configuration
export interface SwathLODConfig {
  // Max swaths to render in "all" mode (prevents freeze)
  maxAllSwaths: number;
  // Camera altitude threshold for LOD switching (meters)
  lodThresholdAltitude: number;
  // Debounce time for filter updates (ms)
  filterDebounceMs: number;
  // Show warning when hitting swath cap
  showCapWarning: boolean;
}

interface SwathStore {
  // Selection state
  selectedSwathId: string | null;
  selectedOpportunityId: string | null;
  hoveredSwathId: string | null;
  hoveredOpportunityId: string | null;

  // Current run context
  activeRunId: string | null;

  // Visibility mode (single toggle group)
  visibilityMode: SwathVisibilityMode;

  // Target filter (when selecting a target, auto-filter to its swaths)
  filteredTargetId: string | null;
  autoFilterEnabled: boolean;

  // LOD configuration
  lodConfig: SwathLODConfig;

  // Debug overlay
  debugEnabled: boolean;
  debugInfo: SwathDebugInfo;

  // Rendered swath tracking (for performance)
  renderedSwathIds: Set<string>;
  visibleSwathCount: number;

  // Actions - Selection
  selectSwath: (swathId: string | null, opportunityId?: string | null) => void;
  setHoveredSwath: (
    swathId: string | null,
    opportunityId?: string | null,
  ) => void;
  clearSelection: () => void;

  // Actions - Run context
  setActiveRunId: (runId: string | null) => void;

  // Actions - Visibility
  setVisibilityMode: (mode: SwathVisibilityMode) => void;
  cycleVisibilityMode: () => void;

  // Actions - Filtering
  setFilteredTarget: (targetId: string | null) => void;
  setAutoFilterEnabled: (enabled: boolean) => void;
  clearFilters: () => void;

  // Actions - LOD
  setLODConfig: (config: Partial<SwathLODConfig>) => void;

  // Actions - Debug
  setDebugEnabled: (enabled: boolean) => void;
  updateDebugInfo: (info: Partial<SwathDebugInfo>) => void;

  // Actions - Rendered swaths tracking
  setRenderedSwaths: (swathIds: string[]) => void;
  updateVisibleCount: (count: number) => void;

  // Utility - Get swath properties from entity
  getSwathOpportunityId: (entityId: string) => string | null;
}

// Default LOD configuration
const DEFAULT_LOD_CONFIG: SwathLODConfig = {
  maxAllSwaths: 200, // Cap to prevent freeze
  lodThresholdAltitude: 5000000, // 5000km altitude
  filterDebounceMs: 150,
  showCapWarning: true,
};

// Initial debug info
const INITIAL_DEBUG_INFO: SwathDebugInfo = {
  currentRunId: null,
  renderedSwathCount: 0,
  selectedOpportunityId: null,
  hoveredOpportunityId: null,
  pickingHitType: null,
  lastPickTime: null,
  visibilityMode: "filtered",
  lodLevel: "full",
  filterActive: false,
};

// Visibility mode cycle order
const VISIBILITY_MODE_ORDER: SwathVisibilityMode[] = [
  "off",
  "selected_plan",
  "filtered",
  "all",
];

export const useSwathStore = create<SwathStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      selectedSwathId: null,
      selectedOpportunityId: null,
      hoveredSwathId: null,
      hoveredOpportunityId: null,
      activeRunId: null,
      visibilityMode: "filtered", // Default to filtered mode
      filteredTargetId: null,
      autoFilterEnabled: true, // Auto-filter when selecting target
      lodConfig: DEFAULT_LOD_CONFIG,
      debugEnabled: false,
      debugInfo: INITIAL_DEBUG_INFO,
      renderedSwathIds: new Set(),
      visibleSwathCount: 0,

      // Selection actions
      selectSwath: (swathId, opportunityId) => {
        set({
          selectedSwathId: swathId,
          selectedOpportunityId: opportunityId ?? null,
        });
        // Update debug info
        get().updateDebugInfo({
          selectedOpportunityId: opportunityId ?? null,
        });
      },

      setHoveredSwath: (swathId, opportunityId) => {
        set({
          hoveredSwathId: swathId,
          hoveredOpportunityId: opportunityId ?? null,
        });
        get().updateDebugInfo({
          hoveredOpportunityId: opportunityId ?? null,
        });
      },

      clearSelection: () => {
        set({
          selectedSwathId: null,
          selectedOpportunityId: null,
          hoveredSwathId: null,
          hoveredOpportunityId: null,
        });
        get().updateDebugInfo({
          selectedOpportunityId: null,
          hoveredOpportunityId: null,
        });
      },

      // Run context
      setActiveRunId: (runId) => {
        set({ activeRunId: runId });
        get().updateDebugInfo({ currentRunId: runId });
      },

      // Visibility mode
      setVisibilityMode: (mode) => {
        set({ visibilityMode: mode });
        get().updateDebugInfo({ visibilityMode: mode });
      },

      cycleVisibilityMode: () => {
        const { visibilityMode } = get();
        const currentIndex = VISIBILITY_MODE_ORDER.indexOf(visibilityMode);
        const nextIndex = (currentIndex + 1) % VISIBILITY_MODE_ORDER.length;
        const nextMode = VISIBILITY_MODE_ORDER[nextIndex];
        set({ visibilityMode: nextMode });
        get().updateDebugInfo({ visibilityMode: nextMode });
      },

      // Filtering
      setFilteredTarget: (targetId) => {
        set({ filteredTargetId: targetId });
        get().updateDebugInfo({ filterActive: targetId !== null });
      },

      setAutoFilterEnabled: (enabled) => {
        set({ autoFilterEnabled: enabled });
      },

      clearFilters: () => {
        set({ filteredTargetId: null });
        get().updateDebugInfo({ filterActive: false });
      },

      // LOD configuration
      setLODConfig: (config) => {
        set((state) => ({
          lodConfig: { ...state.lodConfig, ...config },
        }));
      },

      // Debug
      setDebugEnabled: (enabled) => {
        set({ debugEnabled: enabled });
      },

      updateDebugInfo: (info) => {
        set((state) => ({
          debugInfo: { ...state.debugInfo, ...info },
        }));
      },

      // Rendered swaths tracking
      setRenderedSwaths: (swathIds) => {
        set({
          renderedSwathIds: new Set(swathIds),
          visibleSwathCount: swathIds.length,
        });
        get().updateDebugInfo({ renderedSwathCount: swathIds.length });
      },

      updateVisibleCount: (count) => {
        set({ visibleSwathCount: count });
        get().updateDebugInfo({ renderedSwathCount: count });
      },

      // Utility to extract opportunity_id from entity ID
      getSwathOpportunityId: (entityId) => {
        // Entity ID format: sar_swath_{target}_{timestamp}_{index}
        if (!entityId.startsWith("sar_swath_")) return null;
        // Extract the opportunity_id portion (everything after "sar_swath_")
        return entityId.replace("sar_swath_", "");
      },
    }),
    { name: "SwathStore", enabled: import.meta.env?.DEV ?? false },
  ),
);

// Selector hooks for common patterns
export const useSwathSelection = () =>
  useSwathStore((state) => ({
    selectedSwathId: state.selectedSwathId,
    selectedOpportunityId: state.selectedOpportunityId,
    hoveredSwathId: state.hoveredSwathId,
    hoveredOpportunityId: state.hoveredOpportunityId,
    selectSwath: state.selectSwath,
    setHoveredSwath: state.setHoveredSwath,
    clearSelection: state.clearSelection,
  }));

export const useSwathVisibility = () =>
  useSwathStore((state) => ({
    visibilityMode: state.visibilityMode,
    setVisibilityMode: state.setVisibilityMode,
    cycleVisibilityMode: state.cycleVisibilityMode,
    filteredTargetId: state.filteredTargetId,
    setFilteredTarget: state.setFilteredTarget,
    autoFilterEnabled: state.autoFilterEnabled,
    setAutoFilterEnabled: state.setAutoFilterEnabled,
  }));

export const useSwathDebug = () =>
  useSwathStore((state) => ({
    debugEnabled: state.debugEnabled,
    debugInfo: state.debugInfo,
    setDebugEnabled: state.setDebugEnabled,
    updateDebugInfo: state.updateDebugInfo,
  }));

export const useSwathLOD = () =>
  useSwathStore((state) => ({
    lodConfig: state.lodConfig,
    setLODConfig: state.setLODConfig,
    visibleSwathCount: state.visibleSwathCount,
    renderedSwathIds: state.renderedSwathIds,
  }));
