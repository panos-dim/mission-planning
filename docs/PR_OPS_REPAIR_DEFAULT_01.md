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
| Soft lock = yellow, modifiable by policy | Soft locks fully removed from codebase |
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

### E) Repair Full Flexibility — Soft Lock Removal

Complete removal of `SoftLockPolicy` enum and all soft lock logic:
- `SoftLockPolicy` enum removed from `incremental_planning.py`
- `soft_lock_policy` parameter removed from repair request model and all API endpoints
- All unlocked items (`lock_level: "none"`) are fully flexible (can be rearranged, replaced, or dropped)
- Only hard-locked items (`lock_level: "hard"`) are immutable
- Repair presets simplified to `max_changes` + `objective` only

**Backend Files Changed:**
- `backend/incremental_planning.py` — Removed `SoftLockPolicy` enum, `soft_lock_policy` from `RepairPlanningContext` and `load_repair_context`
- `backend/routers/schedule.py` — Removed `soft_lock_policy` from `RepairPlanRequestModel`, updated all lock_level comments/defaults/validation to `none | hard`
- `backend/schedule_persistence.py` — Changed default lock_level to `"none"`, migration normalizes `soft` → `none`
- `backend/policy_engine.py` — Removed `include_soft_lock_replace` from `SelectionRules`
- `backend/routers/batching.py` — Removed `include_soft_lock_replace`, default lock_level to `"none"`
- `backend/routers/workspaces.py` — Default lock_level to `"none"`
- `backend/validation/workflow_models.py` — Removed `repair_allow_shift`/`repair_allow_replace`
- `backend/validation/workflow_runner.py` — Default lock_level to `"none"`

**Frontend Files Changed:**
- `frontend/src/api/generated/api-types.ts` — Removed `soft_lock_policy`, `include_soft_lock_replace`
- `frontend/src/api/scheduleApi.ts` — Removed `SoftLockPolicy` type, `LockLevel = "none" | "hard"`
- `frontend/src/components/RepairSettingsPresets.tsx` — Removed `soft_lock_policy` from settings/presets
- `frontend/src/components/MissionPlanning.tsx` — Removed `softLockPolicy` state and dropdown
- `frontend/src/components/LockToggle.tsx` — Removed `soft` config entry
- `frontend/src/components/LeftSidebar.tsx` — Default `lock_level: "none"`
- `frontend/src/components/OrdersArea.tsx` — Default `lock_level: "none"`

**Config:**
- `config/batch_policies.yaml` — Removed `include_soft_lock_replace` from all policies

**Tests:**
- `tests/unit/test_incremental_planning.py` — Removed soft lock tests, updated defaults
- `tests/unit/test_lock_management.py` — Updated fixture and tests for none/hard only
- `scripts/test_repair_e2e_v2.py` — Removed soft_lock_policy params, removed freeze_soft test
- `scripts/test_api_sweep.py` — Removed soft_lock_policy from repair call

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
- `src/api/generated/api-types.ts` - Removed soft_lock_policy, include_soft_lock_replace types
- `src/api/scheduleApi.ts` - Removed SoftLockPolicy type, LockLevel = none|hard
- `src/components/MissionPlanning.tsx` - Repair-first defaults, removed softLockPolicy state/UI
- `src/components/RepairSettingsPresets.tsx` - Removed soft_lock_policy from presets/form
- `src/components/LockToggle.tsx` - Simplified to none/hard only
- `src/components/RepairDiffPanel.tsx` - Narrative summary
- `src/components/SchedulePanel.tsx` - Timeline tab integration
- `src/components/ScheduleTimeline.tsx` - New timeline component
- `src/components/LeftSidebar.tsx` - Default lock_level: none
- `src/components/OrdersArea.tsx` - Default lock_level: none
- `src/constants/simpleMode.ts` - TIMELINE tab constant

### Backend
- `backend/incremental_planning.py` - Removed SoftLockPolicy enum, simplified partitioning
- `backend/routers/schedule.py` - Lock endpoints, repair request model, defaults updated
- `backend/schedule_persistence.py` - v2.2 migration, lock normalization, default none
- `backend/policy_engine.py` - Removed include_soft_lock_replace
- `backend/routers/batching.py` - Removed soft lock fields, default lock_level none
- `backend/routers/workspaces.py` - Default lock_level none
- `backend/validation/workflow_models.py` - Removed repair_allow_shift/replace
- `backend/validation/workflow_runner.py` - Default lock_level none

### Config
- `config/batch_policies.yaml` - Removed include_soft_lock_replace from all policies

### Tests
- `tests/unit/test_incremental_planning.py` - Removed soft lock tests
- `tests/unit/test_lock_management.py` - Updated for none/hard only
- `scripts/test_repair_e2e_v2.py` - Removed soft_lock_policy, freeze_soft step
- `scripts/test_api_sweep.py` - Removed soft_lock_policy from repair call

---

## Acceptance Criteria

✅ Mission planner cannot accidentally run non-repair planning in Simple Mode
✅ Only two lock states exist end-to-end (hard/none) — soft locks fully removed
✅ Repair can fully rearrange unlocked schedule with clear narrative
✅ Schedule Timeline tab is usable and "mission planner grade"
✅ 120 unit tests pass (incremental planning + lock management + conflict + workspace)
✅ TypeScript typecheck clean (0 errors)
✅ E2E repair test: 35/35 passed with live API
