# PR-UXSYNC-01: Selection Sync + Context Filters Checklist

## Overview

This PR implements unified selection synchronization and context filtering across the mission planner app. It ensures reliable "click → see only relevant items" behavior without adding new features or panels.

## Components Modified

| Component | Changes |
|-----------|---------|
| `selectionStore.ts` | NEW - Unified selection store for target/opportunity/acquisition/conflict |
| `ContextFilterBar.tsx` | NEW - Filter chips component for results tables |
| `useSelectionKeyboard.ts` | NEW - Keyboard handler hook (Esc to clear) |
| `CesiumViewer.tsx` | Updated - Dispatch selection on entity clicks |
| `MissionPlanning.tsx` | Updated - Context filter integration, row highlighting |
| `Inspector.tsx` | Updated - Respond to unified selection store |
| `App.tsx` | Updated - Integrated Esc key for clearing selection |
| `store/index.ts` | Updated - Export new selection store |

## Manual Verification Steps

### 1. Map → Results Sync

#### Target Selection
- [ ] Click a target marker on the map
- [ ] Verify Inspector opens with target details
- [ ] Verify dev console shows `[SelectionStore] selectTarget: <targetId> (source: map)`

#### Opportunity/Swath Selection  
- [ ] Click an opportunity/swath polygon on the map (if visible)
- [ ] Verify Inspector opens with opportunity details
- [ ] Verify dev console shows `[SelectionStore] selectOpportunity: <oppId> (source: map)`

### 2. Results Table → Map Sync

#### Row Selection
- [ ] Run a mission planning algorithm to generate results
- [ ] Click a row in the schedule table
- [ ] Verify the row highlights with blue background
- [ ] Verify Inspector opens with opportunity details
- [ ] Verify dev console shows `[SelectionStore] selectOpportunity: <oppId> (source: table)`

#### Pagination Stability
- [ ] Select a row in the results table
- [ ] Change page size (e.g., 50 → 100)
- [ ] Verify selection is preserved if the item is still visible
- [ ] Navigate to a different page
- [ ] Return to original page and verify selection state

### 3. Context Filtering

#### Filter Application
- [ ] Run mission planning to generate results with multiple targets
- [ ] Verify ContextFilterBar appears when filters are active
- [ ] Click a target chip to filter by that target
- [ ] Verify table shows only opportunities for that target
- [ ] Verify header shows "X opportunities of Y" when filtered

#### Filter Clearing
- [ ] Click the X button on a filter chip to remove it
- [ ] Verify table returns to showing all results
- [ ] Click "Clear all" to remove all filters at once
- [ ] Verify all filters are cleared

#### SAR Filters (if SAR mission)
- [ ] Verify Look Side (L/R) filter chip appears for SAR missions
- [ ] Verify Pass Direction (ASC/DESC) filter chip appears for SAR missions
- [ ] Verify filtering by these attributes works correctly

### 4. Clear Selection

#### Escape Key
- [ ] Select an item (target or opportunity)
- [ ] Press Escape key
- [ ] Verify selection is cleared
- [ ] Verify Inspector shows "Select an object to view its properties"
- [ ] Verify dev console shows `[SelectionStore] clearSelection`

#### Clear Button in Inspector
- [ ] Select an item via map or table
- [ ] Click the trash icon in Inspector header (for unified selections)
- [ ] Verify selection is cleared

#### Input Field Exception
- [ ] Focus on a text input field
- [ ] Press Escape
- [ ] Verify selection is NOT cleared (Escape is handled by input)

### 5. Inspector Content

#### Target Details
- [ ] Select a target from map
- [ ] Verify Inspector shows:
  - Target name
  - Location (latitude/longitude)
  - Priority (if set)

#### Opportunity Details
- [ ] Select an opportunity from table or map
- [ ] Verify Inspector shows:
  - Target and Satellite IDs
  - Start/End times
  - Roll/Pitch angles (if available)

### 6. Debug Logging (Dev Mode Only)

- [ ] Open browser dev console
- [ ] Perform selection actions
- [ ] Verify logs appear with format: `[SelectionStore] <action>: <details>`
- [ ] Verify logs include:
  - `selectTarget`
  - `selectOpportunity`
  - `clearSelection`
  - `setContextFilter`
  - `clearContextFilter`

### 7. No Regressions

#### Simple Mode Surface
- [ ] Verify left sidebar shows only 4 items: Workspaces, Mission Analysis, Planning, Schedule
- [ ] Verify right sidebar shows only 3 panels: Inspector, Layers, Help
- [ ] Verify Object Explorer is not visible by default

#### Existing Functionality
- [ ] Mission analysis still works correctly
- [ ] Mission planning algorithms run successfully
- [ ] Schedule commits work as expected
- [ ] Map navigation (zoom, pan, rotate) works normally

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Target selection syncs map → inspector | ⬜ |
| Opportunity selection syncs map → table → inspector | ⬜ |
| Row clicks highlight and open inspector | ⬜ |
| Context filter bar shows active filters | ⬜ |
| Filters are removable (chip X or Clear all) | ⬜ |
| Escape key clears selection | ⬜ |
| Pagination doesn't break selection | ⬜ |
| Dev mode shows selection debug logs | ⬜ |
| No Simple Mode regressions | ⬜ |

## Known Limitations

1. **Entity ID Matching**: Map entity clicks rely on ID prefixes (`target_`, `opp_`, `swath_`). Entities without these prefixes fall back to legacy scene object selection.

2. **Opportunity Lookup**: Finding opportunity metadata requires searching through planning results. If no planning has been run, opportunity details may be limited.

3. **Conflict Selection**: Conflict selection is implemented in the store but full UI integration depends on conflict panel updates in a future PR.

## Files Changed Summary

```
frontend/src/
├── store/
│   ├── selectionStore.ts    # NEW: Unified selection state
│   └── index.ts             # UPDATED: Export selection store
├── components/
│   ├── ContextFilterBar.tsx # NEW: Filter chips UI
│   ├── CesiumViewer.tsx     # UPDATED: Map click → selection
│   ├── MissionPlanning.tsx  # UPDATED: Table filtering & highlighting
│   └── ObjectExplorer/
│       └── Inspector.tsx    # UPDATED: Show unified selections
├── hooks/
│   └── useSelectionKeyboard.ts # NEW: Esc key handler
└── App.tsx                  # UPDATED: Global Esc handler
```
