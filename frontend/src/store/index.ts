/**
 * Store Module - Barrel Export
 *
 * Zustand stores for state management.
 */

// Visualization store (scene modes, layers, clock sync)
export { useVisStore, type SceneMode, type ViewMode } from "./visStore";

// Slew visualization store
export {
  useSlewVisStore,
  type ColorByMode,
  type FilterMode,
} from "./slewVisStore";

// Target management stores
export { useTargetAddStore } from "./targetAddStore";
export { usePreviewTargetsStore } from "./previewTargetsStore";

// Selection store (unified selection state)
export {
  useSelectionStore,
  useSelection,
  useHighlightedIds,
  useContextFilter,
  useHasActiveContextFilter,
  useInspectorState,
  isItemSelected,
  isItemHighlighted,
  type SelectionType,
  type ViewContext,
  type ContextFilter,
} from "./selectionStore";
