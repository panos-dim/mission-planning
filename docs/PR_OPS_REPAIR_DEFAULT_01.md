# PR-OPS-REPAIR-DEFAULT-01: Repair-First Planner + Hard Locks Only + Schedule Timeline

## Overview

This PR implements team feedback to make mission planning "ops-grade and simple":

1. **Repair-First Workflow** - Mission planner always operates in Repair mode
2. **Simplified Lock Model** - Only Hard Lock and Unlocked states (soft locks removed)
3. **Full Flexibility Repair** - Repair can fully rearrange all unlocked tasks
4. **Narrative Summary** - Human-readable explanation of what changed
5. **Schedule Timeline** - Scrollable timeline view of scheduled acquisitions

---

## Behavior Changes Summary

### A) Repair-First Workflow

| Before | After |
|--------|-------|
| Mode selector: From Scratch / Incremental / Repair | Mode selector hidden in Simple Mode |
| Default mode: `from_scratch` | Default mode: `repair` |
| Button label: "Run Mission Planning" | Button label: "Repair Schedule" |

**Files Changed:**
- `frontend/src/components/MissionPlanning.tsx`
  - Default `planningMode` state → `"repair"`
  - Updated button label to "Repair Schedule"

### B) Lock Model Simplification

| Before | After |
|--------|-------|
| Three lock levels: `none`, `soft`, `hard` | Two lock levels: `none`, `hard` |
| Soft lock = yellow, modifiable by policy | Soft locks deprecated, treated as `none` |
| Lock toggle cycles through 3 states | Lock toggle toggles between 2 states |

**Migration:**
- Database migration v2.2 automatically normalizes all existing `soft` locks to `none`
- Backend endpoints accept `soft` for backwards compatibility but normalize to `none`

**Files Changed:**
- `frontend/src/components/LockToggle.tsx`
  - Simplified toggle: `none` ↔ `hard` only
  - Removed soft lock button from `BulkLockActions`
- `backend/schedule_persistence.py`
  - Added `_migrate_to_v2_2()` migration
  - Updated `commit_plan()` to normalize soft → none
  - Schema version: `2.1` → `2.2`
- `backend/routers/schedule.py`
  - Updated `update_acquisition_lock` endpoint
  - Updated `bulk_update_lock` endpoint
  - Both normalize `soft` → `none`

### C) Repair Output Narrative

Added human-readable summary of repair changes:

```
Replaced 3 acquisitions with 5 higher-value alternatives.
Rescheduled 2 acquisitions to better time slots.
12 acquisitions unchanged.
Schedule value improved by 15.3 points.
Resolved 2 scheduling conflicts.
```

**Features:**
- Counts: kept / moved / dropped / added
- Score impact with +/- indication
- Conflict resolution summary
- Expandable reasons list

**Files Changed:**
- `frontend/src/components/RepairDiffPanel.tsx`
  - Added `NarrativeSummary` component
  - Integrated into repair results display

### D) Schedule Timeline Overview

New Timeline tab in Schedule panel:

**Features:**
- Vertical scrollable timeline grouped by day
- Each card shows:
  - Time range (UTC) with duration
  - Satellite name
  - Target name
  - Hard Lock badge (shield icon)
  - Conflict badge (warning icon)
- Clicking a card:
  - Selects acquisition in `selectionStore`
  - Opens Inspector details
  - Focuses Cesium map and timeline

**Files Changed:**
- `frontend/src/components/ScheduleTimeline.tsx` (new file)
- `frontend/src/components/SchedulePanel.tsx`
  - Added Timeline tab
  - Converts orders to timeline acquisitions
- `frontend/src/constants/simpleMode.ts`
  - Added `TIMELINE` to `SCHEDULE_TABS`
  - Added to `SIMPLE_MODE_SCHEDULE_TABS`

### E) Repair Full Flexibility

Updated repair engine defaults:
- All unlocked items are fully flexible (can be rearranged, replaced, or dropped)
- Only hard-locked items are immutable
- `soft_lock_policy` parameter deprecated (always uses `allow_replace` behavior)

**Files Changed:**
- `backend/incremental_planning.py`
  - Updated `SoftLockPolicy` docstring
- `backend/routers/schedule.py`
  - Updated `RepairPlanRequestModel` documentation

---

## Migration Notes

### Database Migration (v2.1 → v2.2)

The migration runs automatically on first database access:

```sql
UPDATE acquisitions
SET lock_level = 'none', updated_at = ?
WHERE lock_level = 'soft'
```

**Impact:**
- All previously soft-locked acquisitions become unlocked
- They are now fully flexible for repair operations
- If you need to protect specific acquisitions, hard-lock them manually

### API Backwards Compatibility

- `lock_level: "soft"` is accepted but normalized to `"none"`
- No breaking changes to API contracts
- Existing API clients will continue to work

---

## UX Spec: Timeline Tab

### Layout

```
┌─────────────────────────────────────┐
│ [Committed] [Timeline] [Conflicts]  │  ← Tab bar
├─────────────────────────────────────┤
│ Today                          3 acq│  ← Sticky day header
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ 09:15 – 09:18 (3m)          🛡️ →│ │  ← Acquisition card
│ │ 🛰 SAT-001  📍 Target-Alpha     │ │
│ └─────────────────────────────────┘ │
│ ┌─────────────────────────────────┐ │
│ │ 10:42 – 10:45 (3m)           →│ │
│ │ 🛰 SAT-002  📍 Target-Beta      │ │
│ └─────────────────────────────────┘ │
├─────────────────────────────────────┤
│ Tomorrow                       5 acq│
├─────────────────────────────────────┤
│ ...                                 │
└─────────────────────────────────────┘
│ 8 total acquisitions    2 locked    │  ← Sticky footer
└─────────────────────────────────────┘
```

### Interactions

| Action | Result |
|--------|--------|
| Click acquisition card | Select in store, open Inspector, focus map |
| Scroll timeline | Smooth vertical scroll, sticky day headers |
| Hard lock badge | Red shield icon indicates immutable |
| Conflict badge | Yellow warning icon indicates conflict |

---

## Manual Verification Checklist

### Lock/Unlock Operations
- [ ] Lock toggle works from schedule list row
- [ ] Lock toggle works from Timeline card (via Inspector)
- [ ] Lock toggle works from Inspector panel
- [ ] Bulk lock/unlock works with multiple selections
- [ ] Only two states shown: Unlocked (gray) and Hard Lock (red)

### Repair Behavior
- [ ] Repair respects hard locks (never moves/drops them)
- [ ] Repair can rearrange all unlocked items
- [ ] Narrative summary matches actual diff counts
- [ ] Score delta displayed correctly (+/-)
- [ ] Conflict resolution count accurate

### Timeline Tab
- [ ] Timeline tab visible in Schedule panel
- [ ] Acquisitions grouped by day with correct labels
- [ ] Click highlights acquisition on map
- [ ] Click opens Inspector with details
- [ ] Smooth scrolling with 500+ items
- [ ] Hard lock badge displays correctly
- [ ] Conflict badge displays correctly

### Regression Tests
- [ ] Existing scheduled orders display correctly
- [ ] Commit to Schedule still works
- [ ] Planning results display correctly
- [ ] No console errors in browser

---

## Files Modified

### Frontend
- `src/components/MissionPlanning.tsx` - Repair-first defaults, button label
- `src/components/LockToggle.tsx` - Simplified lock toggle
- `src/components/RepairDiffPanel.tsx` - Narrative summary
- `src/components/SchedulePanel.tsx` - Timeline tab integration
- `src/components/ScheduleTimeline.tsx` - New timeline component
- `src/constants/simpleMode.ts` - TIMELINE tab constant

### Backend
- `backend/schedule_persistence.py` - v2.2 migration, lock normalization
- `backend/routers/schedule.py` - Lock endpoint updates, repair defaults
- `backend/incremental_planning.py` - Documentation updates

---

## Acceptance Criteria

✅ Mission planner cannot accidentally run non-repair planning in Simple Mode
✅ Only two lock states exist end-to-end (hard/none)
✅ Repair can fully rearrange unlocked schedule with clear narrative
✅ Schedule Timeline tab is usable and "mission planner grade"
