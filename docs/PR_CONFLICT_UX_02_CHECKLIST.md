# PR-CONFLICT-UX-02: Conflict UX Enhancement Checklist

## Overview

This PR extends the conflict selection UX (PR-CONFLICT-UX-01) to highlight conflict acquisitions on the Cesium map and focus the timeline on the conflict time window.

## Features Implemented

### 1. Cesium Map Highlighting

When a conflict is selected, involved acquisitions are highlighted on the map:

- **Store**: `conflictHighlightStore.ts` - Manages acquisition→entity mapping and highlight state
- **Hook**: `useConflictMapHighlight.ts` - Applies visual highlighting to Cesium entities
- **Integration**: Added to `GlobeViewport.tsx`

### 2. Timeline Focus

When a conflict is selected, the timeline automatically focuses on the conflict time window:

- Computes `min(start_time)` and `max(end_time)` across conflict acquisitions
- Sets timeline viewport with ~3 minutes padding
- Jumps clock to start of conflict

### 3. Quick Actions in ConflictInspector

Two quick action buttons added to the ConflictInspector:

- **Focus on Map**: Flies camera to the first acquisition's target location
- **Focus Timeline**: Re-focuses timeline on the conflict time window

## Acceptance Criteria Checklist

### Map Highlighting

- [ ] Select conflict → map highlights correct swaths/targets with orange emphasis
- [ ] Multiple acquisitions (2+) in conflict all get highlighted
- [ ] Clear selection (Esc) → map highlights are removed
- [ ] Select different conflict → previous highlights clear, new ones apply
- [ ] Highlighting applies to SAR swaths (polygons) and target markers (billboards)
- [ ] No new geometry types added - only emphasis styling on existing primitives

### Timeline Focus

- [ ] Select conflict → timeline focuses on correct time window
- [ ] Time window includes ~3 minutes padding on each side
- [ ] Clock jumps to start of conflict time range
- [ ] Clear selection → timeline can be manually navigated again
- [ ] If timeline not visible in Simple Mode, focus is applied silently

### Quick Actions

- [ ] "Focus on Map" button visible when conflict selected
- [ ] "Focus Timeline" button visible when conflict selected
- [ ] "Focus on Map" → camera flies to first acquisition location
- [ ] "Focus Timeline" → timeline re-focuses on conflict window
- [ ] Buttons hidden when no conflict selected

### Performance

- [ ] Highlighting is O(k) for k conflict items
- [ ] No full scene re-render on each highlight
- [ ] Acquisition→entity mapping is cached
- [ ] No FPS degradation on large horizons (100+ acquisitions)

## Files Changed

### New Files

| File | Description |
|------|-------------|
| `frontend/src/store/conflictHighlightStore.ts` | Zustand store for conflict highlight state and acquisition→entity mapping |
| `frontend/src/hooks/useConflictMapHighlight.ts` | React hook for applying Cesium entity highlighting |

### Modified Files

| File | Changes |
|------|---------|
| `frontend/src/components/Map/GlobeViewport.tsx` | Added `useConflictMapHighlight` hook integration |
| `frontend/src/components/ObjectExplorer/Inspector.tsx` | Added focus handlers and passed props to ConflictInspector |

### ConflictInspector Changes

Added props:
- `onFocusMap?: () => void`
- `onFocusTimeline?: () => void`

Added Quick Actions section with ActionButton components for Focus on Map and Focus Timeline.

## Dev Logging

Conflict highlight actions are logged in dev mode:

```
[ConflictHighlight] Setting highlighted acquisitions: 2 items
[ConflictHighlight] Highlighted 3 entities for 2 acquisitions
[ConflictHighlight] Focused timeline on conflict: 2024-01-15T10:30:00Z - 2024-01-15T10:45:00Z
[ConflictHighlight] Clearing all highlights
[Inspector] Focus map on conflict: conflict_123 acquisitions: 2
[Inspector] Focus timeline on conflict: conflict_123
```

## Testing Steps

1. **Setup**: Create or load a mission with scheduling conflicts
2. **Select Conflict**: Click on a conflict in the ConflictsPanel
3. **Verify Map**: Check that involved acquisitions are highlighted with orange/red styling
4. **Verify Timeline**: Check that timeline is focused on the conflict time window
5. **Test Quick Actions**: Click "Focus on Map" and "Focus Timeline" buttons
6. **Test Deselection**: Press Esc or click elsewhere, verify highlights clear
7. **Test Switch**: Select a different conflict, verify old highlights clear and new ones apply

## Constraints Honored

- ✅ No new panels or routes added
- ✅ No backend changes
- ✅ No new endpoints
- ✅ No new overlays/toggles
- ✅ No new workflow steps
- ✅ No changes to planning algorithms or DB schema
- ✅ Uses existing data from schedule horizon + acquisitions

## Related PRs

- **PR-CONFLICT-UX-01**: Initial conflict selection and unified selection store (prerequisite)
