# PR_UI_008 — Remove Mission-Planning Tuning Inputs from Planner UI

**Goal:** Hide/remove all planner-facing "planning knobs" so operators only do:
select targets → run feasibility → lock → apply. Runtime uses backend/config defaults
(Pydantic schema defaults). No algorithm changes.

---

## 1. Inventory of Removed Tuning Inputs

### A) Agility Parameters

| UI Label | State Key | Request Field | Backend Default Source | Action |
|----------|-----------|---------------|----------------------|--------|
| Imaging Time (τ) | `config.imaging_time_s` | `imaging_time_s` | `backend/schemas/planning.py:22` → `5.0`; `config/mission_settings.yaml:80` → `5.0` | **Removed from UI, omitted from requests** |
| Roll Rate | `config.max_roll_rate_dps` | `max_roll_rate_dps` | `backend/schemas/planning.py:23` → `1.0`; `config/mission_settings.yaml:81` → `3.0` | **Removed from UI, omitted from requests** |
| Roll Acceleration | `config.max_roll_accel_dps2` | `max_roll_accel_dps2` | `backend/schemas/planning.py:24` → `10000.0`; `config/mission_settings.yaml:82` → `1.0` | **Removed from UI, omitted from requests** |
| Pitch Rate | `config.max_pitch_rate_dps` | `max_pitch_rate_dps` | `backend/schemas/planning.py:29` → `1.0`; `config/mission_settings.yaml:83` → `0.0` | **Removed from UI, omitted from requests** |
| Pitch Acceleration | `config.max_pitch_accel_dps2` | `max_pitch_accel_dps2` | `backend/schemas/planning.py:30` → `10000.0`; `config/mission_settings.yaml:84` → `0.0` | **Removed from UI, omitted from requests** |

### B) Scoring / Quality Parameters

| UI Label | State Key | Request Field | Backend Default Source | Action |
|----------|-----------|---------------|----------------------|--------|
| Target Value Source | `config.value_source` | `value_source` | `backend/schemas/planning.py:41` → `"uniform"`; `config/mission_settings.yaml:91` → `uniform` | **Removed from UI, omitted from requests** |
| Quality Model | `config.quality_model` | `quality_model` | `backend/schemas/planning.py:55` → `"monotonic"` | **Removed from UI, omitted from requests** |
| Ideal Off-Nadir (°) | `config.ideal_incidence_deg` | `ideal_incidence_deg` | `backend/schemas/planning.py:58` → `35.0` | **Removed from UI, omitted from requests** |
| Band Width (°) | `config.band_width_deg` | `band_width_deg` | `backend/schemas/planning.py:61` → `7.5` | **Removed from UI, omitted from requests** |

### C) Multi-Criteria Weight Parameters — KEPT (planner-facing)

| UI Label | State Key | Request Field | Backend Default Source | Action |
|----------|-----------|---------------|----------------------|--------|
| Weight Priority | `weightConfig.weight_priority` | `weight_priority` | `backend/schemas/planning.py:66` → `40.0` | **Kept** — sent via preset selection |
| Weight Geometry | `weightConfig.weight_geometry` | `weight_geometry` | `backend/schemas/planning.py:69` → `40.0` | **Kept** — sent via preset selection |
| Weight Timing | `weightConfig.weight_timing` | `weight_timing` | `backend/schemas/planning.py:72` → `20.0` | **Kept** — sent via preset selection |
| Scoring Strategy Presets | `weightConfig.weight_preset` | `weight_preset` | `backend/schemas/planning.py:75` → `None` | **Kept** — planner selects preset (Balanced/Priority/Quality/Urgent/Archival) |

> **Note:** Fine-tune weight sliders were removed. Planners select from presets only.

### D) Previously Removed (PR_UI_007)

| UI Label | State Key | Request Field | Backend Default Source | Action |
|----------|-----------|---------------|----------------------|--------|
| Look Window | `config.look_window_s` | `look_window_s` | `backend/schemas/planning.py:50` → `600.0` | Already removed in PR_UI_007 |

---

## 2. What Remains in Planner UI (Operator Essentials)

| Element | Purpose | Location |
|---------|---------|----------|
| Scoring Strategy Presets (Balanced/Priority/Quality/Urgent/Archival) | Select scoring emphasis + weight visualization bar | Always visible |
| Planning Mode toggle (from_scratch / incremental / repair) | Select planning approach | Developer-mode only (`showAdvancedOptions` gate) |
| Schedule Context panel | Show existing acquisitions before planning | Incremental/repair modes |
| Include Tentative toggle | Include tentative acquisitions in context | Incremental/repair modes |
| Platform Config (read-only) | Show satellite bus/sensor config from backend | Always visible when data available |
| ▶ Repair Schedule button | Run planning | Always visible |
| Apply button | Commit plan to schedule | Shown after results |
| Results table + export | View and export schedule | Shown after results |

---

## 3. Frontend Files Changed

| File | Change |
|------|--------|
| `frontend/src/components/MissionPlanning.tsx` | Removed: `WEIGHT_PRESETS` constant, `applyPreset()`, `getNormalizedWeights()`, `config` state (all tuning params), `setConfig`, `showAdvancedPlanning` state. Removed entire "Scoring Strategy" section, "Advanced Parameters" accordion, all input controls (imaging time, value source, quality model, band params, weight sliders, spacecraft agility). Kept: planning mode (dev-only), config summary (read-only), action buttons, results. Updated repair request and standard planning request to omit all tuning fields. Removed unused imports (`Settings`, `ChevronDown`, `ChevronUp`, `COLLAPSED_BY_DEFAULT`). |
| `frontend/src/types/index.ts` | Made all tuning fields optional in `PlanningRequest`: `imaging_time_s?`, `max_roll_rate_dps?`, `max_roll_accel_dps2?`, `max_pitch_rate_dps?`, `max_pitch_accel_dps2?`, `value_source?`, `quality_model?`, `ideal_incidence_deg?`, `band_width_deg?`, `weight_priority?`, `weight_geometry?`, `weight_timing?`. Only `algorithms` remains required. |
| `frontend/src/components/features/mission-planning/usePlanningState.ts` | Simplified `DEFAULT_CONFIG` to only `{ algorithms, weight_preset }`. Simplified `runPlanning` to send only `{ algorithms }`. Fixed `getNormalizedWeights` for optional weight fields. |

### Files NOT Changed (backend defaults confirmed stable)

| File | Reference | Default Value | Status |
|------|-----------|---------------|--------|
| `backend/schemas/planning.py` | `PlanningRequest` Pydantic model | All `Field(default=...)` values | **Kept** — canonical Pydantic defaults |
| `backend/routers/schedule.py` | Incremental/repair request schemas | `Field(default=...)` for all params | **Kept** — Pydantic defaults apply when FE omits |
| `config/mission_settings.yaml` | `mission_planning.agility_constraints.*` | See inventory table above | **Kept** — config source of truth |
| `src/mission_planner/scheduler.py` | `SchedulerConfig` dataclass | Algorithm-level defaults | **Kept** — no changes |

### Dead Code (not imported, out of scope)

| File | Notes |
|------|-------|
| `frontend/src/components/features/mission-planning/PlanningParameters.tsx` | Exported from barrel but never imported by consuming components |
| `frontend/src/components/features/mission-planning/WeightConfiguration.tsx` | Exported from barrel but never imported by consuming components |
| `frontend/src/components/features/mission-planning/AlgorithmSelector.tsx` | Exported from barrel but never imported by consuming components |

---

## 4. Payload Diffs

### Before (PR_UI_007 state — standard planning request)

```json
{
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_roll_accel_dps2": 10000.0,
  "max_pitch_rate_dps": 1.0,
  "max_pitch_accel_dps2": 10000.0,
  "algorithms": ["roll_pitch_best_fit"],
  "value_source": "target_priority",
  "quality_model": "monotonic",
  "ideal_incidence_deg": 35.0,
  "band_width_deg": 7.5,
  "weight_priority": 40,
  "weight_geometry": 40,
  "weight_timing": 20,
  "weight_preset": "balanced",
  "mode": "repair",
  "workspace_id": "default"
}
```

### After (PR_UI_008 — standard planning request)

```json
{
  "algorithms": ["roll_pitch_best_fit"],
  "mode": "repair",
  "workspace_id": "default",
  "weight_priority": 40,
  "weight_geometry": 40,
  "weight_timing": 20,
  "weight_preset": "balanced"
}
```

### Before (repair request)

```json
{
  "planning_mode": "repair",
  "workspace_id": "default",
  "include_tentative": false,
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_roll_accel_dps2": 10000.0,
  "max_pitch_rate_dps": 1.0,
  "max_pitch_accel_dps2": 10000.0,
  "value_source": "target_priority"
}
```

### After (PR_UI_008 — repair request)

```json
{
  "planning_mode": "repair",
  "workspace_id": "default",
  "include_tentative": false,
  "weight_priority": 40,
  "weight_geometry": 40,
  "weight_timing": 20,
  "weight_preset": "balanced"
}
```

### Fields Omitted (9 removed, 4 kept via scoring presets)

| Field | Backend Pydantic Default |
|-------|------------------------|
| `imaging_time_s` | `5.0` |
| `max_roll_rate_dps` | `1.0` |
| `max_roll_accel_dps2` | `10000.0` |
| `max_pitch_rate_dps` | `1.0` |
| `max_pitch_accel_dps2` | `10000.0` |
| `value_source` | `"uniform"` |
| `quality_model` | `"monotonic"` |
| `ideal_incidence_deg` | `35.0` |
| `band_width_deg` | `7.5` |
| `weight_priority` | **KEPT** — sent from preset |
| `weight_geometry` | **KEPT** — sent from preset |
| `weight_timing` | **KEPT** — sent from preset |
| `weight_preset` | **KEPT** — sent from preset |

---

## 5. Backward Compatibility

- **FE request DTOs** (`IncrementalPlanRequest`, `RepairPlanRequest` in `scheduleApi.ts`) retain
  all tuning fields as **optional**. Older clients or scripts that still send them will have them
  accepted and used by the backend — no breaking change.
- **Backend schemas** still define all fields with `Field(default=...)`. If a field is present in
  a request, it is used. If absent, the Pydantic default applies.
- **No backend field removal** in this PR.

---

## 6. Manual Verification Steps

- [ ] **V1:** Run feasibility from UI → confirm it works
- [ ] **V2:** Run repair/apply flow from UI → confirm it works
- [ ] **V3:** Confirm (browser DevTools → Network tab) standard planning request payload contains only `algorithms`, `mode`, `workspace_id`
- [ ] **V4:** Confirm repair request payload contains only `planning_mode`, `workspace_id`, `include_tentative`
- [ ] **V5:** Confirm no tuning controls visible in Planning panel (no sliders, no inputs, no presets)
- [ ] **V6:** Confirm read-only Platform Config summary still displays when satellite config is loaded
- [ ] **V7:** (Optional) Send a legacy request with tuning fields via curl → confirm backend accepts and uses them

---

## 7. Non-Goals (confirmed not done)

- No algorithm changes
- No backend schema field removals
- No new Admin UI in this PR
- No lock/apply flow changes
- No timeline realism changes
- No changes to scripts, tests, or docs beyond this checklist
