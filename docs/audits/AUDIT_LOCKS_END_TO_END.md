# AUDIT: Locks End-to-End

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

The system implements a **two-level lock model** (`none` | `hard`) with optimistic UI updates, backend persistence in SQLite, and toast feedback. The legacy `soft` level has been deprecated and is normalized to `none` on commit.

### Lock Levels Currently Present

| Level | Meaning | Where Defined |
| ----- | ------- | ------------- |
| `none` | Unlocked — fully flexible, can be rearranged by repair planner | `frontend/src/api/scheduleApi.ts:633` |
| `hard` | Immutable — never touched by repair planner | `frontend/src/api/scheduleApi.ts:633` |
| `soft` (deprecated) | Was "prefer to keep" — **normalized to `none`** on persist | `backend/schedule_persistence.py:825-831`, `backend/schedule_persistence.py:1652-1655` |

The TypeScript type is: `export type LockLevel = "none" | "hard";` (`scheduleApi.ts:633`).

The backend SQLite column is `lock_level TEXT DEFAULT 'none'` (`schedule_persistence.py:530`).

---

## 2. Where Each Lock Type Is Defined

### 2.1 Frontend Type Definitions

- **`LockLevel` type**: `frontend/src/api/scheduleApi.ts:633` — `"none" | "hard"`
- **`LockState` interface**: `frontend/src/store/lockStore.ts:25-32` — `levels: Map<string, LockLevel>`
- **`LOCK_CONFIG` visual config**: `frontend/src/components/LockToggle.tsx:15-39` — maps `none`→Unlock icon (gray), `hard`→Shield icon (red)
- **`ScheduledAcquisition.lock_level`**: `frontend/src/components/ScheduleTimeline.tsx:44` — `LockLevel` field on timeline cards
- **`AcquisitionSummary.lock_level`**: `frontend/src/api/scheduleApi.ts:68` — `string` in API response

### 2.2 Backend Definitions

- **DB column**: `backend/schedule_persistence.py:530` — `lock_level TEXT DEFAULT 'none'`
- **Acquisition dataclass**: `backend/schedule_persistence.py:197` — `lock_level: str  # none | hard`
- **Router model**: `backend/routers/schedule.py:42` — `lock_level: str = "none"  # none | hard`
- **Valid lock values**: `backend/schedule_persistence.py:1376-1379` — `["none", "hard"]`
- **Soft→none migration**: `backend/schedule_persistence.py:825-831` — `UPDATE acquisitions SET lock_level = 'none' WHERE lock_level = 'soft'`

---

## 3. Where Locking Actions Exist

### 3.1 UI Action Points

| Location | Component | Action | Lines |
| -------- | --------- | ------ | ----- |
| Timeline card | `ScheduleTimeline.tsx` | Per-card lock toggle icon | `660-679` |
| Acquisition list row | `ScheduledAcquisitionsList.tsx` | `LockToggle` widget + `LockBadge` | `400-439` |
| Repair diff panel | `RepairDiffPanel.tsx` | Per-row toggle + bulk "Lock Kept" / "Lock Kept+Moved" buttons | `1124-1163` |
| Schedule panel | `SchedulePanel.tsx` | Lock levels merged into timeline acquisitions | `48-82` |

### 3.2 Store Actions (Zustand)

| Action | Store | Description | Lines |
| ------ | ----- | ----------- | ----- |
| `toggleLock(id)` | `lockStore.ts` | Toggle `none`↔`hard` with optimistic update | `93-97` |
| `setLockLevel(id, level)` | `lockStore.ts` | Set specific level with optimistic update + rollback | `99-158` |
| `bulkSetLockLevel(ids, level)` | `lockStore.ts` | Bulk update with partial rollback on failure | `160-251` |
| `seedLevels(entries)` | `lockStore.ts` | Hydrate from backend data | `253-259` |

### 3.3 API Endpoints

| Endpoint | Method | Handler | Purpose |
| -------- | ------ | ------- | ------- |
| `/api/v1/schedule/acquisition/{id}/lock` | PUT | `schedule.py` | Single lock update |
| `/api/v1/schedule/acquisitions/bulk-lock` | POST | `schedule.py` | Bulk lock update |
| `/api/v1/schedule/acquisitions/hard-lock-committed` | POST | `schedule.py` | Hard-lock all committed in workspace |

### 3.4 Backend Persistence

| Method | File | Lines | Description |
| ------ | ---- | ----- | ----------- |
| `update_acquisition_lock_level()` | `schedule_persistence.py` | `2167-2181` | Single acquisition lock update |
| `bulk_update_lock_levels()` | `schedule_persistence.py` | `2183-2228` | Batch lock update |
| `update_acquisition_state()` | `schedule_persistence.py` | `1350-1382` | General state+lock update |

---

## 4. Where "Flexibility" Is Implemented

The repair planner uses locks to partition acquisitions into **fixed** (hard-locked, untouchable) and **flex** (unlocked, can be changed) sets.

| Concept | File | Lines | Description |
| ------- | ---- | ----- | ----------- |
| `repair_scope` | `backend/routers/schedule.py` | `1603-1609` | Scope enum: workspace_horizon, satellite_subset, target_subset |
| `max_changes` | `backend/routers/schedule.py` | `1611` | Cap on disruption (default: 100) |
| `objective` | `backend/routers/schedule.py` | `1612-1614` | maximize_score, maximize_priority, minimize_changes |
| `RepairPlanningContext` | `backend/incremental_planning.py` | `~288-296` | Context with repair_scope + objective + max_changes |
| Fixed/flex partition | `backend/incremental_planning.py` | `~1165-1226` | Partitions acquisitions: hard-locked → fixed, rest → flex |
| Flex drop logic | `backend/incremental_planning.py` | `~1379-1382` | Respects max_changes cap |
| Frontend repair config | `frontend/src/components/MissionPlanning.tsx` | `87-97` | `planningMode`, `repairObjective`, `maxChanges` state |
| Repair settings UI | `frontend/src/components/RepairSettingsPresets.tsx` | whole file | Preset buttons for repair objective/scope |
| `RepairPlanRequest` | `frontend/src/api/scheduleApi.ts` | `477-498` | Request shape with repair_scope, max_changes, objective |

### Review Team Directive: "Remove flexibility feature completely"

This means:
- Remove `repair_scope`, `max_changes`, `objective` from repair request UI
- Simplify repair to always operate on full workspace horizon with no change cap
- Remove `RepairSettingsPresets.tsx` component
- Simplify `MissionPlanning.tsx` state (lines 87-97)

---

## 5. What Would Need to Change for "Map Lock Mode" UX

The review team wants a **"lock on map" mode toggle** where the user activates a mode, then clicks targets/opportunities on the Cesium globe to lock them.

### Required State Machine

```
┌─────────────┐   toggle    ┌──────────────┐
│  NORMAL     │ ──────────> │  LOCK_MODE   │
│  (default)  │ <────────── │  (map click  │
│             │   toggle    │   = lock)    │
└─────────────┘             └──────────────┘
```

### Implementation Points

1. **New store field**: Add `mapLockMode: boolean` to `lockStore.ts` or `visStore.ts`
2. **Toggle button**: Add toolbar button near map controls (similar to existing `targetAddStore.ts` "add target on map" mode)
3. **Click handler**: In `CesiumViewer.tsx` or `ObjectMapViewer.tsx`, detect entity clicks when `mapLockMode` is active, resolve to acquisition ID, call `toggleLock(id)`
4. **Visual feedback**: Change cursor to lock icon when mode is active; show lock overlay on map entities
5. **Pattern exists**: `targetAddStore.ts` already implements a similar "click on map to add" mode pattern — can be replicated

### Analogous Pattern

`frontend/src/store/targetAddStore.ts` provides `isAddMode` / `toggleAddMode` / `disableAddMode` — the same pattern can be used for map lock mode.

---

## 6. Backend Persistence Tables/Fields

### `acquisitions` Table Schema (relevant columns)

```sql
CREATE TABLE IF NOT EXISTS acquisitions (
    id TEXT PRIMARY KEY,
    ...
    state TEXT NOT NULL DEFAULT 'tentative',
    lock_level TEXT DEFAULT 'none',
    ...
);
```

- `state` values: `tentative | locked | committed | executing | completed | failed`
- `lock_level` values: `none | hard`
- Soft→none normalization: `schedule_persistence.py:825-831` runs on DB init

---

## 7. Risks / Inconsistencies

1. **`state` vs `lock_level` confusion**: The `state` field has a value `"locked"` that is separate from `lock_level = "hard"`. These are semantically different but visually confusing. The `state="locked"` means "frozen in schedule" while `lock_level="hard"` means "immutable to repair planner".
2. **Soft lock vestige**: Migration code (`schedule_persistence.py:825-831`) still runs `UPDATE ... SET lock_level = 'none' WHERE lock_level = 'soft'` on every DB init. Can be removed once confirmed no soft locks exist.
3. **`ScheduledAcquisitionsList.tsx` has its own lock handler** (`handleLockChange` at line 160) that calls `updateAcquisitionLock` directly, bypassing the `lockStore`. This creates two code paths for lock updates — one through the store (optimistic) and one direct.
4. **No "map lock mode"** exists. The closest pattern is `targetAddStore` for click-to-add targets.

---

## 8. Recommended Minimal Change Strategy

1. **Keep the two-level model as-is** (`none`/`hard`) — it already matches the review team's "two lock levels only" requirement. Remove the `soft` migration code.
2. **Remove flexibility knobs** from repair UI: hide `repair_scope`, `max_changes`, `objective` controls; hard-code sensible defaults in the backend request.
3. **Add map lock mode** by cloning `targetAddStore` pattern: new `mapLockModeStore`, toolbar toggle, Cesium click handler that resolves entity → acquisition ID → `toggleLock()`.
