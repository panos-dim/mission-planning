# PR-MAP-HIGHLIGHT-01: Unified Cesium Entity ID Contract + Highlight Adapter

## Overview

This PR implements a unified Cesium entity ID contract and highlight adapter layer to ensure deterministic map highlighting across all selection types: conflict, repair diff, and normal selection.

**Key Features:**
- Canonical entity ID patterns documented in `docs/CESIUM_ENTITY_ID_CONTRACT.md`
- Unified `highlightAdapter.ts` with O(k) entity resolution and caching
- Ghost entity clone fallback for moved items when ghost entities don't exist
- Timeline focus reliability guard (stores pending focus when timeline hidden)
- Backward compatible with existing conflict and repair highlighting

---

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `docs/CESIUM_ENTITY_ID_CONTRACT.md` | Canonical entity ID patterns and resolution rules |
| `frontend/src/adapters/highlightAdapter.ts` | Unified highlight adapter with entity resolution and styling |
| `frontend/src/store/unifiedHighlightStore.ts` | Single source of truth for all highlight state |
| `frontend/src/hooks/useUnifiedMapHighlight.ts` | Unified hook for applying Cesium entity highlighting |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/components/Map/GlobeViewport.tsx` | Added `useUnifiedMapHighlight` hook integration |
| `frontend/src/hooks/useConflictMapHighlight.ts` | Updated header for PR reference |

---

## Manual Test Steps

### Prerequisites
1. Load a mission with multiple targets
2. Run initial planning to generate acquisitions
3. Have some scheduling conflicts available (or create overlapping acquisitions)

### Test 1: Conflict Highlighting Works for SAR Swaths

- [ ] Select a conflict from the Conflicts Panel
- [ ] Verify SAR swath polygons highlight with orange fill and red outline
- [ ] Verify target markers associated with the conflict also highlight
- [ ] Verify timeline focuses on the conflict time window
- [ ] Press Esc or click Clear to deselect
- [ ] Verify all highlights are removed

### Test 2: Conflict Highlighting Works for Target Markers

- [ ] Select a conflict that involves target markers
- [ ] Verify target billboards/points highlight with orange glow
- [ ] Verify no console errors about missing entities
- [ ] Deselect and verify clean state

### Test 3: Repair Kept Items Highlight (Green)

- [ ] Switch to Repair Mode
- [ ] Run repair planning with existing schedule
- [ ] Click a "Kept" item in the Repair Diff panel
- [ ] Verify associated swath/entity highlights with green styling
- [ ] Verify timeline focuses correctly
- [ ] Verify Inspector shows "Repair: Kept" badge

### Test 4: Repair Dropped Items Highlight (Red)

- [ ] Click a "Dropped" item in the Repair Diff panel
- [ ] Verify associated entity highlights with red styling
- [ ] Verify timeline focuses correctly
- [ ] Verify Inspector shows "Repair: Dropped" badge

### Test 5: Repair Added Items Highlight (Cyan/Blue)

- [ ] Click an "Added" item in the Repair Diff panel
- [ ] Verify associated entity highlights with cyan styling
- [ ] Verify timeline focuses correctly
- [ ] Verify Inspector shows "Repair: Added" badge

### Test 6: Repair Moved Items - Ghost + Solid

- [ ] Click a "Moved" item in the Repair Diff panel
- [ ] Verify on map: **ghost** style (faded white) for old position
- [ ] Verify on map: **solid** yellow style for new position
- [ ] Verify timeline shows entire time span (from old start to new end)
- [ ] Verify Inspector shows "Repair: Moved" badge with time shift details

### Test 7: Ghost Entity Fallback (Clone Creation)

- [ ] If ghost entities don't exist in CZML, verify the adapter creates lightweight clones
- [ ] Verify ghost clones are removed when selection is cleared
- [ ] Verify no lingering ghost entities after mode switch

### Test 8: Selection Switch Clears Previous Highlights

- [ ] Select a conflict (orange highlights appear)
- [ ] Immediately select a repair diff item
- [ ] Verify orange conflict highlights are cleared before repair highlights apply
- [ ] Select a different repair item
- [ ] Verify previous repair highlights are cleared

### Test 9: Timeline Focus Reliability

- [ ] Select an item with timeline visible
- [ ] Verify timeline focuses correctly
- [ ] Hide the timeline (if possible in Simple Mode)
- [ ] Select another item
- [ ] Show the timeline again
- [ ] Verify pending focus is applied when timeline becomes visible

### Test 10: Performance with 100+ Acquisitions

- [ ] Load a large mission with 100+ acquisitions
- [ ] Select various conflicts and repair items
- [ ] Verify no FPS degradation during highlighting
- [ ] Verify entity resolution is fast (< 100ms)
- [ ] Check console for any performance warnings

### Test 11: Legacy Entity ID Patterns

- [ ] Verify entities with legacy IDs (e.g., `sar_swath_*`, `target_*`) still highlight
- [ ] Verify entities with canonical IDs (e.g., `swath:*`, `target:*`) also highlight
- [ ] Verify mixed ID patterns work together

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Conflict highlights work for SAR swaths and target markers | [ ] |
| Repair highlights work for kept/dropped/added/moved types | [ ] |
| Moved items show ghost (previous) + solid (new) positions | [ ] |
| Ghost highlight works even if renderer didn't pre-generate ghost entities | [ ] |
| Switching between conflict and repair selection clears old highlights | [ ] |
| Timeline focus is reliable even if timeline was hidden | [ ] |
| No "depends on entity ID pattern" failures | [ ] |
| No FPS degradation or full-scene scans | [ ] |
| Performance check passes on 100+ acquisitions | [ ] |

---

## Known Limitations

1. **Entity cache invalidation**: Cache is invalidated when entity count changes, not on individual add/remove. This is sufficient for most use cases but may cause extra work if entities are rapidly added/removed.

2. **Ghost clone positioning**: Ghost clones use the source entity's current position. For time-varying positions, the clone may not perfectly represent the historical position.

3. **Concurrent mode access**: The unified store supports one active highlight mode at a time. Attempting to highlight in multiple modes simultaneously will result in the last mode winning.

---

## Architecture Notes

### Entity ID Contract

All Cesium layers should follow the canonical ID patterns:

```text
target:{targetId}
opp:{opportunityId}
acq:{acquisitionId}
swath:{opportunityId}
ghost:acq:{acquisitionId}
```

### Highlight Adapter Flow

1. Store receives highlight request (conflict/repair/selection)
2. Adapter resolves logical IDs to Cesium entity IDs using cached mapping
3. Adapter applies styling based on mode and diff type
4. For moved items, adapter creates ghost clones if needed
5. On clear, adapter restores original styles and removes clones

### Timeline Focus Reliability

The unified store tracks `timelineVisible` state and stores `pendingTimelineFocus` when timeline is hidden. When timeline becomes visible, pending focus is automatically applied.

---

## Rollback Plan

If issues arise:

1. Remove `useUnifiedMapHighlight` from `GlobeViewport.tsx`
2. Existing `useConflictMapHighlight` and `useRepairMapHighlight` hooks remain functional
3. Delete new files:
   - `frontend/src/adapters/highlightAdapter.ts`
   - `frontend/src/store/unifiedHighlightStore.ts`
   - `frontend/src/hooks/useUnifiedMapHighlight.ts`
   - `docs/CESIUM_ENTITY_ID_CONTRACT.md`

---

## Related Documentation

- `docs/CESIUM_ENTITY_ID_CONTRACT.md` - Entity ID patterns reference
- `docs/PR_CONFLICT_UX_02_CHECKLIST.md` - Conflict highlighting (prerequisite)
- `docs/PR_REPAIR_UX_01_CHECKLIST.md` - Repair diff highlighting (prerequisite)
