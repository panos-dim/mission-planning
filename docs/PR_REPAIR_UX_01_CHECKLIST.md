# PR-REPAIR-UX-01: Repair Diff Review Checklist

## Overview

This PR implements interactive repair diff review functionality, making it easy for mission planners to understand and validate proposed repair changes before committing.

**Key Features:**
- Clickable repair diff items (kept, dropped, added, moved)
- Map highlighting when selecting diff items
- Timeline focus on selected item's time window
- Inspector shows "Repair Change" badge with details
- Moved items show ghost (previous) and solid (new) positions
- Before vs After metrics comparison header
- Preview-only mode (no DB mutation until commit)

---

## Files Changed

### New Files
| File | Purpose |
|------|---------|
| `frontend/src/store/repairHighlightStore.ts` | Zustand store for repair diff selection and highlighting state |
| `frontend/src/hooks/useRepairMapHighlight.ts` | Hook to apply Cesium entity highlighting for repair items |

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/components/RepairDiffPanel.tsx` | Fully rewritten with expandable sections, clickable items, metrics header |
| `frontend/src/components/ObjectExplorer/Inspector.tsx` | Added RepairChangeBadge component, repair item quick actions |
| `frontend/src/components/Map/GlobeViewport.tsx` | Integrated useRepairMapHighlight hook |
| `frontend/src/components/MissionPlanning.tsx` | Clear repair state when switching planning modes |

---

## Manual Test Steps

### Prerequisites
1. Load a mission with multiple targets
2. Run initial planning (from scratch)
3. Commit the schedule to create existing acquisitions
4. Switch to **Repair Mode** in Planning panel

### Test 1: Repair Diff Panel Display
- [ ] Run repair planning with some existing schedule
- [ ] Verify "Repair Preview" panel appears with metrics comparison
- [ ] Verify Before/After metrics show: Score, Conflicts, Acquisitions count
- [ ] Verify diff sections show: Kept (green), Dropped (red), Added (blue), Moved (yellow)
- [ ] Verify each section shows correct count

### Test 2: Click Kept Item
- [ ] Expand "Kept" section by clicking header
- [ ] Click an individual kept item
- [ ] Verify item row highlights with green border
- [ ] Verify associated swath/entity highlights on Cesium map (green)
- [ ] Verify timeline focuses on item's time window
- [ ] Verify Inspector shows "Repair: Kept" badge

### Test 3: Click Dropped Item
- [ ] Expand "Dropped" section
- [ ] Click an individual dropped item
- [ ] Verify item row highlights with red border
- [ ] Verify associated entity highlights on map (red)
- [ ] Verify timeline focuses correctly
- [ ] Verify Inspector shows "Repair: Dropped" badge
- [ ] Verify reason text displays (if available)

### Test 4: Click Added Item
- [ ] Expand "Added" section
- [ ] Click an individual added item
- [ ] Verify item row highlights with blue border
- [ ] Verify associated entity highlights on map (cyan/blue)
- [ ] Verify timeline focuses correctly
- [ ] Verify Inspector shows "Repair: Added" badge

### Test 5: Click Moved Item
- [ ] Expand "Moved" section
- [ ] Click an individual moved item
- [ ] Verify item row shows From → To timing visualization
- [ ] Verify item row highlights with yellow border
- [ ] Verify on map: **ghost** style (faded white) for old position, **solid** yellow for new position
- [ ] Verify timeline shows entire time span (from old start to new end)
- [ ] Verify Inspector shows "Repair: Moved" badge with time shift details
- [ ] Verify roll angle change displays (if applicable)

### Test 6: Selection Clear
- [ ] Select any diff item
- [ ] Click "Clear" button in Inspector quick actions
- [ ] Verify all map highlights are removed
- [ ] Verify selection state clears
- [ ] Verify Inspector returns to default state

### Test 7: Mode Switch Clears State
- [ ] Select a diff item while in Repair mode
- [ ] Switch to "From Scratch" mode
- [ ] Verify repair highlights are cleared
- [ ] Verify repair panel no longer shows
- [ ] Switch back to Repair mode
- [ ] Verify clean state (no lingering selection)

### Test 8: Timeline Focus Button
- [ ] Select a diff item
- [ ] Click "Focus Timeline" in Inspector quick actions
- [ ] Verify timeline zooms to item's time window with padding

### Test 9: Large Diff Performance
- [ ] Generate a repair with 50+ changes
- [ ] Verify diff sections load quickly
- [ ] Verify "Load more" pagination appears for large lists
- [ ] Verify clicking "Load more" reveals additional items
- [ ] Verify scrolling remains smooth

### Test 10: Preview Mode Safety
- [ ] Run repair planning
- [ ] Click through various diff items
- [ ] Verify NO database changes occur (check network tab)
- [ ] Verify "Preview only — not committed" hint displays
- [ ] Verify only "Commit" action triggers actual DB mutation

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Mission planner can click through "Dropped" items and immediately see what/where/when changed | [ ] |
| Planner can click "Added" items and see swath/target and timing | [ ] |
| Moved items clearly show old vs new position and timing | [ ] |
| No accidental commits or state mutation during preview | [ ] |
| Clearing selection resets all highlights | [ ] |
| Large diffs remain responsive (virtualized/paginated) | [ ] |

---

## Known Limitations

1. **Ghost entities for moved items**: Requires entities to exist with `ghost_` prefix in Cesium data source. If not present, only the new position will highlight.

2. **Entity mapping**: Highlighting depends on entity IDs following the pattern `sar_swath_{id}`, `opp_{id}`, `target_{id}`, or `acq_{id}`. Non-standard IDs may not highlight.

3. **Timeline focus**: Requires Cesium viewer timeline to be visible. If timeline is hidden, focus will silently fail.

---

## Rollback Plan

If issues arise:
1. Revert changes to `RepairDiffPanel.tsx` (restore original simple version)
2. Remove `repairHighlightStore.ts` and `useRepairMapHighlight.ts`
3. Remove repair highlight hooks from `GlobeViewport.tsx` and `Inspector.tsx`
4. Remove `clearRepairState` calls from `MissionPlanning.tsx`

---

## Related Documentation

- `docs/REPAIR_MODE.md` - Repair mode concepts and API reference
- `docs/PR_CONFLICT_UX_02_CHECKLIST.md` - Similar pattern for conflict highlighting
- `docs/API_SURFACE_USED_BY_UI.md` - API endpoints used
