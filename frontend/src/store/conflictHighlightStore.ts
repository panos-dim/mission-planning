/**
 * Conflict Highlight Store
 *
 * Manages highlighting of conflict-related entities on the Cesium map:
 * - Acquisition → Entity ID mapping (cached for O(k) lookup)
 * - Highlight state for conflict acquisitions
 * - Timeline focus state for conflict time windows
 *
 * Part of PR-CONFLICT-UX-02
 */

import { create } from "zustand";
import { subscribeWithSelector } from "zustand/middleware";

// Dev mode check
const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Types
// =============================================================================

export interface ConflictTimeRange {
  start: string; // ISO timestamp
  end: string; // ISO timestamp
  padding: number; // Minutes to add as padding
}

export interface HighlightedEntityInfo {
  entityId: string;
  acquisitionId: string;
  type: "swath" | "target" | "footprint";
}

interface ConflictHighlightState {
  // Acquisition ID → Entity IDs mapping (cached)
  acquisitionEntityMap: Map<string, string[]>;

  // Currently highlighted entity IDs for conflict display
  highlightedEntityIds: string[];

  // Conflict time range for timeline focus
  conflictTimeRange: ConflictTimeRange | null;

  // Whether timeline focus should be applied
  shouldFocusTimeline: boolean;

  // Camera focus target (first acquisition's position)
  cameraFocusTarget: {
    latitude: number;
    longitude: number;
    acquisitionId: string;
  } | null;

  // Loading/processing state
  isProcessing: boolean;
}

interface ConflictHighlightActions {
  // Map building
  registerAcquisitionEntity: (
    acquisitionId: string,
    entityId: string,
    type?: "swath" | "target" | "footprint",
  ) => void;
  unregisterAcquisitionEntity: (
    acquisitionId: string,
    entityId: string,
  ) => void;
  clearEntityMap: () => void;

  // Highlight management
  setHighlightedAcquisitions: (
    acquisitionIds: string[],
    acquisitionData?: Array<{
      id: string;
      start_time: string;
      end_time: string;
      latitude?: number;
      longitude?: number;
    }>,
  ) => void;
  clearHighlights: () => void;

  // Timeline focus
  setConflictTimeRange: (range: ConflictTimeRange | null) => void;
  focusTimelineOnConflict: () => void;
  clearTimelineFocus: () => void;

  // Camera focus
  setCameraFocusTarget: (
    target: {
      latitude: number;
      longitude: number;
      acquisitionId: string;
    } | null,
  ) => void;

  // Resolve entity IDs for given acquisition IDs
  resolveEntityIds: (acquisitionIds: string[]) => string[];
}

// =============================================================================
// Initial State
// =============================================================================

const initialState: ConflictHighlightState = {
  acquisitionEntityMap: new Map(),
  highlightedEntityIds: [],
  conflictTimeRange: null,
  shouldFocusTimeline: false,
  cameraFocusTarget: null,
  isProcessing: false,
};

// =============================================================================
// Store
// =============================================================================

export const useConflictHighlightStore = create<
  ConflictHighlightState & ConflictHighlightActions
>()(
  subscribeWithSelector((set, get) => ({
    ...initialState,

    registerAcquisitionEntity: (acquisitionId, entityId, _type) => {
      set((state) => {
        const newMap = new Map(state.acquisitionEntityMap);
        const existing = newMap.get(acquisitionId) || [];
        if (!existing.includes(entityId)) {
          newMap.set(acquisitionId, [...existing, entityId]);
        }
        return { acquisitionEntityMap: newMap };
      });

      if (isDev) {
        console.log(
          `[ConflictHighlight] Registered entity ${entityId} for acquisition ${acquisitionId}`,
        );
      }
    },

    unregisterAcquisitionEntity: (acquisitionId, entityId) => {
      set((state) => {
        const newMap = new Map(state.acquisitionEntityMap);
        const existing = newMap.get(acquisitionId) || [];
        const filtered = existing.filter((id) => id !== entityId);
        if (filtered.length > 0) {
          newMap.set(acquisitionId, filtered);
        } else {
          newMap.delete(acquisitionId);
        }
        return { acquisitionEntityMap: newMap };
      });
    },

    clearEntityMap: () => {
      set({ acquisitionEntityMap: new Map() });
      if (isDev) {
        console.log("[ConflictHighlight] Cleared entity map");
      }
    },

    setHighlightedAcquisitions: (acquisitionIds, acquisitionData) => {
      if (isDev) {
        console.log(
          `[ConflictHighlight] Setting highlighted acquisitions: ${acquisitionIds.length} items`,
        );
      }

      set({ isProcessing: true });

      // Resolve entity IDs from acquisition IDs
      const { acquisitionEntityMap } = get();
      const entityIds: string[] = [];

      for (const acqId of acquisitionIds) {
        const entities = acquisitionEntityMap.get(acqId);
        if (entities) {
          entityIds.push(...entities);
        }
        // Also try common entity ID patterns
        entityIds.push(`sar_swath_${acqId}`);
        entityIds.push(`target_${acqId}`);
        entityIds.push(`opp_${acqId}`);
        entityIds.push(`swath_${acqId}`);
      }

      // Compute time range if acquisition data provided
      let timeRange: ConflictTimeRange | null = null;
      let focusTarget: {
        latitude: number;
        longitude: number;
        acquisitionId: string;
      } | null = null;

      if (acquisitionData && acquisitionData.length > 0) {
        const startTimes = acquisitionData
          .map((a) => new Date(a.start_time).getTime())
          .filter((t) => !isNaN(t));
        const endTimes = acquisitionData
          .map((a) => new Date(a.end_time).getTime())
          .filter((t) => !isNaN(t));

        if (startTimes.length > 0 && endTimes.length > 0) {
          const minStart = new Date(Math.min(...startTimes));
          const maxEnd = new Date(Math.max(...endTimes));

          timeRange = {
            start: minStart.toISOString(),
            end: maxEnd.toISOString(),
            padding: 3, // 3 minutes padding
          };

          if (isDev) {
            console.log(
              `[ConflictHighlight] Computed time range: ${timeRange.start} - ${timeRange.end}`,
            );
          }
        }

        // Set camera focus to first acquisition with coordinates
        const firstWithCoords = acquisitionData.find(
          (a) => a.latitude !== undefined && a.longitude !== undefined,
        );
        if (
          firstWithCoords &&
          firstWithCoords.latitude &&
          firstWithCoords.longitude
        ) {
          focusTarget = {
            latitude: firstWithCoords.latitude,
            longitude: firstWithCoords.longitude,
            acquisitionId: firstWithCoords.id,
          };
        }
      }

      // Deduplicate entity IDs
      const uniqueEntityIds = [...new Set(entityIds)];

      set({
        highlightedEntityIds: uniqueEntityIds,
        conflictTimeRange: timeRange,
        shouldFocusTimeline: timeRange !== null,
        cameraFocusTarget: focusTarget,
        isProcessing: false,
      });

      if (isDev) {
        console.log(
          `[ConflictHighlight] Highlighted ${uniqueEntityIds.length} entities for ${acquisitionIds.length} acquisitions`,
        );
      }
    },

    clearHighlights: () => {
      if (isDev) {
        console.log("[ConflictHighlight] Clearing all highlights");
      }

      set({
        highlightedEntityIds: [],
        conflictTimeRange: null,
        shouldFocusTimeline: false,
        cameraFocusTarget: null,
      });
    },

    setConflictTimeRange: (range) => {
      set({ conflictTimeRange: range, shouldFocusTimeline: range !== null });
    },

    focusTimelineOnConflict: () => {
      set({ shouldFocusTimeline: true });
    },

    clearTimelineFocus: () => {
      set({ shouldFocusTimeline: false });
    },

    setCameraFocusTarget: (target) => {
      set({ cameraFocusTarget: target });
    },

    resolveEntityIds: (acquisitionIds) => {
      const { acquisitionEntityMap } = get();
      const entityIds: string[] = [];

      for (const acqId of acquisitionIds) {
        const entities = acquisitionEntityMap.get(acqId);
        if (entities) {
          entityIds.push(...entities);
        }
        // Also try common patterns
        entityIds.push(`sar_swath_${acqId}`);
        entityIds.push(`target_${acqId}`);
        entityIds.push(`opp_${acqId}`);
      }

      return [...new Set(entityIds)];
    },
  })),
);

// =============================================================================
// Selector Hooks - Use individual selectors to avoid creating new object refs
// =============================================================================

export const useConflictHighlightedEntities = () =>
  useConflictHighlightStore((state) => state.highlightedEntityIds);

// Individual selectors to avoid infinite render loops
export const useConflictTimeRangeValue = () =>
  useConflictHighlightStore((state) => state.conflictTimeRange);

export const useShouldFocusTimeline = () =>
  useConflictHighlightStore((state) => state.shouldFocusTimeline);

export const useConflictCameraTarget = () =>
  useConflictHighlightStore((state) => state.cameraFocusTarget);

export const useConflictHighlightActions = () =>
  useConflictHighlightStore((state) => ({
    setHighlightedAcquisitions: state.setHighlightedAcquisitions,
    clearHighlights: state.clearHighlights,
    focusTimelineOnConflict: state.focusTimelineOnConflict,
    clearTimelineFocus: state.clearTimelineFocus,
    setCameraFocusTarget: state.setCameraFocusTarget,
    registerAcquisitionEntity: state.registerAcquisitionEntity,
  }));
