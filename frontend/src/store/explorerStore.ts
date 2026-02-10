/**
 * Object Explorer Store
 *
 * Zustand store for managing the STK-style Object Explorer tree state,
 * selection, and inspector data synchronization.
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";
import type {
  TreeNodeType,
  ContextMenuState,
  InspectorData,
} from "../types/explorer";

// =============================================================================
// Store Types
// =============================================================================

interface ExplorerState {
  // Tree state
  expandedNodes: Set<string>;
  selectedNodeId: string | null;
  selectedNodeType: TreeNodeType | null;
  searchQuery: string;

  // Active items (for sync with map/timeline)
  activePlanId: string | null;
  activeOrderId: string | null;
  filterByTarget: string | null;

  // Context menu
  contextMenu: ContextMenuState;

  // Inspector cache
  inspectorCache: Map<string, InspectorData>;

  // UI state
  isTreeLoading: boolean;
  treeError: string | null;

  // History tracking for runs
  analysisRuns: AnalysisRunSummary[];
  planningRuns: PlanningRunSummary[];
}

interface AnalysisRunSummary {
  id: string;
  timestamp: string;
  opportunitiesCount: number;
  missionMode: string;
}

interface PlanningRunSummary {
  id: string;
  algorithm: string;
  timestamp: string;
  accepted: number;
  totalValue: number;
}

interface ExplorerActions {
  // Tree navigation
  toggleNode: (nodeId: string) => void;
  expandNode: (nodeId: string) => void;
  collapseNode: (nodeId: string) => void;
  expandAll: () => void;
  collapseAll: () => void;

  // Selection
  selectNode: (nodeId: string | null, nodeType?: TreeNodeType | null) => void;
  clearSelection: () => void;

  // Search
  setSearchQuery: (query: string) => void;
  clearSearch: () => void;

  // Active plan/order
  setActivePlan: (planId: string | null) => void;
  setActiveOrder: (orderId: string | null) => void;
  setFilterByTarget: (targetId: string | null) => void;

  // Context menu
  openContextMenu: (
    x: number,
    y: number,
    nodeId: string,
    nodeType: TreeNodeType,
  ) => void;
  closeContextMenu: () => void;

  // Inspector cache
  cacheInspectorData: (nodeId: string, data: InspectorData) => void;
  clearInspectorCache: () => void;

  // Loading/error state
  setTreeLoading: (loading: boolean) => void;
  setTreeError: (error: string | null) => void;

  // Run history
  addAnalysisRun: (run: AnalysisRunSummary) => void;
  addPlanningRun: (run: PlanningRunSummary) => void;
  clearRunHistory: () => void;

  // Bulk operations
  setExpandedNodes: (nodes: Set<string>) => void;
  reset: () => void;
}

type ExplorerStore = ExplorerState & ExplorerActions;

// =============================================================================
// Initial State
// =============================================================================

const initialState: ExplorerState = {
  expandedNodes: new Set(["workspace", "scenario", "assets", "results"]),
  selectedNodeId: null,
  selectedNodeType: null,
  searchQuery: "",
  activePlanId: null,
  activeOrderId: null,
  filterByTarget: null,
  contextMenu: {
    isOpen: false,
    x: 0,
    y: 0,
    nodeId: null,
    nodeType: null,
    actions: [],
  },
  inspectorCache: new Map(),
  isTreeLoading: false,
  treeError: null,
  analysisRuns: [],
  planningRuns: [],
};

// =============================================================================
// Store Implementation
// =============================================================================

export const useExplorerStore = create<ExplorerStore>()(
  devtools(
    persist(
      (set, get) => ({
        ...initialState,

        // Tree navigation
        toggleNode: (nodeId: string) => {
          set((state) => {
            const newExpanded = new Set(state.expandedNodes);
            if (newExpanded.has(nodeId)) {
              newExpanded.delete(nodeId);
            } else {
              newExpanded.add(nodeId);
            }
            return { expandedNodes: newExpanded };
          });
        },

        expandNode: (nodeId: string) => {
          set((state) => {
            const newExpanded = new Set(state.expandedNodes);
            newExpanded.add(nodeId);
            return { expandedNodes: newExpanded };
          });
        },

        collapseNode: (nodeId: string) => {
          set((state) => {
            const newExpanded = new Set(state.expandedNodes);
            newExpanded.delete(nodeId);
            return { expandedNodes: newExpanded };
          });
        },

        expandAll: () => {
          // This will be called with all node IDs from the tree component
          // For now, expand the main sections
          set({
            expandedNodes: new Set([
              "workspace",
              "scenario",
              "assets",
              "satellites",
              "targets",
              "ground_stations",
              "constraints",
              "runs",
              "results",
              "opportunities",
              "plans",
              "orders",
            ]),
          });
        },

        collapseAll: () => {
          set({ expandedNodes: new Set(["workspace"]) });
        },

        // Selection
        selectNode: (nodeId: string | null, nodeType?: TreeNodeType | null) => {
          set({
            selectedNodeId: nodeId,
            selectedNodeType: nodeType ?? null,
          });
        },

        clearSelection: () => {
          set({
            selectedNodeId: null,
            selectedNodeType: null,
          });
        },

        // Search
        setSearchQuery: (query: string) => {
          set({ searchQuery: query });
        },

        clearSearch: () => {
          set({ searchQuery: "" });
        },

        // Active plan/order
        setActivePlan: (planId: string | null) => {
          set({ activePlanId: planId });
        },

        setActiveOrder: (orderId: string | null) => {
          set({ activeOrderId: orderId });
        },

        setFilterByTarget: (targetId: string | null) => {
          set({ filterByTarget: targetId });
        },

        // Context menu
        openContextMenu: (
          x: number,
          y: number,
          nodeId: string,
          nodeType: TreeNodeType,
        ) => {
          set({
            contextMenu: {
              isOpen: true,
              x,
              y,
              nodeId,
              nodeType,
              actions: [], // Actions will be populated by the component based on node type
            },
          });
        },

        closeContextMenu: () => {
          set({
            contextMenu: {
              ...get().contextMenu,
              isOpen: false,
              nodeId: null,
              nodeType: null,
            },
          });
        },

        // Inspector cache
        cacheInspectorData: (nodeId: string, data: InspectorData) => {
          set((state) => {
            const newCache = new Map(state.inspectorCache);
            newCache.set(nodeId, data);
            return { inspectorCache: newCache };
          });
        },

        clearInspectorCache: () => {
          set({ inspectorCache: new Map() });
        },

        // Loading/error state
        setTreeLoading: (loading: boolean) => {
          set({ isTreeLoading: loading });
        },

        setTreeError: (error: string | null) => {
          set({ treeError: error });
        },

        // Run history
        addAnalysisRun: (run: AnalysisRunSummary) => {
          set((state) => ({
            analysisRuns: [run, ...state.analysisRuns].slice(0, 20), // Keep last 20
          }));
        },

        addPlanningRun: (run: PlanningRunSummary) => {
          set((state) => ({
            planningRuns: [run, ...state.planningRuns].slice(0, 50), // Keep last 50
          }));
        },

        clearRunHistory: () => {
          set({ analysisRuns: [], planningRuns: [] });
        },

        // Bulk operations
        setExpandedNodes: (nodes: Set<string>) => {
          set({ expandedNodes: nodes });
        },

        reset: () => {
          set({
            ...initialState,
            expandedNodes: new Set([
              "workspace",
              "scenario",
              "assets",
              "results",
            ]),
          });
        },
      }),
      {
        name: "explorer-store",
        // Custom serialization for Set and Map
        storage: {
          getItem: (name) => {
            const str = localStorage.getItem(name);
            if (!str) return null;
            const parsed = JSON.parse(str);
            return {
              state: {
                ...parsed.state,
                expandedNodes: new Set(parsed.state.expandedNodes || []),
                inspectorCache: new Map(), // Don't persist cache
              },
            };
          },
          setItem: (name, value) => {
            const toStore = {
              state: {
                ...value.state,
                expandedNodes: Array.from(value.state.expandedNodes || []),
                inspectorCache: [], // Don't persist cache
              },
            };
            localStorage.setItem(name, JSON.stringify(toStore));
          },
          removeItem: (name) => localStorage.removeItem(name),
        },
        partialize: (state) => ({
          expandedNodes: state.expandedNodes,
          activePlanId: state.activePlanId,
          activeOrderId: state.activeOrderId,
          analysisRuns: state.analysisRuns,
          planningRuns: state.planningRuns,
        }),
      },
    ),
    { name: "ExplorerStore", enabled: import.meta.env?.DEV ?? false },
  ),
);

// =============================================================================
// Selector Hooks
// =============================================================================

export const useTreeState = () =>
  useExplorerStore((state) => ({
    expandedNodes: state.expandedNodes,
    selectedNodeId: state.selectedNodeId,
    selectedNodeType: state.selectedNodeType,
    searchQuery: state.searchQuery,
    isLoading: state.isTreeLoading,
    error: state.treeError,
  }));

export const useSelectionState = () =>
  useExplorerStore((state) => ({
    selectedNodeId: state.selectedNodeId,
    selectedNodeType: state.selectedNodeType,
    activePlanId: state.activePlanId,
    activeOrderId: state.activeOrderId,
    filterByTarget: state.filterByTarget,
  }));

export const useContextMenuState = () =>
  useExplorerStore((state) => state.contextMenu);

export const useRunHistory = () =>
  useExplorerStore((state) => ({
    analysisRuns: state.analysisRuns,
    planningRuns: state.planningRuns,
  }));
