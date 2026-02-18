# PR_UI_007 — Remove Look Window from Planner UI & Centralize Default

**Goal:** Remove "look window" from planner-facing UI, stop FE from sending overrides,
and let the backend use its config/Pydantic default. No algorithm changes.

---

## 1. Usage Map (complete inventory)

### Frontend (changed in this PR)

| File | Reference | What it does | Action |
|------|-----------|-------------|--------|
| `frontend/src/components/MissionPlanning.tsx:103` | `look_window_s: 600.0` in state init | Default value in legacy planner config state | **Removed** — comment placeholder |
| `frontend/src/components/MissionPlanning.tsx:255` | `look_window_s: config.look_window_s` in repair request | Sends override to `/api/v1/schedule/repair` | **Removed** — no longer sent |
| `frontend/src/components/MissionPlanning.tsx:898` | `<input>` with label "Look Window" | Planner UI control for editing value | **Removed** — replaced with comment |
| `frontend/src/components/MissionPlanning.tsx:335` | `...config` spread in planning request | Would include look_window_s if present | **No longer present** in config state |
| `frontend/src/components/features/mission-planning/PlanningParameters.tsx:40-48` | `<Input label="Look Window" ...>` | Refactored planner UI control | **Removed** — replaced with comment |
| `frontend/src/components/features/mission-planning/usePlanningState.ts:109` | `look_window_s: 600.0` in DEFAULT_CONFIG | Default in planning state hook | **Removed** — comment placeholder |
| `frontend/src/types/index.ts:571` | `look_window_s: number` in `PlanningRequest` | Required field in request DTO | **Changed to optional** (`look_window_s?: number`) |
| `frontend/src/types/index.ts:593` | `look_window_s: number` in `PlanningConfig` | Required field in config DTO | **Changed to optional** |
| `frontend/src/api/scheduleApi.ts:342` | `look_window_s?: number` in `IncrementalPlanRequest` | Already optional in incremental request | **Kept** — backward compat |
| `frontend/src/api/scheduleApi.ts:460` | `look_window_s?: number` in `RepairPlanRequest` | Already optional in repair request | **Kept** — backward compat |
| `frontend/src/api/planningApi.ts:26` | `look_window_s: number` in `PlanningConfigResponse` | Response type from GET config endpoint | **Kept** — backend still returns it |

### Backend (NOT changed — stable, uses defaults)

| File | Reference | What it does | Action |
|------|-----------|-------------|--------|
| `backend/schemas/planning.py:50-52` | `look_window_s: float = Field(default=600.0, ...)` | Pydantic schema default for planning request | **Kept** — canonical Pydantic default |
| `backend/routers/schedule.py:1152` | `look_window_s: float = Field(default=600.0, ...)` | Incremental plan request schema | **Kept** — Pydantic default applies when FE omits |
| `backend/routers/schedule.py:1627` | `look_window_s: float = Field(default=600.0)` | Repair plan request schema | **Kept** — Pydantic default applies when FE omits |
| `backend/incremental_planning.py:509` | `look_window_s: float = Field(default=600.0, ...)` | Incremental planning request model | **Kept** — Pydantic default |
| `backend/main.py:2617` | `look_window_s=request.look_window_s` | Passes value to SchedulerConfig | **Kept** — reads from request (Pydantic-defaulted) |
| `backend/main.py:2935` | `"look_window_s": 600.0` | GET /planning/config response | **Kept** — returns default for info |

### Core library (NOT changed)

| File | Reference | What it does | Action |
|------|-----------|-------------|--------|
| `src/mission_planner/scheduler.py:304` | `look_window_s: float = 600.0` | SchedulerConfig dataclass default | **Kept** — algorithm-level default |

### Config (NOT changed)

| File | Reference | What it does | Action |
|------|-----------|-------------|--------|
| `config/mission_settings.yaml:90` | `default_look_window_s: 600` | YAML config default | **Kept** — config source of truth |

### Scripts (NOT changed — out of scope)

| File | Reference | Notes |
|------|-----------|-------|
| `scripts/analysis/tight_limits.py` | `look_window_s` in test payloads | Analysis script — not planner UI |
| `scripts/analysis/aggressive_maneuvers.py` | `look_window_s` | Analysis script |
| `scripts/analysis/extreme_slews.py` | `look_window_s` | Analysis script |
| `scripts/analysis/mixed_maneuvers.py` | `look_window_s` | Analysis script |
| `scripts/analysis/complex_scenario.py` | `look_window_s` | Analysis script |
| `scripts/analysis/edge_of_fov.py` | `look_window_s` | Analysis script |
| `scripts/analysis/extreme_pitch.py` | `look_window_s` | Analysis script |
| `scripts/analysis/greece_mission.py` | `look_window_s` | Analysis script |
| `scripts/analysis/greece_validation.py` | `look_window_s` | Analysis script |
| `scripts/analysis/pitch_maneuvers.py` | `look_window_s` | Analysis script |
| `scripts/analysis/roll_pitch_algorithm.py` | `look_window_s` | Analysis script |
| `scripts/analysis/scheduler_algorithms.py` | `look_window_s` | Analysis script |
| `scripts/demo/demo_incidence_angle_problem.py` | `look_window_s` | Demo script |
| `scripts/utilities/compare_with_api.py` | `look_window_s` | Utility script |
| `scripts/utilities/verify_kml_mission.py` | `look_window_s` | Utility script |
| `scripts/tests/test_e2e_quality_planning.py` | `look_window_s` | Test script |
| `scripts/tests/test_quality_planning.py` | `look_window_s` | Test script |
| `tests/integration/test_incidence_angle_api.py` | `look_window_s` | Integration test |

### Docs (NOT changed — informational)

| File | Notes |
|------|-------|
| `docs/audits/AUDIT_PARAMETER_GOVERNANCE_GAPS.md` | Audit doc referencing look_window governance |
| `docs/audits/AUDIT_PR_SUMMARY.md` | PR summary doc |
| `docs/audits/AUDIT_API_SURFACE_FOR_PLANNER.md` | API surface audit |
| `docs/PR_PARAM_GOV_01_CHECKLIST.md` | Parameter governance checklist |
| `docs/PR_UI_002_CHECKLIST.md` | Earlier UI checklist |
| `docs/AUDIT_PERSISTENT_SCHEDULING_HISTORY.md` | Scheduling history audit |
| `docs/PARAMETER_GOVERNANCE_RULES.md` | Governance rules doc |
| `docs/WORKSPACE_OBJECT_TREE_AUDIT.md` | Workspace audit |
| `docs/algorithms/ROLL_PITCH.md` | Algorithm documentation |
| `docs/api/API_REFERENCE.md` | API reference |

---

## 2. Canonical Default Source

**Canonical default: `600.0` seconds** — sourced from multiple layers:

| Layer | Location | Value | Role |
|-------|----------|-------|------|
| **Config (YAML)** | `config/mission_settings.yaml:90` | `default_look_window_s: 600` | Config file source of truth |
| **Core library** | `src/mission_planner/scheduler.py:304` | `look_window_s: float = 600.0` | Dataclass default (algorithm layer) |
| **Backend schema** | `backend/schemas/planning.py:50` | `Field(default=600.0)` | Pydantic validation default |
| **Router schemas** | `backend/routers/schedule.py:1152,1627` | `Field(default=600.0)` | Request model defaults |

**After this PR:** When the FE omits `look_window_s` from requests, Pydantic fills in `600.0`
from the schema default. The YAML config value (`default_look_window_s: 600`) is available
for future use if the backend switches to reading from config at startup. Currently, the
Pydantic defaults are the active canonical source at runtime.

---

## 3. Backward Compatibility

- **FE request DTOs** (`IncrementalPlanRequest`, `RepairPlanRequest` in `scheduleApi.ts`) retain
  `look_window_s` as an **optional** field. Older clients or scripts that still send the field
  will have it accepted and used by the backend — no breaking change.
- **Backend schemas** still define `look_window_s` with `Field(default=600.0)`. If the field is
  present in a request, it is used. If absent, the Pydantic default applies.
- **No backend field removal** in this PR — that is a future PR once UI cleanup is confirmed.

---

## 4. Manual Verification Steps

- [ ] **V1:** Run feasibility/planning with the UI after change → confirm it still works
- [ ] **V2:** Confirm (network logs / browser DevTools) the request payload no longer contains `look_window_s`
- [ ] **V3:** Confirm backend logs/config indicate the default (600.0) is applied
- [ ] **V4:** (Optional) Send a legacy request with `look_window_s` included → confirm backend accepts it

---

## 5. Files Changed Summary

| File | Change |
|------|--------|
| `frontend/src/components/MissionPlanning.tsx` | Removed Look Window input control, removed from state init, removed from repair request |
| `frontend/src/components/features/mission-planning/PlanningParameters.tsx` | Removed Look Window input control |
| `frontend/src/components/features/mission-planning/usePlanningState.ts` | Removed `look_window_s` from DEFAULT_CONFIG |
| `frontend/src/types/index.ts` | Made `look_window_s` optional in `PlanningRequest` and `PlanningConfig` |
| `docs/PR_UI_007_CHECKLIST.md` | **Created** — this file |

---

## 6. Non-Goals (confirmed not done)

- No algorithm changes
- No backend field removal (future PR)
- No Admin UI introduced
- No timeline/locking/priority changes
- No changes to scripts, tests, or docs beyond this checklist
