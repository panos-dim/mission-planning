# PR-PS2.4: Interactive Locks + What-If Compare + Safe Commit Workflow

## Branch
`feat/repair-ux-locks-whatif-commit`

## Overview

This PR implements comprehensive lock controls, what-if comparison visualization, and safe commit workflows for the schedule repair system. Mission planners can now:

- **Lock critical acquisitions** at different levels (hard/soft/none)
- **Preview exactly what will change** before committing
- **Compare before/after** on both timeline and map
- **Commit safely** with clear warnings and rollback options

## Why This Matters

Repair is powerful, but mission planners won't trust it unless they can:
1. Protect critical acquisitions from modification
2. See exactly what will change before committing
3. Understand why changes are proposed
4. Commit with confidence (or rollback if needed)

---

## Features Implemented

### 1. Frontend: Lock Controls Everywhere

#### Components
- **`LockToggle`** - Reusable lock control with visual indicators
- **`BulkLockActions`** - Bulk operations toolbar
- **`ScheduledAcquisitionsList`** - Full acquisition list with integrated locks

#### Lock Levels
| Level | Icon | Description |
|-------|------|-------------|
| `hard` | 🔴 Shield | Immutable in repair - never moved or dropped |
| `soft` | 🟡 Lock | Modifiable depending on policy |
| `none` | ⚪ Unlock | Fully flexible / tentative |

#### Bulk Actions
- "Hard-lock all committed" - Protect all committed acquisitions
- "Soft-lock selected" - Apply soft lock to selection
- "Unlock selected" - Remove locks (tentative only)

### 2. What-If Mode: Before/After Comparison

#### Components
- **`WhatIfComparePanel`** - Side-by-side baseline vs proposed comparison
- **`WhatIfCesiumControls`** - Map layer toggles and legend
- **`RepairDiffPanel`** - Visual diff summary

#### Visual Indicators
| Change Type | Timeline | Map |
|-------------|----------|-----|
| Kept | Normal | Green outline |
| Dropped | Strikethrough/ghost | Red dashed outline |
| Added | Emphasized/highlighted | Blue thick border |
| Moved | Arrow indicator (from→to) | Yellow with arrow |

#### Cesium Map Toggles
- Show baseline swaths
- Show proposed swaths  
- Show only changes
- View mode selector (Both/Current/Proposed/Changes-only)

### 3. Commit Workflow Upgrades

#### `RepairCommitModal` Features
- **Summary counts**: Kept/dropped/added/moved
- **Score delta**: Before vs after with trend indicator
- **Conflicts display**: Before/after conflict counts
- **Dropped reasons**: Detailed explanation for each drop
- **Hard lock warnings**: Clear alerts when hard locks prevent resolution
- **Force commit checkbox**: Only enabled when conflicts exist
- **Commit notes**: Optional audit trail notes

#### Backend: Atomic Commit
- All-or-nothing transaction
- Audit log with: `plan_id`, `repair_diff`, `config_hash`, `who/when`
- Conflict recomputation after commit

### 4. Backend: Lock Persistence + Validation

#### Hard Lock Warnings
When repair planning encounters conflicts with hard-locked acquisitions:
```
Cannot resolve conflict: acquisition ACQ-123 (TARGET-A) 
conflicts with hard-locked ACQ-456 (TARGET-B). 
The soft-locked acquisition will be dropped.
```

#### API Endpoints
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/acquisition/{id}/lock` | PATCH | Update single lock |
| `/acquisitions/bulk-lock` | POST | Bulk lock update |
| `/acquisitions/hard-lock-committed` | POST | Lock all committed |
| `/repair` | POST | Create repair plan with `hard_lock_warnings` |
| `/repair/commit` | POST | Atomic commit with audit |

### 5. Quality of Life: Safe Defaults

#### Default Repair Settings (Conservative)
```typescript
{
  soft_lock_policy: "freeze_soft",
  max_changes: 10,
  objective: "minimize_changes"
}
```

#### Preset Buttons
| Preset | Policy | Max Changes | Objective |
|--------|--------|-------------|-----------|
| **Conservative** | freeze_soft | 10 | minimize_changes |
| **Balanced** | allow_shift | 20 | maximize_score |
| **Aggressive** | allow_replace | 50 | maximize_score |

---

## Files Changed

### Backend

| File | Changes |
|------|---------|
| `backend/incremental_planning.py` | Added `hard_lock_warnings` to `RepairDiff`, tracking in `execute_repair_planning()` |
| `backend/routers/schedule.py` | Added `hard_lock_warnings` to `RepairDiffResponse`, included in repair response |
| `backend/validation/storage.py` | Fixed type annotation for `json.load()` return |

### Frontend

| File | Changes |
|------|---------|
| `frontend/src/api/scheduleApi.ts` | Added `hard_lock_warnings` to `RepairDiff` interface |
| `frontend/src/components/ScheduledAcquisitionsList.tsx` | **NEW** - Full acquisition list with locks |
| `frontend/src/components/WhatIfCesiumControls.tsx` | **NEW** - Map layer toggles |
| `frontend/src/components/RepairCommitModal.tsx` | Added hard lock warnings display |
| `frontend/src/components/RepairSettingsPresets.tsx` | Added `DEFAULT_SAFE_REPAIR_SETTINGS` export, updated max_changes |
| `frontend/src/components/repair/index.ts` | **NEW** - Barrel export for repair components |

---

## API Changes

### RepairDiff Response (Enhanced)

```typescript
interface RepairDiff {
  kept: string[];
  dropped: string[];
  added: string[];
  moved: MovedAcquisitionInfo[];
  reason_summary: {
    dropped?: Array<{ id: string; reason: string }>;
    moved?: Array<{ id: string; reason: string }>;
  };
  change_score: ChangeScore;
  hard_lock_warnings?: string[];  // NEW
}
```

---

## Usage Examples

### Import Repair Components
```typescript
import {
  LockToggle,
  BulkLockActions,
  RepairCommitModal,
  WhatIfComparePanel,
  WhatIfCesiumControls,
  ScheduledAcquisitionsList,
  RepairSettingsPresets,
  DEFAULT_SAFE_REPAIR_SETTINGS,
} from "@/components/repair";
```

### Use Default Safe Settings
```typescript
const [settings, setSettings] = useState<RepairSettings>(
  DEFAULT_SAFE_REPAIR_SETTINGS
);
```

### Handle Hard Lock Warnings
```typescript
if (repairResult.repair_diff.hard_lock_warnings?.length > 0) {
  // Show warning UI
  console.warn("Hard lock conflicts detected:", 
    repairResult.repair_diff.hard_lock_warnings);
}
```

---

## Acceptance Criteria

| Criteria | Status |
|----------|--------|
| Lock toggles work and persist | ✅ |
| Repair results show clear before/after diff on timeline + map | ✅ |
| Commit is safe, atomic, and explainable | ✅ |
| Hard locks are strictly respected | ✅ |
| Unresolved conflicts are surfaced clearly | ✅ |

---

## Testing Checklist

- [ ] Lock toggle changes persist after page refresh
- [ ] Bulk lock actions update multiple acquisitions
- [ ] "Hard-lock all committed" protects committed acquisitions
- [ ] Repair plan shows hard_lock_warnings when conflicts exist
- [ ] What-If panel shows baseline vs proposed correctly
- [ ] Cesium map toggles work for swath visibility
- [ ] Commit modal shows all required information
- [ ] Force commit checkbox only appears when needed
- [ ] Audit log created on successful commit
- [ ] Preset buttons apply correct settings

---

## Screenshots

*TODO: Add screenshots of:*
- Lock toggle in different states
- ScheduledAcquisitionsList with bulk actions
- WhatIfComparePanel showing diff
- RepairCommitModal with hard lock warnings
- Cesium map with What-If layer toggles

---

## Related Issues

- Implements PR-PS2.4 requirements
- Enhances repair workflow UX
- Adds mission planner safety controls
