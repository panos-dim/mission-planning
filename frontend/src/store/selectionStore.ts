/**
 * Selection Store - Single Source of Truth for UI Selection
 *
 * This store manages all selection state across the mission planner app:
 * - Target selection (from map markers or target lists)
 * - Opportunity selection (from map swaths/polygons or results tables)
 * - Acquisition selection (committed schedule items)
 * - Conflict selection (from conflicts panel)
 *
 * Context filters are local to each view (Analysis, Planning, Schedule)
 * and control what subset of data is shown in results tables.
 */

import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";

// Dev mode check compatible with Vite
const isDev = import.meta.env?.DEV ?? false;

// =============================================================================
// Types
// =============================================================================

export type SelectionType =
  | "target"
  | "opportunity"
  | "acquisition"
  | "conflict"
  | null;

export type ViewContext = "analysis" | "planning" | "schedule";

export interface SelectionState {
  // Primary selection
  selectedType: SelectionType;
  selectedTargetId: string | null;
  selectedOpportunityId: string | null;
  selectedAcquisitionId: string | null;
  selectedConflictId: string | null;

  // Related IDs for highlighting (e.g., all acquisitions in a conflict)
  highlightedTargetIds: string[];
  highlightedOpportunityIds: string[];
  highlightedAcquisitionIds: string[];

  // Context filters (per-view, not global)
  contextFilters: {
    analysis: ContextFilter;
    planning: ContextFilter;
    schedule: ContextFilter;
  };

  // UI state
  inspectorOpen: boolean;
  lastSelectionSource:
    | "map"
    | "table"
    | "timeline"
    | "inspector"
    | "repair"
    | null;
}

export interface ContextFilter {
  targetId: string | null;
  satelliteId: string | null;
  lookSide: "LEFT" | "RIGHT" | null;
  passDirection: "ASCENDING" | "DESCENDING" | null;
}

const emptyContextFilter: ContextFilter = {
  targetId: null,
  satelliteId: null,
  lookSide: null,
  passDirection: null,
};

interface SelectionActions {
  // Target selection
  selectTarget: (
    targetId: string | null,
    source?: SelectionState["lastSelectionSource"],
  ) => void;

  // Opportunity selection
  selectOpportunity: (
    opportunityId: string | null,
    source?: SelectionState["lastSelectionSource"],
  ) => void;

  // Acquisition selection
  selectAcquisition: (
    acquisitionId: string | null,
    source?: SelectionState["lastSelectionSource"],
  ) => void;

  // Conflict selection
  selectConflict: (
    conflictId: string | null,
    relatedAcquisitionIds?: string[],
  ) => void;

  // Clear all selection
  clearSelection: () => void;

  // Highlight related items (without changing primary selection)
  setHighlightedTargets: (ids: string[]) => void;
  setHighlightedOpportunities: (ids: string[]) => void;
  setHighlightedAcquisitions: (ids: string[]) => void;

  // Context filter actions
  setContextFilter: (view: ViewContext, filter: Partial<ContextFilter>) => void;
  clearContextFilter: (view: ViewContext) => void;
  clearAllContextFilters: () => void;

  // Inspector
  setInspectorOpen: (open: boolean) => void;
  toggleInspector: () => void;
}

// =============================================================================
// Initial State
// =============================================================================

const initialState: SelectionState = {
  selectedType: null,
  selectedTargetId: null,
  selectedOpportunityId: null,
  selectedAcquisitionId: null,
  selectedConflictId: null,
  highlightedTargetIds: [],
  highlightedOpportunityIds: [],
  highlightedAcquisitionIds: [],
  contextFilters: {
    analysis: { ...emptyContextFilter },
    planning: { ...emptyContextFilter },
    schedule: { ...emptyContextFilter },
  },
  inspectorOpen: false,
  lastSelectionSource: null,
};

// =============================================================================
// Store
// =============================================================================

export const useSelectionStore = create<SelectionState & SelectionActions>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      ...initialState,

      selectTarget: (targetId, source = null) => {
        const prevState = get();
        const isDeselect =
          targetId === null || targetId === prevState.selectedTargetId;

        if (isDev) {
          console.log(
            `[SelectionStore] selectTarget: ${isDeselect ? "deselect" : targetId} (source: ${source})`,
          );
        }

        set({
          selectedType: isDeselect ? null : "target",
          selectedTargetId: isDeselect ? null : targetId,
          selectedOpportunityId: null,
          selectedAcquisitionId: null,
          selectedConflictId: null,
          highlightedTargetIds: isDeselect ? [] : [targetId!],
          highlightedOpportunityIds: [],
          highlightedAcquisitionIds: [],
          inspectorOpen: !isDeselect,
          lastSelectionSource: source,
        });
      },

      selectOpportunity: (opportunityId, source = null) => {
        const prevState = get();
        const isDeselect =
          opportunityId === null ||
          opportunityId === prevState.selectedOpportunityId;

        if (isDev) {
          console.log(
            `[SelectionStore] selectOpportunity: ${isDeselect ? "deselect" : opportunityId} (source: ${source})`,
          );
        }

        set({
          selectedType: isDeselect ? null : "opportunity",
          selectedTargetId: null,
          selectedOpportunityId: isDeselect ? null : opportunityId,
          selectedAcquisitionId: null,
          selectedConflictId: null,
          highlightedTargetIds: [],
          highlightedOpportunityIds: isDeselect ? [] : [opportunityId!],
          highlightedAcquisitionIds: [],
          inspectorOpen: !isDeselect,
          lastSelectionSource: source,
        });
      },

      selectAcquisition: (acquisitionId, source = null) => {
        const prevState = get();
        const isDeselect =
          acquisitionId === null ||
          acquisitionId === prevState.selectedAcquisitionId;

        if (isDev) {
          console.log(
            `[SelectionStore] selectAcquisition: ${isDeselect ? "deselect" : acquisitionId} (source: ${source})`,
          );
        }

        set({
          selectedType: isDeselect ? null : "acquisition",
          selectedTargetId: null,
          selectedOpportunityId: null,
          selectedAcquisitionId: isDeselect ? null : acquisitionId,
          selectedConflictId: null,
          highlightedTargetIds: [],
          highlightedOpportunityIds: [],
          highlightedAcquisitionIds: isDeselect ? [] : [acquisitionId!],
          inspectorOpen: !isDeselect,
          lastSelectionSource: source,
        });
      },

      selectConflict: (conflictId, relatedAcquisitionIds = []) => {
        const prevState = get();
        const isDeselect =
          conflictId === null || conflictId === prevState.selectedConflictId;

        if (isDev) {
          console.log(
            `[SelectionStore] selectConflict: ${isDeselect ? "deselect" : conflictId} (related: ${relatedAcquisitionIds.length})`,
          );
        }

        set({
          selectedType: isDeselect ? null : "conflict",
          selectedTargetId: null,
          selectedOpportunityId: null,
          selectedAcquisitionId: null,
          selectedConflictId: isDeselect ? null : conflictId,
          highlightedTargetIds: [],
          highlightedOpportunityIds: [],
          highlightedAcquisitionIds: isDeselect ? [] : relatedAcquisitionIds,
          inspectorOpen: !isDeselect,
          lastSelectionSource: "table",
        });
      },

      clearSelection: () => {
        if (isDev) {
          console.log("[SelectionStore] clearSelection");
        }

        set({
          selectedType: null,
          selectedTargetId: null,
          selectedOpportunityId: null,
          selectedAcquisitionId: null,
          selectedConflictId: null,
          highlightedTargetIds: [],
          highlightedOpportunityIds: [],
          highlightedAcquisitionIds: [],
          inspectorOpen: false,
          lastSelectionSource: null,
        });
      },

      setHighlightedTargets: (ids) => set({ highlightedTargetIds: ids }),
      setHighlightedOpportunities: (ids) =>
        set({ highlightedOpportunityIds: ids }),
      setHighlightedAcquisitions: (ids) =>
        set({ highlightedAcquisitionIds: ids }),

      setContextFilter: (view, filter) => {
        if (isDev) {
          console.log(`[SelectionStore] setContextFilter (${view}):`, filter);
        }

        set((state) => ({
          contextFilters: {
            ...state.contextFilters,
            [view]: {
              ...state.contextFilters[view],
              ...filter,
            },
          },
        }));
      },

      clearContextFilter: (view) => {
        if (isDev) {
          console.log(`[SelectionStore] clearContextFilter (${view})`);
        }

        set((state) => ({
          contextFilters: {
            ...state.contextFilters,
            [view]: { ...emptyContextFilter },
          },
        }));
      },

      clearAllContextFilters: () => {
        if (isDev) {
          console.log("[SelectionStore] clearAllContextFilters");
        }

        set({
          contextFilters: {
            analysis: { ...emptyContextFilter },
            planning: { ...emptyContextFilter },
            schedule: { ...emptyContextFilter },
          },
        });
      },

      setInspectorOpen: (open) => set({ inspectorOpen: open }),
      toggleInspector: () =>
        set((state) => ({ inspectorOpen: !state.inspectorOpen })),
    })),
    { name: "SelectionStore", enabled: import.meta.env?.DEV ?? false },
  ),
);

// =============================================================================
// Selector Hooks
// =============================================================================

export const useSelection = () =>
  useSelectionStore((state) => ({
    type: state.selectedType,
    targetId: state.selectedTargetId,
    opportunityId: state.selectedOpportunityId,
    acquisitionId: state.selectedAcquisitionId,
    conflictId: state.selectedConflictId,
    source: state.lastSelectionSource,
  }));

export const useHighlightedIds = () =>
  useSelectionStore((state) => ({
    targets: state.highlightedTargetIds,
    opportunities: state.highlightedOpportunityIds,
    acquisitions: state.highlightedAcquisitionIds,
  }));

export const useContextFilter = (view: ViewContext) =>
  useSelectionStore((state) => state.contextFilters[view]);

export const useHasActiveContextFilter = (view: ViewContext) =>
  useSelectionStore((state) => {
    const filter = state.contextFilters[view];
    return !!(
      filter.targetId ||
      filter.satelliteId ||
      filter.lookSide ||
      filter.passDirection
    );
  });

export const useInspectorState = () =>
  useSelectionStore((state) => ({
    isOpen: state.inspectorOpen,
    selectedType: state.selectedType,
  }));

// =============================================================================
// Utility: Check if an item matches the current selection
// =============================================================================

export const isItemSelected = (
  state: SelectionState,
  type: SelectionType,
  id: string,
): boolean => {
  switch (type) {
    case "target":
      return state.selectedTargetId === id;
    case "opportunity":
      return state.selectedOpportunityId === id;
    case "acquisition":
      return state.selectedAcquisitionId === id;
    case "conflict":
      return state.selectedConflictId === id;
    default:
      return false;
  }
};

export const isItemHighlighted = (
  state: SelectionState,
  type: SelectionType,
  id: string,
): boolean => {
  switch (type) {
    case "target":
      return state.highlightedTargetIds.indexOf(id) !== -1;
    case "opportunity":
      return state.highlightedOpportunityIds.indexOf(id) !== -1;
    case "acquisition":
      return state.highlightedAcquisitionIds.indexOf(id) !== -1;
    default:
      return false;
  }
};

// =============================================================================
// Conflict Selection Helpers
// =============================================================================

/**
 * Resolved conflict data for UI display
 */
export interface ResolvedConflictData {
  conflictId: string;
  type: string;
  severity: string;
  description?: string;
  acquisitionIds: string[];
  satelliteId?: string;
  timeRange?: {
    start: string;
    end: string;
  };
  detectedAt: string;
}

/**
 * Hook for accessing conflict-related selection state
 */
export const useConflictSelection = () =>
  useSelectionStore((state) => ({
    isConflictSelected: state.selectedType === "conflict",
    selectedConflictId: state.selectedConflictId,
    highlightedAcquisitionIds: state.highlightedAcquisitionIds,
    selectConflict: useSelectionStore.getState().selectConflict,
    clearSelection: useSelectionStore.getState().clearSelection,
    selectAcquisition: useSelectionStore.getState().selectAcquisition,
  }));
