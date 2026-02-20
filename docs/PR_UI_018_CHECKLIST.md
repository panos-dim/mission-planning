# PR-UI-018: Apply Button Unification, Repair Flow Fixes & Panel Redesign

## Checklist

### 1. No "commit" strings remain in UI surfaces

**Grep evidence** (run from `frontend/src/`):

```bash
# User-facing commit text audit
grep -rn --include="*.tsx" --include="*.ts" -i "commit" frontend/src/ \
  | grep -v node_modules \
  | grep -v "// " \          # code comments
  | grep -v "console\." \    # debug logs
  | grep -v "import " \      # import statements
  | grep -v "api/generated/" # auto-generated API types
```

**Remaining "commit" occurrences are all internal/non-user-facing:**

| Category | Examples | Why kept |
|----------|----------|----------|
| API function names | `commitScheduleDirect`, `commitBatch`, `commitRepairPlan` | Maps to backend endpoint names |
| API type interfaces | `CommitPreview`, `DirectCommitRequest`, `RepairCommitResponse` | Maps to backend schema |
| API endpoint constants | `SCHEDULE_COMMIT_DIRECT`, `BATCH_COMMIT` | Backend URL paths |
| Internal variable names | `isCommitting`, `commitItems`, `backendCommitSuccess` | Code-only, not rendered |
| Backend state values | `'committed'` (acquisition/batch state) | API enum from backend |
| Generated types | `api/generated/api-types.ts` | Auto-generated, do not edit |
| Code comments | JSDoc, PR tags | Not rendered |
| Console.log messages | `console.log('[PromoteToOrders]...')` | Debug only |

### 2. Apply button placement & style

| Surface | Component | Style | Placement |
|---------|-----------|-------|-----------|
| **Planning results** | `MissionPlanning.tsx` | `bg-blue-600` brand blue | Top of results section |
| **Planning results (feature)** | `PlanningResults.tsx` | `variant="primary"` (blue) | Header actions row |
| **Repair preview modal** | `RepairCommitModal.tsx` | `bg-blue-600` brand blue | Modal footer (bottom) |
| **Conflict warning modal** | `ConflictWarningModal.tsx` | `variant="primary"` (blue) | Modal footer (bottom) |
| **Apply confirmation panel** | `ApplyConfirmationPanel.tsx` | `bg-blue-600` with shadow | Panel footer (sticky bottom) |
| **Batch orders** | `OrdersArea.tsx` | `bg-blue-600` brand blue | Batch detail actions |
| **What-If compare** | `WhatIfComparePanel.tsx` | `bg-blue-600` brand blue | Panel footer |

### 3. Schedule title without "(N opportunities)"

| Component | Before | After |
|-----------|--------|-------|
| `PlanningResults.tsx` | `Schedule (42 opportunities)` | `Schedule` |

### 4. Export icon → download arrow mapping

| Component | Export Action | Icon Before | Icon After |
|-----------|-------------|-------------|------------|
| `MissionPlanning.tsx` | CSV export | text only | `Download` ↓ |
| `MissionPlanning.tsx` | JSON export | text only | `Download` ↓ |
| `PlanningResults.tsx` | CSV export | text only | `Download` ↓ |
| `PlanningResults.tsx` | JSON export | text only | `Download` ↓ |
| `MissionResultsPanel.tsx` | JSON export | `List` | `Download` ↓ |
| `MissionResultsPanel.tsx` | CSV export | `Download` ↓ | `Download` ↓ (unchanged) |
| `AcceptedOrders.tsx` | CSV export | `Download` ↓ | `Download` ↓ (unchanged) |

### 5. Repair commit flow (409 Conflict fix)

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| **409 on repair Apply** | Frontend sent all items (including existing acqs) to `commitScheduleDirect`, which rejects duplicates | `LeftSidebar.tsx` now detects repair mode via `result.repair_plan_id` and calls `commitRepairPlan` instead |
| **Repair metadata missing** | `AlgorithmResult` had no repair fields | Added `repair_plan_id` and `repair_dropped_ids` to `AlgorithmResult` in `types/index.ts` |
| **Repair metadata not populated** | `MissionPlanning.tsx` didn't set repair fields | `algoResult` now populates `repair_plan_id`, `repair_dropped_ids`, and `target_statistics` from repair response |

### 6. ApplyConfirmationPanel redesign

| Before | After |
|--------|-------|
| Flat gray header | Gradient header with contextual color (emerald/yellow/red) |
| Sparse text summary | 3-column stats row: Acquisitions · Satellites · Targets |
| Plain text diff counts | Styled pill badges with icons: `🛡 kept` `+ added` `- dropped` `⏱ moved` |
| No target list | Full target assignment list with satellite, time, and `NEW`/`kept` badges |
| Basic coverage text | Gradient coverage bar (emerald at 100%, blue otherwise) |
| "No conflicts detected" | Repair-aware: "Existing acquisitions preserved. New targets added safely." |
| "Review Warnings" for incremental adds | Only warns when acquisitions are actually dropped (0-drop = green "Ready to Apply") |
| Plain footer buttons | Refined buttons with shadow and border accents |
| No horizon display | Compact clock icon + time range at bottom |

### 7. Zero Roll/Incidence angle fix

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| **Off-Nadir/Roll = 0 for new targets** | `main.py` cache tried to read `opp.roll_angle_deg` but `Opportunity` uses `incidence_angle` | Corrected mapping: `incidence_angle → roll_angle_deg`, `pitch_angle → pitch_angle_deg` |
| **Python falsy trap** | `0.0 or default` returns default because `0.0` is falsy | Changed to explicit `is not None` checks |
| **Fallback hardcoded 0.0** | `schedule.py` repair fallback set `roll_angle_deg: 0.0` | Now extracts `incidence_angle_deg` from `PassDetails` |
| **Fallback used full pass window** | Pass `start_time→end_time` spans minutes, overlapping existing acquisitions → all rejected as infeasible | Now uses `max_elevation_time` (point-in-time imaging moment) |
| **value=None on plan items** | Fixed/kept items in `incremental_planning.py` didn't include `value` in output dict | Added `value` field to fixed and flex item dicts in `execute_repair_planning` |

### 8. Backend fixes

| File | Change |
|------|--------|
| `backend/main.py` | Opportunity cache: `incidence_angle → roll_angle_deg` mapping with `is not None` checks |
| `backend/routers/schedule.py` | Repair fallback: `max_elevation_time` instead of full pass window; extract `incidence_angle_deg` |
| `backend/schedule_persistence.py` | v2.4 migration: add `score_before`, `score_after`, `conflicts_before`, `conflicts_after` to `commit_audit_logs` |
| `backend/incremental_planning.py` | Add `value` to fixed/flex plan items; add rejection reason logging for filtered opportunities |

### 9. Double-invocation guard

| Issue | Root Cause | Fix |
|-------|-----------|-----|
| **Repair POST called twice (30s delay)** | React StrictMode double-fires; `isPlanning` state guard is async — both calls read `false` | Added `planningGuardRef` (synchronous ref-based guard, same pattern as `commitGuardRef`) |

### 10. Files changed

#### Frontend

| File | Changes |
|------|---------|
| `components/MissionPlanning.tsx` | Warning logic: only warn on actual drops, not incremental adds; `target_statistics` computed for repair results; `planningGuardRef` double-invocation guard; `repair_plan_id`/`repair_dropped_ids`/`target_statistics` in `AlgorithmResult` |
| `components/ApplyConfirmationPanel.tsx` | Full redesign: gradient header, stats row, diff pills, target assignments, coverage bar, repair-aware status banner, refined footer |
| `components/LeftSidebar.tsx` | Repair commit flow: detect `repair_plan_id` → call `commitRepairPlan` instead of `commitScheduleDirect` |
| `types/index.ts` | Added `repair_plan_id` and `repair_dropped_ids` to `AlgorithmResult` interface |
| `components/ConflictWarningModal.tsx` | "Ready to Commit" → "Ready to Apply", button labels |
| `components/RepairCommitModal.tsx` | "Commit Preview" → "Apply Preview", button blue, labels |
| `components/features/mission-planning/PlanningResults.tsx` | Remove "(N opportunities)", export icons, Apply variant primary |
| `components/MissionResultsPanel.tsx` | JSON export: `List` → `Download` icon |
| `components/SchedulePanel.tsx` | Tab label "Committed" → "Schedule", history text |
| `components/AcceptedOrders.tsx` | Header "Committed" → "Schedule", empty state text |
| `components/ScheduledAcquisitionsList.tsx` | "Lock Committed" → "Lock All", error text |
| `components/ScheduleTimeline.tsx` | Empty state: "No committed schedule" → "No schedule" |
| `components/OrdersArea.tsx` | "Commit" → "Apply" button, confirm dialog, error msg, blue style |
| `components/RepairDiffPanel.tsx` | "until committed" → "until applied", tooltip |
| `components/ObjectExplorer/Inspector.tsx` | "not committed" → "not applied", lock text |
| `components/WhatIfComparePanel.tsx` | "Accept & Commit" → "Accept & Apply", blue style |
| `components/DemoScenarioRunner.tsx` | "Plans committed" → "Plans applied", error msg |
| `components/admin/ValidationTab.tsx` | "commit workflows" → "apply workflows", "Committed" → "Applied" |
| `utils/errorMapper.ts` | "Cannot commit" → "Cannot apply", "already committed" → "already applied" |

#### Backend

| File | Changes |
|------|---------|
| `backend/main.py` | Opportunity cache attribute mapping fix (`incidence_angle → roll_angle_deg`), `is not None` checks |
| `backend/routers/schedule.py` | Repair fallback: `max_elevation_time` for point-in-time opportunities, `incidence_angle_deg` extraction |
| `backend/schedule_persistence.py` | v2.4 schema migration: `score_before/after`, `conflicts_before/after` columns on `commit_audit_logs` |
| `backend/incremental_planning.py` | `value` field on fixed/kept plan items; rejection reason logging |

#### Test

| File | Changes |
|------|---------|
| `scripts/test_repair_e2e_v2.py` | Horizon query: explicit `from`/`to` date range matching test analysis window |

### 11. Build verification

- [x] `tsc --noEmit` passes (zero errors)
- [x] `vite build` passes (zero errors)
- [x] Python compiles clean (`py_compile` on all changed backend files)
- [x] E2E test: **31/31 passed** (`scripts/test_repair_e2e_v2.py`)
  - ✅ Analyze → Plan → Commit → Hard-lock → Horizon → Repair → Diff → Reasons → Metrics → Context → Plan Items → minimize_changes
- [x] Manual smoke: repair commit flow (no 409), Apply panel shows green "Ready to Apply" for incremental adds
- [ ] Screenshots captured

### 12. E2E test coverage summary

| Mode | Verified | Details |
|------|----------|---------|
| `from_scratch` | ✅ | Plans 3 items from 690 opportunities via `roll_pitch_best_fit` |
| `direct_commit` | ✅ | Commits to isolated workspace with lock level |
| `hard_lock` | ✅ | Locks acquisition, persists across horizon query |
| `repair` (maximize_score) | ✅ | Preserves hard-locked, keeps flex, geometry/values intact, 690 opportunities available |
| `repair` (minimize_changes) | ✅ | Respects `max_changes` limit |
| `repair_commit` | ✅ | Uses dedicated endpoint, no 409 on existing acquisitions |

### 13. Non-goals confirmed

- [x] No schedule algorithm logic changes
- [x] No conflict detection logic changes
- [x] No planning visualization changes
- [x] No target/opportunity coloring rule changes
