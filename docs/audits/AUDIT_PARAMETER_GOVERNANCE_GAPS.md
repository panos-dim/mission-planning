# AUDIT: Parameter Governance Gaps

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

Mission planning inputs are currently split between the **MissionControls** panel (feasibility/analysis inputs) and the **MissionPlanning** panel (scheduling/planning inputs). Some parameters that should be immutable platform truth (admin-managed) are exposed to the planner. The review team directive is: **"no inputs required for mission planner"** — move parameters to admin/config.

---

## 2. All Mission Planning Inputs Currently Exposed to Planner

### 2.1 Feasibility Analysis Inputs (MissionControls.tsx)

| Parameter | Current Location | Default | Categorization |
| --------- | ---------------- | ------- | -------------- |
| Targets (name, lat, lon, priority, color) | `MissionControls.tsx:374-388` / `TargetInput.tsx` | Empty list | **Should remain** in feasibility input |
| Start Time (UTC) | `MissionParameters.tsx:198-203` | Now | **Should remain** in feasibility input |
| End Time (UTC) | `MissionParameters.tsx:207-213` | Now + 24h | **Should remain** in feasibility input |
| Imaging Type (optical/SAR) | `MissionParameters.tsx:165-195` | `optical` | **Should be per-satellite config** (sensor type is platform truth) |
| Max Pointing Angle (degrees) | `MissionParameters.tsx:376-417` | `45°` | **Should be admin/config** — this is `max_spacecraft_roll_deg`, a bus limit |
| SAR Imaging Mode (spot/strip/scan/dwell) | `MissionParameters.tsx:229-249` | `strip` | **Should be per-satellite config** (sensor capability) |
| SAR Look Side (LEFT/RIGHT/ANY) | `MissionParameters.tsx:252-277` | `ANY` | **Should remain** in feasibility input (tasking choice) |
| SAR Pass Direction (ASC/DESC/ANY) | `MissionParameters.tsx:280-309` | `ANY` | **Should remain** in feasibility input (tasking choice) |
| SAR Incidence Angle Range | `MissionParameters.tsx:326-369` | Mode-dependent | **Should be per-satellite config** (sensor spec) with planner override |
| Satellite Selection | `MissionControls.tsx:342-372` | From Admin Panel | **Already admin-managed** — read-only display |

### 2.2 Planning/Scheduling Inputs (MissionPlanning.tsx)

| Parameter | Current Location | Default | Categorization |
| --------- | ---------------- | ------- | -------------- |
| `imaging_time_s` | `MissionPlanning.tsx:176` | `1.0` | **Should be admin/config** — platform dwell time |
| `max_roll_rate_dps` | `MissionPlanning.tsx:177` | `1.0` | **Should be admin/config** — bus agility spec |
| `max_roll_accel_dps2` | `MissionPlanning.tsx:178` | `10000.0` | **Should be admin/config** — bus spec |
| `max_pitch_rate_dps` | `MissionPlanning.tsx:179` | `1.0` | **Should be admin/config** — bus spec |
| `max_pitch_accel_dps2` | `MissionPlanning.tsx:180` | `10000.0` | **Should be admin/config** — bus spec |
| `algorithms` | `MissionPlanning.tsx:181` | `["roll_pitch_best_fit"]` | **Should be admin/config** — only one algorithm in use |
| `value_source` | `MissionPlanning.tsx:182` | `"target_priority"` | **Should be admin/config** — operational default |
| `look_window_s` | `MissionPlanning.tsx:183` | `600.0` | **Should be admin/config** — algorithm tuning parameter |
| `quality_model` | `MissionPlanning.tsx:185` | `"monotonic"` | **Should be admin/config** — depends on sensor type |
| `ideal_incidence_deg` | `MissionPlanning.tsx:186` | `35.0` | **Should be per-satellite config** — SAR sensor spec |
| `band_width_deg` | `MissionPlanning.tsx:187` | `7.5` | **Should be per-satellite config** — SAR quality band |
| `weight_priority` | `MissionPlanning.tsx:189` | `40` | Could remain as planner input OR move to config preset |
| `weight_geometry` | `MissionPlanning.tsx:190` | `40` | Could remain as planner input OR move to config preset |
| `weight_timing` | `MissionPlanning.tsx:191` | `20` | Could remain as planner input OR move to config preset |
| `weight_preset` | `MissionPlanning.tsx:192` | `"balanced"` | Could remain as planner input |
| Planning Mode (repair/from_scratch) | `MissionPlanning.tsx:87` | `"repair"` | **Should be admin/config** — always repair in ops |
| Lock Policy | `MissionPlanning.tsx:88` | `"respect_hard_only"` | **Should be admin/config** — operational invariant |
| Repair Scope | `MissionPlanning.tsx:92-93` | `"maximize_score"` | **Remove** — flexibility feature being removed |
| Max Changes | `MissionPlanning.tsx:94` | `100` | **Remove** — flexibility feature being removed |

### 2.3 Already Admin-Managed (Config)

These are correctly in admin/config already:

| Parameter | Location | Notes |
| --------- | -------- | ----- |
| Satellite TLE data | `config/` YAML + Admin Panel | Correct |
| Ground station list | `config/ground_stations.yaml` | Correct |
| SAR mode specs | `config/sar_modes.yaml` | Correct |
| Batch policies | `config/batch_policies.yaml` | Correct |
| Mission settings | `config/mission_settings.yaml` | Correct |

---

## 3. "Look Window" Usage

The `look_window_s` parameter controls the candidate evaluation window for the Best-Fit algorithm — how far ahead (in seconds) the scheduler looks when picking the next opportunity.

### Where It Exists

| Location | File | Lines | Usage |
| -------- | ---- | ----- | ----- |
| Frontend default | `MissionPlanning.tsx` | `183` | `look_window_s: 600.0` |
| Frontend type | `types/index.ts` | `576` | `look_window_s: number` in `PlanningRequest` |
| Frontend config type | `types/index.ts` | `598` | `look_window_s: number` in `PlanningConfig` |
| API request | `scheduleApi.ts` | `368` | `look_window_s?: number` in `IncrementalPlanRequest` |
| Repair request | `scheduleApi.ts` | `496` | `look_window_s?: number` in `RepairPlanRequest` |
| Backend schema | `backend/schemas/planning.py` | `50-52` | `look_window_s: float = 600.0` |
| Scheduler config | `src/mission_planner/scheduler.py` | `304` | `look_window_s: float = 600.0` |
| Backend router | `backend/routers/schedule.py` | various | Passed through to planner |
| Generated API types | `frontend/src/api/generated/api-types.ts` | various | Mirror of backend schema |
| Feature component | `frontend/src/components/features/mission-planning/PlanningParameters.tsx` | various | UI control |

### Review Team Directive: "Remove look window eventually"

The parameter is an algorithm tuning knob that should be hidden from planners. To remove:
1. Move to `config/mission_settings.yaml` with a sensible default (600s)
2. Remove from frontend `PlanningRequest` type or make it optional with server-side default
3. Remove UI control from `MissionPlanning.tsx` and `PlanningParameters.tsx`
4. Keep in backend schema as optional with default for backward compatibility

---

## 4. "Max Satellite Agility" — What It Actually Represents

### Current Implementation

The parameter labeled "Max Pointing Angle" / "Max Satellite Agility" / `max_spacecraft_roll_deg` represents the **maximum off-nadir roll angle** the satellite bus can physically achieve. It is NOT the sensor field of view.

| Name in Code | Actual Meaning | File | Lines |
| ------------ | -------------- | ---- | ----- |
| `max_spacecraft_roll_deg` | Bus mechanical limit for cross-track tilt | `src/mission_planner/scheduler.py` | `290-291` |
| `pointingAngle` (frontend) | Same — mapped to `max_spacecraft_roll_deg` | `frontend/src/types/index.ts` | `94` |
| `Max Pointing Angle` (UI label) | Same — shown in MissionParameters | `MissionParameters.tsx` | `379` |
| `Satellite limit: {x}°` (UI hint) | Shows bus limit from config | `MissionParameters.tsx` | `382-383` |
| `max_roll_rate_dps` | How fast the satellite can roll (deg/s) | `scheduler.py` | `293` |
| `sensor_fov_half_angle_deg` | Sensor FOV — separate concept | `scheduler.py` | `288` (comment) |

### Review Team Request: "Rename to Max Off-nadir Angle"

The rename is straightforward:
- Change UI label `"Max Pointing Angle"` → `"Max Off-nadir Angle"` in `MissionParameters.tsx:379`
- Change tooltip text in `MissionParameters.tsx:412-415`
- The backend field name `max_spacecraft_roll_deg` is already descriptive; no API rename needed
- The frontend type field `pointingAngle` in `FormData` (`types/index.ts:454`) should eventually be renamed to `maxOffNadirAngle` but can be deferred

---

## 5. Categorized Summary

### Should Be Admin/Config (satellite-independent)

- `imaging_time_s`, `max_roll_rate_dps`, `max_roll_accel_dps2`, `max_pitch_rate_dps`, `max_pitch_accel_dps2`
- `algorithms`, `value_source`, `look_window_s`, `quality_model`
- `planning_mode`, `lock_policy`

### Should Be Per-Satellite Config

- `max_spacecraft_roll_deg` (bus limit per satellite)
- `imaging_type` (optical vs SAR — sensor type)
- `ideal_incidence_deg`, `band_width_deg` (SAR sensor specs)
- SAR imaging mode defaults (spot/strip/scan/dwell)

### Should Remain in Feasibility Input

- Targets (name, lat, lon, priority, color)
- Start/End time window
- SAR look side (LEFT/RIGHT/ANY) — tasking choice
- SAR pass direction (ASC/DESC/ANY) — tasking choice
- Weight presets (balanced/priority_first/quality_first/urgent/archival)

### Should Be Removed Entirely

- `repair_scope`, `max_changes`, `objective` (flexibility feature)
- `look_window_s` from UI (move to backend config)
- Algorithm selector (only one algorithm in use)

---

## 6. Risks / Inconsistencies

1. **Planner can override bus limits**: The `pointingAngle` slider allows setting a value up to the satellite's max roll. If the goal is "no inputs required", this slider should be hidden and the value should come from satellite config.
2. **Imaging type exposed as planner choice**: Whether a satellite is optical or SAR is a hardware fact, not a per-mission choice. It should be locked based on the selected satellite's sensor type.
3. **Look window hidden behind "Advanced" accordion** but still accessible: `COLLAPSED_BY_DEFAULT.planningAdvanced = true` (`simpleMode.ts:98`) hides it, but it's expandable.
4. **Config summary already fetched**: `MissionPlanning.tsx:156-171` fetches `/api/v1/config/satellite-config-summary` which includes bus specs per satellite. This data is available to auto-populate platform truth fields.

---

## 7. File References

| File | Lines | Purpose |
| ---- | ----- | ------- |
| `frontend/src/components/MissionControls.tsx` | 44-489 | Analysis form with target input + parameters |
| `frontend/src/components/MissionParameters.tsx` | 1-488 | Imaging type, time, pointing angle, SAR params |
| `frontend/src/components/MissionPlanning.tsx` | 100-350 | Planning config state (all scheduler params) |
| `frontend/src/types/index.ts` | 563-601 | `PlanningRequest` and `PlanningConfig` types |
| `backend/schemas/planning.py` | 1-105 | Backend planning request schema |
| `src/mission_planner/scheduler.py` | 280-333 | `SchedulerConfig` dataclass with all planner params |
| `config/mission_settings.yaml` | whole file | Global config (could host moved parameters) |
| `config/sar_modes.yaml` | whole file | SAR mode specifications |
| `frontend/src/constants/simpleMode.ts` | 97-102 | Collapsed sections config |

---

## 8. Recommended Minimal Change Strategy

1. **Move bus/sensor params to config**: Read `imaging_time_s`, `max_roll_rate_dps`, `max_roll_accel_dps2` etc. from satellite config summary (already fetched at `MissionPlanning.tsx:156-171`). Remove corresponding UI controls. Pass as server-side defaults.
2. **Remove flexibility knobs**: Delete `repair_scope`, `max_changes`, `objective` state and UI from `MissionPlanning.tsx:87-97`. Hard-code `repair` mode with `maximize_score` objective and no change cap.
3. **Hide look_window_s**: Move to `config/mission_settings.yaml`, remove from frontend `PlanningRequest`, let backend use config default.
