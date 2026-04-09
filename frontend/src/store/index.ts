/**
 * Store Module - Barrel Export
 *
 * Zustand stores for state management.
 */

// Visualization store (scene modes, layers, clock sync)
export { useVisStore, type SceneMode, type ViewMode } from './visStore'

// Slew visualization store
export { useSlewVisStore, type ColorByMode, type FilterMode } from './slewVisStore'

// Target management stores
export { useTargetAddStore } from './targetAddStore'
export { usePreviewTargetsStore } from './previewTargetsStore'

// Lock mode store (map lock interaction mode)
export { useLockModeStore } from './lockModeStore'

// Pre-feasibility order store (single run-level order + targets before feasibility)
export { usePreFeasibilityOrdersStore, type PreFeasibilityOrder } from './preFeasibilityOrdersStore'

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
} from './selectionStore'

// Schedule store (master timeline state)
export { useScheduleStore, type MasterZoom } from './scheduleStore'
