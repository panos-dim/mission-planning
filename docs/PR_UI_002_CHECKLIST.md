# PR UI-002: Remove Flexibility & Standardize Repair Defaults

**PR**: `chore/locks-remove-flexibility-and-standardize-repair-defaults`
**Date**: 2026-02-12

---

## 1. Removed Controls Inventory

| Control | Location | Type | Action |
|---------|----------|------|--------|
| Max Changes slider (1–200) | `MissionPlanning.tsx` → Repair Configuration section | `<input type="range">` | Removed |
| Optimization Objective dropdown (maximize_score / maximize_priority / minimize_changes) | `MissionPlanning.tsx` → Repair Configuration section | `<select>` | Removed |
| Lock Policy dropdown (Hard locks only / Hard + soft locks) | `MissionPlanning.tsx` → Schedule Context (incremental mode) | `<select>` | Replaced with static "Hard locks respected" indicator |
| `RepairSettingsPresets.tsx` component (presets + form) | `components/RepairSettingsPresets.tsx` | Entire file | Deleted |
| Barrel export of `RepairSettingsPresets`, `RepairSettingsForm`, `DEFAULT_SAFE_REPAIR_SETTINGS`, `RepairSettings` type | `components/repair/index.ts` | Re-exports | Removed |
| Soft lock stats display ("N soft") | `ScheduledAcquisitionsList.tsx` → Stats bar | `<span>` | Removed; stats now show "unlocked" / "locked" only |

### State variables removed

| Variable | File | Notes |
|----------|------|-------|
| `repairObjective` / `setRepairObjective` | `MissionPlanning.tsx` | Was `useState<RepairObjective>('maximize_score')` |
| `maxChanges` / `setMaxChanges` | `MissionPlanning.tsx` | Was `useState(100)` |
| `lockPolicy` / `setLockPolicy` | `MissionPlanning.tsx` | Was `useState<LockPolicy>('respect_hard_only')` — now lock policy is implicit |

### Types removed from frontend

| Type | File |
|------|------|
| `RepairScope` | `api/scheduleApi.ts` |
| `RepairObjective` | `api/scheduleApi.ts` |

### Fields removed from `RepairPlanRequest` interface

| Field | Previously sent | Now |
|-------|----------------|-----|
| `repair_scope` | `"workspace_horizon"` | Not sent (backend default: `"workspace_horizon"`) |
| `max_changes` | User-controlled (1–200) | Not sent (backend default: `100`) |
| `objective` | User-controlled dropdown | Not sent (backend default: `"maximize_score"`) |
| `satellite_subset` | Never sent from UI | Removed from interface |
| `target_subset` | Never sent from UI | Removed from interface |

---

## 2. Payload Contract Confirmation

### Repair request (`POST /api/v1/schedule/repair`)

Fields **now sent** by frontend:

```json
{
  "planning_mode": "repair",
  "workspace_id": "<string>",
  "include_tentative": false,
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_roll_accel_dps2": 10000.0,
  "max_pitch_rate_dps": 1.0,
  "max_pitch_accel_dps2": 10000.0,
  "look_window_s": 300,
  "value_source": "priority"
}
```

Fields **no longer sent**: `repair_scope`, `max_changes`, `objective`, `satellite_subset`, `target_subset`.

### Backend compatibility

The backend (`backend/routers/schedule.py`) defines defaults for all removed fields:
- `repair_scope`: `Field(default="workspace_horizon")`
- `max_changes`: `Field(default=100)`
- `objective`: `Field(default="maximize_score")`

**No backend changes required.** Omitting these fields triggers the Pydantic defaults.

---

## 3. Lock Model Confirmation

| Level | UI Label | Behavior |
|-------|----------|----------|
| `none` | Unlocked | Can be adjusted by repair |
| `hard` | Locked | Immutable, never touched by repair |

No third lock level (soft/flexible/intermediate) exists in the UI.

### Files verified clean of stale lock references

- `LockToggle.tsx` — description updated, comment cleaned
- `ScheduledAcquisitionsList.tsx` — stats bar shows "unlocked" / "locked" only
- `scheduleApi.ts` — `LockLevel = "none" | "hard"` (unchanged, already correct)
- `repair/index.ts` — barrel comment updated

---

## 4. Manual Test Checklist

| # | Scenario | Expected | Result |
|---|----------|----------|--------|
| 1 | Open planner → confirm no flexibility/advanced repair knobs exist | No Max Changes slider, no Objective dropdown, no Lock Policy dropdown with soft option | ⬜ |
| 2 | Lock a target/acquisition → Apply → confirm lock remains unchanged after apply | Hard-locked items stay locked in result | ⬜ |
| 3 | Apply without locks → confirm it still completes successfully | Repair completes, diff panel shows results | ⬜ |
| 4 | Inspect network request to confirm removed fields are not sent | Payload has no `max_changes`, `objective`, `repair_scope` | ⬜ |
| 5 | Check ScheduledAcquisitionsList stats bar shows only "unlocked" / "locked" | No "soft" count visible | ⬜ |
| 6 | Check LockToggle tooltip shows "Unlocked" / "Hard Lock" only | No "flexible" or "soft" language | ⬜ |

---

## 5. Files Changed Summary

| File | Change |
|------|--------|
| `frontend/src/components/MissionPlanning.tsx` | Removed flexibility state, repair config UI (slider+dropdown), lock policy dropdown, soft references |
| `frontend/src/api/scheduleApi.ts` | Removed `RepairScope`, `RepairObjective` types; removed flexibility fields from `RepairPlanRequest` |
| `frontend/src/components/LockToggle.tsx` | Cleaned soft/flexible wording in comments and descriptions |
| `frontend/src/components/ScheduledAcquisitionsList.tsx` | Removed soft lock stats; relabeled to "unlocked"/"locked" |
| `frontend/src/components/RepairSettingsPresets.tsx` | **Deleted** |
| `frontend/src/components/repair/index.ts` | Removed `RepairSettingsPresets` exports, updated comment |
