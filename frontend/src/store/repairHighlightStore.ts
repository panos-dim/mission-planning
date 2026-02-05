/**
 * Repair Highlight Store
 *
 * Manages highlighting of repair-related entities on the Cesium map:
 * - Repair diff item selection (kept, dropped, added, moved)
 * - Acquisition → Entity ID mapping for highlighting
 * - Timeline focus state for repair items
 * - Ghost/solid visualization for moved items
 *
 * Part of PR-REPAIR-UX-01
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type {
  RepairDiff,
  MovedAcquisitionInfo,
  MetricsComparison,
} from "../api/scheduleApi";

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Types
// =============================================================================

export type RepairDiffType = "kept" | "dropped" | "added" | "moved";

export interface RepairDiffSelection {
  id: string;
  type: RepairDiffType;
  /** For moved items, contains the timing info */
  movedInfo?: MovedAcquisitionInfo;
}

export interface RepairTimeRange {
  start: string; // ISO timestamp
  end: string; // ISO timestamp
  padding: number; // Minutes to add as padding
}

export interface RepairHighlightState {
  // Current repair diff data (from API response)
  repairDiff: RepairDiff | null;
  metricsComparison: MetricsComparison | null;

  // Currently selected repair diff item
  selectedDiffItem: RepairDiffSelection | null;

  // Highlighted entity IDs for repair display
  highlightedEntityIds: string[];

  // For moved items: ghost entity IDs (previous position)
  ghostEntityIds: string[];

  // Time range for timeline focus
  repairTimeRange: RepairTimeRange | null;

  // Whether timeline focus should be applied
  shouldFocusTimeline: boolean;

  // Camera focus target
  cameraFocusTarget: {
    latitude: number;
    longitude: number;
    itemId: string;
  } | null;

  // Loading/processing state
  isProcessing: boolean;

  // Whether repair preview is active (prevents accidental commits)
  isPreviewMode: boolean;
}

interface RepairHighlightActions {
  // Set repair diff data (from API response)
  setRepairDiff: (
    diff: RepairDiff | null,
    metrics: MetricsComparison | null,
  ) => void;

  // Select a repair diff item
  selectDiffItem: (
    id: string,
    type: RepairDiffType,
    itemData?: {
      start_time?: string;
      end_time?: string;
      latitude?: number;
      longitude?: number;
      movedInfo?: MovedAcquisitionInfo;
    },
  ) => void;

  // Clear selection
  clearSelection: () => void;

  // Clear all repair state
  clearRepairState: () => void;

  // Timeline focus
  setRepairTimeRange: (range: RepairTimeRange | null) => void;
  focusTimelineOnRepairItem: () => void;
  clearTimelineFocus: () => void;

  // Camera focus
  setCameraFocusTarget: (
    target: { latitude: number; longitude: number; itemId: string } | null,
  ) => void;

  // Preview mode
  setPreviewMode: (isPreview: boolean) => void;

  // Get all items of a specific type
  getItemsByType: (type: RepairDiffType) => string[];

  // Get moved item info by ID
  getMovedItemInfo: (id: string) => MovedAcquisitionInfo | undefined;
}

// =============================================================================
// Initial State
// =============================================================================

const initialState: RepairHighlightState = {
  repairDiff: null,
  metricsComparison: null,
  selectedDiffItem: null,
  highlightedEntityIds: [],
  ghostEntityIds: [],
  repairTimeRange: null,
  shouldFocusTimeline: false,
  cameraFocusTarget: null,
  isProcessing: false,
  isPreviewMode: false,
};

// =============================================================================
// Store
// =============================================================================

export const useRepairHighlightStore = create<
  RepairHighlightState & RepairHighlightActions
>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    setRepairDiff: (diff, metrics) => {
      if (isDev) {
        console.log(
          "[RepairHighlight] Setting repair diff:",
          diff
            ? `${diff.kept.length} kept, ${diff.dropped.length} dropped, ${diff.added.length} added, ${diff.moved.length} moved`
            : "null",
        );
      }

      set({
        repairDiff: diff,
        metricsComparison: metrics,
        isPreviewMode: diff !== null,
        selectedDiffItem: null,
        highlightedEntityIds: [],
        ghostEntityIds: [],
        repairTimeRange: null,
        shouldFocusTimeline: false,
      });
    },

    selectDiffItem: (id, type, itemData) => {
      if (isDev) {
        console.log(`[RepairHighlight] Selecting diff item: ${id} (${type})`);
      }

      set({ isProcessing: true });

      const { repairDiff } = get();

      // Build entity ID patterns for highlighting
      const entityIds: string[] = [];
      const ghostIds: string[] = [];

      // Add common entity ID patterns
      entityIds.push(id);
      entityIds.push(`sar_swath_${id}`);
      entityIds.push(`swath_${id}`);
      entityIds.push(`opp_${id}`);
      entityIds.push(`target_${id}`);
      entityIds.push(`acq_${id}`);

      // For moved items, also add ghost entities for the previous position
      let movedInfo: MovedAcquisitionInfo | undefined;
      if (type === "moved" && repairDiff) {
        movedInfo = repairDiff.moved.find((m) => m.id === id);
        if (movedInfo) {
          // Ghost entities show the "from" position
          ghostIds.push(`ghost_${id}`);
          ghostIds.push(`ghost_swath_${id}`);
        }
      }

      // Compute time range for timeline focus
      let timeRange: RepairTimeRange | null = null;
      let focusTarget: {
        latitude: number;
        longitude: number;
        itemId: string;
      } | null = null;

      if (itemData) {
        if (itemData.start_time && itemData.end_time) {
          timeRange = {
            start: itemData.start_time,
            end: itemData.end_time,
            padding: 3, // 3 minutes padding
          };
        }

        // For moved items, extend the time range to cover both positions
        if (movedInfo) {
          const fromStart = new Date(movedInfo.from_start).getTime();
          const fromEnd = new Date(movedInfo.from_end).getTime();
          const toStart = new Date(movedInfo.to_start).getTime();
          const toEnd = new Date(movedInfo.to_end).getTime();

          timeRange = {
            start: new Date(Math.min(fromStart, toStart)).toISOString(),
            end: new Date(Math.max(fromEnd, toEnd)).toISOString(),
            padding: 5, // More padding for moved items
          };
        }

        if (
          itemData.latitude !== undefined &&
          itemData.longitude !== undefined
        ) {
          focusTarget = {
            latitude: itemData.latitude,
            longitude: itemData.longitude,
            itemId: id,
          };
        }
      }

      const uniqueEntityIds = [...new Set(entityIds)];
      const uniqueGhostIds = [...new Set(ghostIds)];

      set({
        selectedDiffItem: { id, type, movedInfo },
        highlightedEntityIds: uniqueEntityIds,
        ghostEntityIds: uniqueGhostIds,
        repairTimeRange: timeRange,
        shouldFocusTimeline: timeRange !== null,
        cameraFocusTarget: focusTarget,
        isProcessing: false,
      });

      if (isDev) {
        console.log(
          `[RepairHighlight] Highlighted ${uniqueEntityIds.length} entities, ${uniqueGhostIds.length} ghost entities`,
        );
      }
    },

    clearSelection: () => {
      if (isDev) {
        console.log("[RepairHighlight] Clearing selection");
      }

      set({
        selectedDiffItem: null,
        highlightedEntityIds: [],
        ghostEntityIds: [],
        repairTimeRange: null,
        shouldFocusTimeline: false,
        cameraFocusTarget: null,
      });
    },

    clearRepairState: () => {
      if (isDev) {
        console.log("[RepairHighlight] Clearing all repair state");
      }

      set(initialState);
    },

    setRepairTimeRange: (range) => {
      set({ repairTimeRange: range, shouldFocusTimeline: range !== null });
    },

    focusTimelineOnRepairItem: () => {
      set({ shouldFocusTimeline: true });
    },

    clearTimelineFocus: () => {
      set({ shouldFocusTimeline: false });
    },

    setCameraFocusTarget: (target) => {
      set({ cameraFocusTarget: target });
    },

    setPreviewMode: (isPreview) => {
      set({ isPreviewMode: isPreview });
    },

    getItemsByType: (type) => {
      const { repairDiff } = get();
      if (!repairDiff) return [];

      switch (type) {
        case "kept":
          return repairDiff.kept;
        case "dropped":
          return repairDiff.dropped;
        case "added":
          return repairDiff.added;
        case "moved":
          return repairDiff.moved.map((m) => m.id);
        default:
          return [];
      }
    },

    getMovedItemInfo: (id) => {
      const { repairDiff } = get();
      if (!repairDiff) return undefined;
      return repairDiff.moved.find((m) => m.id === id);
    },
  })),
);

// =============================================================================
// Selector Hooks
// =============================================================================

export const useRepairDiffSelection = () =>
  useRepairHighlightStore((state) => state.selectedDiffItem);

export const useRepairHighlightedEntities = () =>
  useRepairHighlightStore((state) => state.highlightedEntityIds);

export const useRepairGhostEntities = () =>
  useRepairHighlightStore((state) => state.ghostEntityIds);

export const useRepairTimeRangeValue = () =>
  useRepairHighlightStore((state) => state.repairTimeRange);

export const useRepairShouldFocusTimeline = () =>
  useRepairHighlightStore((state) => state.shouldFocusTimeline);

export const useRepairCameraTarget = () =>
  useRepairHighlightStore((state) => state.cameraFocusTarget);

export const useRepairMetrics = () =>
  useRepairHighlightStore((state) => ({
    diff: state.repairDiff,
    metrics: state.metricsComparison,
    isPreviewMode: state.isPreviewMode,
  }));

export const useRepairHighlightActions = () =>
  useRepairHighlightStore((state) => ({
    setRepairDiff: state.setRepairDiff,
    selectDiffItem: state.selectDiffItem,
    clearSelection: state.clearSelection,
    clearRepairState: state.clearRepairState,
    focusTimelineOnRepairItem: state.focusTimelineOnRepairItem,
    clearTimelineFocus: state.clearTimelineFocus,
    setCameraFocusTarget: state.setCameraFocusTarget,
    setPreviewMode: state.setPreviewMode,
    getItemsByType: state.getItemsByType,
    getMovedItemInfo: state.getMovedItemInfo,
  }));

// =============================================================================
// Utility: Check if an item is in the repair diff
// =============================================================================

export const getRepairDiffType = (
  diff: RepairDiff | null,
  itemId: string,
): RepairDiffType | null => {
  if (!diff) return null;

  if (diff.kept.includes(itemId)) return "kept";
  if (diff.dropped.includes(itemId)) return "dropped";
  if (diff.added.includes(itemId)) return "added";
  if (diff.moved.some((m) => m.id === itemId)) return "moved";

  return null;
};

export const getRepairDiffBadgeInfo = (
  type: RepairDiffType,
): { label: string; color: string; bgColor: string } => {
  switch (type) {
    case "kept":
      return {
        label: "Kept",
        color: "text-green-400",
        bgColor: "bg-green-900/30",
      };
    case "dropped":
      return {
        label: "Dropped",
        color: "text-red-400",
        bgColor: "bg-red-900/30",
      };
    case "added":
      return {
        label: "Added",
        color: "text-blue-400",
        bgColor: "bg-blue-900/30",
      };
    case "moved":
      return {
        label: "Moved",
        color: "text-yellow-400",
        bgColor: "bg-yellow-900/30",
      };
  }
};
