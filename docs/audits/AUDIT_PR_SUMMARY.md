# Audit PR Summary: Ops Readiness Review

> PR-AUD-OPS-UI-LOCKS-PARITY — Deep Audit for Mission Planner
> Generated: 2025-02-10

---

## Top 10 Changes Needed

### 1. Flip Priority Scale (1 = Best → 5 = Lowest)

**Impact**: Backend scoring formula + all defaults across 5 files.
**Single-point fix**: Change `quality_scoring.py:236` normalization from `(priority - 1) / 4` to `(5 - priority) / 4`. Change all defaults from `1` to `5`.
**Audit doc**: `AUDIT_PRIORITY_SEMANTICS.md`

### 2. Remove Flexibility Feature (repair_scope, max_changes, objective)

**Impact**: Frontend `MissionPlanning.tsx` state (lines 87–97), `RepairSettingsPresets.tsx`, backend `RepairPlanRequest` schema.
**Action**: Hard-code `repair` mode with `maximize_score` objective and no change cap. Remove UI controls.
**Audit doc**: `AUDIT_LOCKS_END_TO_END.md` §4, `AUDIT_PARAMETER_GOVERNANCE_GAPS.md` §2.2

### 3. Rename UI Labels (Mission Analysis → Feasibility Analysis, etc.)

**Impact**: ~15 string changes across 6 component files. UI-only — no API contract changes.
**Action**: Create `labels.ts` constants file. Batch-rename in one PR.
**Audit doc**: `AUDIT_TERMINOLOGY_MAP.md`

### 4. Move Platform-Truth Parameters to Admin/Config

**Impact**: Remove `imaging_time_s`, `max_roll_rate_dps`, `max_roll_accel_dps2`, `look_window_s`, `algorithms`, `value_source` from planner UI. Read from satellite config summary (already fetched).
**Audit doc**: `AUDIT_PARAMETER_GOVERNANCE_GAPS.md` §5

### 5. Add Map Lock Mode (click-to-lock on Cesium globe)

**Impact**: New Zustand store + Cesium click handler + toolbar toggle button. Pattern exists in `targetAddStore.ts`.
**Audit doc**: `AUDIT_LOCKS_END_TO_END.md` §5

### 6. Add Rich Timeline Hover Tooltips

**Impact**: Modify `ScheduleTimeline.tsx` card render to show date, satellite, target, geometry, lock status on hover.
**Quick win** — achievable in current card-based layout before full timeline rewrite.
**Audit doc**: `AUDIT_TIMELINE_REALISM.md` §3

### 7. Restructure Right Sidebar: "Mission Results" → "Opportunities"

**Impact**: Rename panel in `RightSidebar.tsx`, restructure content to show per-target opportunity counts with dropdowns.
**Audit doc**: `AUDIT_UI_NAV_SURFACE.md` §4, `AUDIT_TERMINOLOGY_MAP.md`

### 8. Remove Conflicts Tab from Schedule Panel

**Impact**: Remove tab from `SCHEDULE_TABS` in `simpleMode.ts:75` and `SchedulePanel.tsx`. Keep badge indicator on Schedule icon.
**Audit doc**: `AUDIT_UI_NAV_SURFACE.md` §4

### 9. Deprecate Legacy Planning Path (`/api/planning/run`)

**Impact**: Route all planning through persistent `/api/v1/schedule/repair` path. Ensures all plans are persisted and auditable.
**Audit doc**: `AUDIT_API_SURFACE_FOR_PLANNER.md` §5

### 10. Rename "Max Pointing Angle" → "Max Off-nadir Angle"

**Impact**: UI label change in `MissionParameters.tsx:379`. No API changes.
**Audit doc**: `AUDIT_PARAMETER_GOVERNANCE_GAPS.md` §4

---

## Proposed PR Sequence (6 PRs)

### PR 1: `chore/terminology-labels`

- Create `frontend/src/constants/labels.ts` with all user-facing strings
- Rename: Mission Analysis → Feasibility Analysis, Mission Results → Feasibility Results, Analyze Mission → Run Feasibility, Commit to Schedule → Apply
- Rename: Max Pointing Angle → Max Off-nadir Angle
- Remove Conflicts tab from Schedule panel (keep badge)
- **Files**: `LeftSidebar.tsx`, `RightSidebar.tsx`, `MissionControls.tsx`, `MissionParameters.tsx`, `MissionPlanning.tsx`, `simpleMode.ts`, `SchedulePanel.tsx`
- **Risk**: Low — UI-only label changes, no API or behavioral changes

### PR 2: `fix/priority-scale-inversion`

- Flip normalization: `quality_scoring.py:236` → `(5.0 - priority) / 4.0`
- Change all defaults from `1` to `5` (frontend types, backend schemas, core library)
- Update priority validator messages to reflect new semantics
- Add regression tests for value computation with inverted scale
- **Files**: `quality_scoring.py`, `targets.py`, `scheduler.py`, `target.py` (backend schema), `types/index.ts`, `TargetInput.tsx`
- **Risk**: Medium — touches scoring engine, needs thorough testing

### PR 3: `refactor/parameter-governance`

- Move `imaging_time_s`, `max_roll_rate_dps`, `max_roll_accel_dps2`, `max_pitch_rate_dps`, `max_pitch_accel_dps2` to backend config defaults
- Remove corresponding UI controls from `MissionPlanning.tsx` advanced section
- Hide `look_window_s`, `algorithms`, `value_source` from planner (use server defaults)
- Auto-populate from satellite config summary (already fetched)
- **Files**: `MissionPlanning.tsx`, `config/mission_settings.yaml`, `backend/schemas/planning.py`
- **Risk**: Medium — must ensure backend defaults match current UI defaults

### PR 4: `refactor/remove-flexibility-feature`

- Remove `repair_scope`, `max_changes`, `objective` from repair UI
- Remove `RepairSettingsPresets.tsx` component
- Hard-code `repair` mode + `maximize_score` + no change cap in frontend
- Backend: make these fields optional with sensible defaults
- Remove `soft` lock migration code (`schedule_persistence.py:825-831`)
- **Files**: `MissionPlanning.tsx`, `RepairSettingsPresets.tsx`, `scheduleApi.ts`, `schedule_persistence.py`
- **Risk**: Low-medium — simplification, removes code paths

### PR 5: `feat/map-lock-mode`

- New `mapLockModeStore.ts` (Zustand) — clone `targetAddStore.ts` pattern
- Toolbar toggle button near map controls
- Cesium entity click handler: resolve entity → acquisition ID → `toggleLock()`
- Visual feedback: lock cursor, lock overlay on map entities
- Add rich hover tooltips to `ScheduleTimeline.tsx` cards
- **Files**: New store, `CesiumViewer.tsx` or `ObjectMapViewer.tsx`, `ScheduleTimeline.tsx`, toolbar component
- **Risk**: Medium — new interactive feature, needs Cesium integration testing

### PR 6: `refactor/consolidate-planning-paths`

- Deprecate `/api/planning/run` with warning header
- Route `from_scratch` planning through persistent schedule path
- Add redirect from legacy endpoint to new endpoint
- Regenerate `api-types.ts`
- **Files**: `backend/main.py`, `MissionPlanning.tsx`, `scheduleApi.ts`, `api-types.ts`
- **Risk**: Medium — touches both planning code paths, needs integration testing

---

## Audit Documents Delivered

| Document | Path | Focus |
| -------- | ---- | ----- |
| UI Navigation Surface | `docs/audits/AUDIT_UI_NAV_SURFACE.md` | Panel layout, component tree, duplication points |
| Locks End-to-End | `docs/audits/AUDIT_LOCKS_END_TO_END.md` | Lock model, persistence, UI actions, map lock mode design |
| Priority Semantics | `docs/audits/AUDIT_PRIORITY_SEMANTICS.md` | Priority scale, normalization, sorting, flip risk assessment |
| Timeline Realism | `docs/audits/AUDIT_TIMELINE_REALISM.md` | Current card layout, real timeline requirements, hover tooltips |
| Terminology Map | `docs/audits/AUDIT_TERMINOLOGY_MAP.md` | Label mapping, API vs UI labels, Object Explorer tree |
| Parameter Governance Gaps | `docs/audits/AUDIT_PARAMETER_GOVERNANCE_GAPS.md` | Input categorization, look_window, agility parameter audit |
| API Surface for Planner | `docs/audits/AUDIT_API_SURFACE_FOR_PLANNER.md` | Complete endpoint map, request/response shapes, legacy paths |
| PR Summary (this doc) | `docs/audits/AUDIT_PR_SUMMARY.md` | Top 10 changes + 6-PR sequence |

---

## Hard Constraints Honored

- No implementation, no algorithm changes, no endpoint renaming
- No UI changes or renaming implemented — audit only
- All file references are to current codebase state
- All recommendations are minimal-change strategies
