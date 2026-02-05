/**
 * Unified Highlight Store
 *
 * Single source of truth for all highlight state across the mission planner:
 * - Conflict highlighting
 * - Repair diff highlighting
 * - Normal selection highlighting
 *
 * Implements timeline focus reliability guard (stores pending focus until timeline visible)
 *
 * Part of PR-MAP-HIGHLIGHT-01
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";
import type { RepairDiffType } from "./repairHighlightStore";
import type { HighlightMode } from "../adapters/highlightAdapter";

const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Types
// =============================================================================

export interface TimeRange {
  start: string; // ISO timestamp
  end: string; // ISO timestamp
  padding: number; // Minutes to add as padding
}

export interface CameraFocusTarget {
  latitude: number;
  longitude: number;
  itemId: string;
}

export interface PendingTimelineFocus {
  range: TimeRange;
  jumpToStart: boolean;
  requestedAt: number;
}

export interface UnifiedHighlightState {
  // Current highlight mode
  activeMode: HighlightMode | null;

  // IDs being highlighted (logical IDs, not entity IDs)
  highlightedIds: string[];

  // Ghost IDs for moved items
  ghostIds: string[];

  // Repair-specific: diff type for coloring
  repairDiffType: RepairDiffType | null;

  // Timeline focus state
  timeRange: TimeRange | null;
  shouldFocusTimeline: boolean;

  // Pending timeline focus (for when timeline is hidden)
  pendingTimelineFocus: PendingTimelineFocus | null;

  // Whether timeline is currently visible
  timelineVisible: boolean;

  // Camera focus target
  cameraFocusTarget: CameraFocusTarget | null;

  // Processing state
  isProcessing: boolean;
}

interface UnifiedHighlightActions {
  // Set highlight for conflict mode
  highlightConflict: (
    acquisitionIds: string[],
    timeRange?: TimeRange,
    cameraTarget?: CameraFocusTarget,
  ) => void;

  // Set highlight for repair mode
  highlightRepair: (
    itemIds: string[],
    diffType: RepairDiffType,
    ghostIds?: string[],
    timeRange?: TimeRange,
    cameraTarget?: CameraFocusTarget,
  ) => void;

  // Set highlight for normal selection
  highlightSelection: (
    itemIds: string[],
    timeRange?: TimeRange,
    cameraTarget?: CameraFocusTarget,
  ) => void;

  // Clear all highlights
  clearHighlights: () => void;

  // Timeline visibility management
  setTimelineVisible: (visible: boolean) => void;

  // Consume pending timeline focus (call this when timeline becomes visible)
  consumePendingTimelineFocus: () => PendingTimelineFocus | null;

  // Re-request timeline focus
  requestTimelineFocus: () => void;

  // Clear timeline focus flag (after it's been applied)
  clearTimelineFocus: () => void;

  // Camera focus
  setCameraFocusTarget: (target: CameraFocusTarget | null) => void;
}

// =============================================================================
// Initial State
// =============================================================================

const initialState: UnifiedHighlightState = {
  activeMode: null,
  highlightedIds: [],
  ghostIds: [],
  repairDiffType: null,
  timeRange: null,
  shouldFocusTimeline: false,
  pendingTimelineFocus: null,
  timelineVisible: true, // Assume visible by default
  cameraFocusTarget: null,
  isProcessing: false,
};

// =============================================================================
// Store
// =============================================================================

export const useUnifiedHighlightStore = create<
  UnifiedHighlightState & UnifiedHighlightActions
>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    highlightConflict: (acquisitionIds, timeRange, cameraTarget) => {
      if (isDev) {
        console.log(
          `[UnifiedHighlight] Highlighting conflict: ${acquisitionIds.length} acquisitions`,
        );
      }

      const { timelineVisible } = get();
      let pendingFocus: PendingTimelineFocus | null = null;

      // If timeline is hidden, store pending focus
      if (timeRange && !timelineVisible) {
        pendingFocus = {
          range: timeRange,
          jumpToStart: true,
          requestedAt: Date.now(),
        };
        if (isDev) {
          console.log(
            `[UnifiedHighlight] Timeline hidden, storing pending focus`,
          );
        }
      }

      set({
        activeMode: "conflict",
        highlightedIds: acquisitionIds,
        ghostIds: [],
        repairDiffType: null,
        timeRange: timeRange || null,
        shouldFocusTimeline: timeRange !== undefined && timelineVisible,
        pendingTimelineFocus: pendingFocus,
        cameraFocusTarget: cameraTarget || null,
        isProcessing: false,
      });
    },

    highlightRepair: (itemIds, diffType, ghostIds, timeRange, cameraTarget) => {
      if (isDev) {
        console.log(
          `[UnifiedHighlight] Highlighting repair (${diffType}): ${itemIds.length} items, ${ghostIds?.length || 0} ghosts`,
        );
      }

      const { timelineVisible } = get();
      let pendingFocus: PendingTimelineFocus | null = null;

      if (timeRange && !timelineVisible) {
        pendingFocus = {
          range: timeRange,
          jumpToStart: true,
          requestedAt: Date.now(),
        };
      }

      set({
        activeMode: "repair",
        highlightedIds: itemIds,
        ghostIds: ghostIds || [],
        repairDiffType: diffType,
        timeRange: timeRange || null,
        shouldFocusTimeline: timeRange !== undefined && timelineVisible,
        pendingTimelineFocus: pendingFocus,
        cameraFocusTarget: cameraTarget || null,
        isProcessing: false,
      });
    },

    highlightSelection: (itemIds, timeRange, cameraTarget) => {
      if (isDev) {
        console.log(
          `[UnifiedHighlight] Highlighting selection: ${itemIds.length} items`,
        );
      }

      const { timelineVisible } = get();
      let pendingFocus: PendingTimelineFocus | null = null;

      if (timeRange && !timelineVisible) {
        pendingFocus = {
          range: timeRange,
          jumpToStart: true,
          requestedAt: Date.now(),
        };
      }

      set({
        activeMode: "selection",
        highlightedIds: itemIds,
        ghostIds: [],
        repairDiffType: null,
        timeRange: timeRange || null,
        shouldFocusTimeline: timeRange !== undefined && timelineVisible,
        pendingTimelineFocus: pendingFocus,
        cameraFocusTarget: cameraTarget || null,
        isProcessing: false,
      });
    },

    clearHighlights: () => {
      if (isDev) {
        console.log(`[UnifiedHighlight] Clearing all highlights`);
      }

      set({
        activeMode: null,
        highlightedIds: [],
        ghostIds: [],
        repairDiffType: null,
        timeRange: null,
        shouldFocusTimeline: false,
        pendingTimelineFocus: null,
        cameraFocusTarget: null,
        isProcessing: false,
      });
    },

    setTimelineVisible: (visible) => {
      const prev = get().timelineVisible;
      if (prev === visible) return;

      if (isDev) {
        console.log(`[UnifiedHighlight] Timeline visibility: ${visible}`);
      }

      set({ timelineVisible: visible });

      // If timeline just became visible and we have pending focus, trigger it
      if (visible) {
        const { pendingTimelineFocus, timeRange } = get();
        if (pendingTimelineFocus) {
          if (isDev) {
            console.log(
              `[UnifiedHighlight] Applying pending timeline focus from ${pendingTimelineFocus.requestedAt}`,
            );
          }
          set({
            shouldFocusTimeline: true,
            timeRange: pendingTimelineFocus.range,
            pendingTimelineFocus: null,
          });
        } else if (timeRange) {
          // Re-apply existing time range focus
          set({ shouldFocusTimeline: true });
        }
      }
    },

    consumePendingTimelineFocus: () => {
      const { pendingTimelineFocus } = get();
      if (pendingTimelineFocus) {
        set({ pendingTimelineFocus: null });
        return pendingTimelineFocus;
      }
      return null;
    },

    requestTimelineFocus: () => {
      const { timeRange, timelineVisible } = get();
      if (!timeRange) return;

      if (timelineVisible) {
        set({ shouldFocusTimeline: true });
      } else {
        set({
          pendingTimelineFocus: {
            range: timeRange,
            jumpToStart: true,
            requestedAt: Date.now(),
          },
        });
      }
    },

    clearTimelineFocus: () => {
      set({ shouldFocusTimeline: false });
    },

    setCameraFocusTarget: (target) => {
      set({ cameraFocusTarget: target });
    },
  })),
);

// =============================================================================
// Selector Hooks
// =============================================================================

export const useActiveHighlightMode = () =>
  useUnifiedHighlightStore((s) => s.activeMode);

export const useHighlightedIds = () =>
  useUnifiedHighlightStore((s) => s.highlightedIds);

export const useGhostIds = () => useUnifiedHighlightStore((s) => s.ghostIds);

export const useRepairDiffType = () =>
  useUnifiedHighlightStore((s) => s.repairDiffType);

export const useHighlightTimeRange = () =>
  useUnifiedHighlightStore((s) => s.timeRange);

export const useShouldFocusTimeline = () =>
  useUnifiedHighlightStore((s) => s.shouldFocusTimeline);

export const useHighlightCameraTarget = () =>
  useUnifiedHighlightStore((s) => s.cameraFocusTarget);

export const useUnifiedHighlightActions = () =>
  useUnifiedHighlightStore((s) => ({
    highlightConflict: s.highlightConflict,
    highlightRepair: s.highlightRepair,
    highlightSelection: s.highlightSelection,
    clearHighlights: s.clearHighlights,
    setTimelineVisible: s.setTimelineVisible,
    requestTimelineFocus: s.requestTimelineFocus,
    clearTimelineFocus: s.clearTimelineFocus,
    setCameraFocusTarget: s.setCameraFocusTarget,
  }));
