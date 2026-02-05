# PR-CONFLICT-UX-01: Conflict Selection End-to-End Checklist

## Overview

This PR implements full conflict selection UX wiring across the app, making conflicts first-class selectable objects with deterministic highlight and navigation.

## Components Modified

| Component | Changes |
|-----------|---------|
| `ConflictsPanel.tsx` | Updated - Wired to unified selection store, dispatches `selectConflict` with acquisition IDs |
| `selectionStore.ts` | Updated - Added `useConflictSelection` hook and `ResolvedConflictData` interface |
| `Inspector.tsx` | Updated - Added `ConflictInspector` component with clickable acquisition links |
| `ScheduledAcquisitionsList.tsx` | Updated - Highlights conflict-related acquisitions with orange styling |

## Manual Verification Steps

### 1. Conflict Selection from Panel

#### Basic Selection
- [ ] Open the Schedule panel and switch to "Conflicts" tab
- [ ] Click on a conflict in the list
- [ ] Verify dev console shows `[ConflictsPanel] select conflict: <conflictId> (source: conflicts_panel)`
- [ ] Verify the conflict row highlights with blue left border

#### Deselection
- [ ] Click the same conflict again
- [ ] Verify dev console shows `[ConflictsPanel] deselect conflict: <conflictId>`
- [ ] Verify the highlight is removed

### 2. Inspector Conflict View

#### Conflict Details Display
- [ ] Select a conflict from the Conflicts panel
- [ ] Verify Inspector opens with conflict details:
  - Severity badge (ERROR/WARNING with appropriate color)
  - Conflict type label (Time Overlap, Slew Infeasible)
  - Conflict ID (copyable)
  - Detection timestamp
  - Description (if available)

#### Involved Acquisitions List
- [ ] Verify "Involved Acquisitions" section shows all affected acquisition IDs
- [ ] Verify each acquisition is clickable with hover effect
- [ ] Click an acquisition in the list
- [ ] Verify selection changes to that acquisition
- [ ] Verify dev console shows `[Inspector] Navigate to acquisition from conflict: <acqId>`

#### Back Navigation
- [ ] While viewing conflict in Inspector, click "Back to schedule" link
- [ ] Verify selection is cleared
- [ ] Verify Inspector returns to empty state

### 3. Schedule List Highlighting

#### Auto-Expand
- [ ] Ensure some acquisitions are committed to the schedule
- [ ] Select a conflict that involves those acquisitions
- [ ] Verify the satellite group(s) containing highlighted acquisitions auto-expand

#### Visual Highlighting
- [ ] Verify highlighted acquisitions show orange border and background
- [ ] Verify orange ring effect around highlighted rows
- [ ] Verify highlighting persists while conflict is selected

#### Scroll Into View
- [ ] Select a conflict with acquisitions that are out of view
- [ ] Verify the list auto-scrolls to bring the first highlighted acquisition into view

### 4. Clear Selection

#### Escape Key
- [ ] Select a conflict
- [ ] Press Escape key
- [ ] Verify selection is cleared
- [ ] Verify Inspector shows "Select an object to view its properties"
- [ ] Verify Schedule list highlighting is removed

#### Clear Button in Inspector
- [ ] Select a conflict
- [ ] Click the trash icon in Inspector header
- [ ] Verify selection is cleared

### 5. Multi-Acquisition Conflicts

#### 2-Item Conflicts
- [ ] Select a conflict with exactly 2 acquisitions
- [ ] Verify both acquisitions are listed in Inspector
- [ ] Verify both acquisitions are highlighted in Schedule list

#### 3+ Item Conflicts
- [ ] Select a conflict with 3 or more acquisitions
- [ ] Verify all acquisitions are listed in Inspector
- [ ] Verify all acquisitions are highlighted in Schedule list
- [ ] Click each acquisition to verify navigation works

### 6. Edge Cases

#### No Conflicts State
- [ ] When no conflicts exist, verify Conflicts panel shows "No conflicts detected"
- [ ] Verify no conflict-related UI appears elsewhere

#### Empty Schedule
- [ ] With no committed acquisitions, verify Schedule list handles highlighting gracefully
- [ ] Verify no errors in console

#### Large Horizon
- [ ] With many acquisitions (50+), select a conflict
- [ ] Verify UI remains responsive (no freezing)
- [ ] Verify scroll-into-view works correctly

### 7. Debug Logging (Dev Mode Only)

- [ ] Open browser dev console
- [ ] Perform conflict selection actions
- [ ] Verify logs appear with format:
  - `[ConflictsPanel] select/deselect conflict: <id> (source: conflicts_panel)`
  - `[SelectionStore] selectConflict: <id> (related: <count>)`
  - `[Inspector] Navigate to acquisition from conflict: <acqId>`

### 8. No Regressions

#### Existing Selection Behavior
- [ ] Target selection from map still works
- [ ] Opportunity selection from table still works
- [ ] Escape key still clears all selection types

#### Simple Mode Surface
- [ ] Conflicts tab still visible in Schedule panel
- [ ] No new panels or routes added
- [ ] No new toggles introduced

## Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| Clicking a conflict highlights correct acquisitions in schedule list | ⬜ |
| Inspector shows full conflict details with clickable acquisitions | ⬜ |
| Clicking acquisition in inspector navigates to that acquisition | ⬜ |
| Clear selection works (Esc and button) | ⬜ |
| Works for 2-item conflicts | ⬜ |
| Works for 3+-item conflicts | ⬜ |
| No dead paths introduced | ⬜ |
| UX remains simple (conflict info only when needed) | ⬜ |
| Works for large horizons without freezing | ⬜ |

## Files Changed Summary

```
frontend/src/
├── store/
│   └── selectionStore.ts    # UPDATED: Added conflict selection helpers
├── components/
│   ├── ConflictsPanel.tsx   # UPDATED: Wired to unified selection store
│   ├── ScheduledAcquisitionsList.tsx # UPDATED: Conflict highlighting
│   └── ObjectExplorer/
│       └── Inspector.tsx    # UPDATED: Added ConflictInspector component
```

## Known Limitations

1. **Map Highlighting**: Full swath/footprint highlighting on the Cesium map requires CZML manipulation and is deferred to a future PR. The current implementation focuses on schedule list highlighting.

2. **Timeline Auto-Scroll**: Auto-scrolling the Cesium timeline to the conflict time range is not implemented. Users can manually navigate using the timeline controls.

3. **Opportunity Resolution**: If a conflict references acquisition IDs that don't match loaded opportunities, the Inspector will still show the IDs but won't have full metadata.

## Related Documentation

- `docs/PR_UXSYNC_01_CHECKLIST.md` - Original selection sync implementation
- `docs/API_SURFACE_USED_BY_UI.md` - Conflict API endpoints used
- `docs/frontend_nav_graph.json` - Navigation structure (no changes)
