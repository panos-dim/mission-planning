# Audit: Scheduling Reshuffle Deep Dive

**Date**: 2026-03-05
**PR**: `audit/scheduling-reshuffle-deep-dive-auto-mode-selection-and-hidden-modes-in-ui`
**Scope**: End-to-end scheduling pipeline trace, invariant verification, bug identification

---

## 1. Pipeline Trace

### Stage 1: Feasibility (Mission Analysis)

- **Endpoint**: `POST /api/v1/mission/analyze`
- **Inputs**: targets (name, lat, lon, priority), satellites (TLE), horizon (from/to)
- **Output**: passes/opportunities cached in `app.state.current_mission_data`
- **Invariants verified**:
  - Opportunity IDs are stable (deterministic from `{satellite}_{target}_{index}`)
  - Target join keys present (`target_name` used as `target_id` throughout)
  - Time window respected (opportunities within horizon)

### Stage 2: Plan Generation

- **Endpoints**: `POST /api/v1/schedule/plan` (from_scratch/incremental), `POST /api/v1/schedule/repair`
- **Mode selection**: Deterministic based on workspace state (see `backend/auto_mode_selection.py`)
- **Invariants verified**:
  - Selected opportunities set is deterministic for same inputs (same `request_hash` → same output)
  - Plan record created with correct `workspace_id` (BUG #1 fix)
  - Plan items reference valid opportunity IDs
  - Audit breadcrumbs record: request hash, chosen mode, item counts

### Stage 3: Apply (Commit)

- **Endpoints**: `POST /api/v1/schedule/commit` (direct), `POST /api/v1/schedule/repair/commit` (repair)
- **Invariants verified**:
  - Acquisitions created with correct `workspace_id` (not NULL — BUG #1 fix)
  - Double-commit prevented (BUG #2 fix)
  - Dropped acquisitions marked as `failed` (not deleted) to preserve history
  - Commit audit log written with plan_id, workspace_id, counts
  - Atomic commit uses `BEGIN IMMEDIATE` + rollback on failure

### Stage 4: Reshuffle (Re-plan after changes)

- **Trigger**: User adds new targets → clicks "Generate Mission Plan" again
- **Mode auto-selected**: `from_scratch` if new targets, `repair` if same targets
- **Invariants verified**:
  - Adding targets triggers `from_scratch` (repair can't include new targets in cached opps)
  - Repair preserves hard-locked acquisitions
  - Schedule diff is measurable via audit trail (`added_count`, `removed_count`, `kept_count`)

---

## 2. Bug Inventory

### BUG #1: NULL workspace_id leakage in plan creation (FIXED)

- **Location**: `backend/routers/schedule.py` — `/plan` and `/repair` endpoints
- **Root cause**: `effective_workspace_id` was set to `None` when workspace had no existing acquisitions (first plan). The persistence layer has 11 queries with `OR workspace_id IS NULL` fallback, causing NULL-workspace acquisitions to appear in every workspace.
- **Impact**: Cross-workspace data contamination. A plan created in workspace A with no prior schedule would have its acquisitions visible in workspace B.
- **Fix**: `effective_workspace_id = request.workspace_id or "default"` — always propagate workspace_id.
- **Severity**: High (data integrity)

### BUG #2: Missing double-commit guard in `commit_plan` (FIXED)

- **Location**: `backend/schedule_persistence.py` — `commit_plan()` method
- **Root cause**: The non-atomic `commit_plan()` did not check `plan.status == "committed"` before creating acquisitions. The atomic variant `commit_plan_atomic()` had this check.
- **Impact**: Double-clicking Apply or network retries could create duplicate acquisitions from the same plan.
- **Fix**: Added `if plan_row["status"] == "committed": raise ValueError` guard.
- **Severity**: Medium (data duplication)

### Investigated but not bugs

- **Join key mismatch (target_id vs target_name)**: Not a bug. The system consistently uses `target_name` as `target_id` throughout the pipeline (passes → opportunities → plan items → acquisitions). The naming is confusing but consistent.
- **Schedule context endpoint accuracy**: `getScheduleContext()` derives from `/schedule/horizon` which correctly queries acquisitions. The `target_ids` returned match the target names used in auto-mode detection.
- **Repair wipes unrelated acquisitions**: Not observed. Repair partitions acquisitions into `fixed_set` (hard-locked) and `flex_set` (unlocked). Only `flex_set` items can be moved/dropped. The `repair_diff` accurately reports changes.

---

## 3. Auto Mode Selection

### Rules (deterministic)

Implemented in `backend/auto_mode_selection.py`:

1. **FROM_SCRATCH**: No existing schedule (0 acquisitions) for workspace
2. **FROM_SCRATCH**: New targets detected (current targets ⊄ scheduled target IDs)
3. **REPAIR**: Existing schedule + conflicts present
4. **REPAIR**: Existing schedule + no new targets + no conflicts (optimize unlocked)

### Frontend mirror

`MissionPlanning.tsx` `handleRunPlanning()` implements the same logic client-side:
- Fetches fresh `scheduleContext` (invalidates cache first)
- Compares `freshContext.target_ids` vs current mission targets
- Routes to repair or from_scratch path accordingly

### Logging

Every mode selection is logged at `INFO` level with structured fields:

```text
[Auto Mode Selection] mode=repair | workspace=default | existing_acq=12 | new_targets=0 | conflicts=0 | reason=...
```

---

## 4. Audit Instrumentation

### Pipeline Audit Trail

Each `/plan` and `/repair` request creates a `PipelineAuditTrail` that records breadcrumbs:

- `request_received` — mode, workspace, horizon, request hash
- `plan_created` / `repair_plan_created` — plan ID, item counts, diff stats
- Finalized trail stored in module-level `_last_planning_run` dict

### Dev Diagnostics Endpoint

`GET /api/v1/dev/last-planning-run` returns the full audit trail (DEV_MODE only):
- `run_id`, `workspace_id`, `started_at`, `completed_at`
- All breadcrumbs with timestamps and data

### Commit Audit Logs

`commit_audit_logs` table records every commit with:
- `plan_id`, `workspace_id`, `commit_type` (normal/repair/force)
- `acquisitions_created`, `acquisitions_dropped`
- `score_before`, `score_after`, `conflicts_before`, `conflicts_after`
- `config_hash`, `repair_diff_json`

---

## 5. Files Changed

| File | Change |
| --- | --- |
| `backend/auto_mode_selection.py` | NEW — Auto-mode selection + audit trail module |
| `backend/routers/schedule.py` | Audit breadcrumbs in /plan and /repair; BUG #1 fix (workspace_id) |
| `backend/routers/dev.py` | NEW endpoint: `/dev/last-planning-run` |
| `backend/schedule_persistence.py` | BUG #2 fix (double-commit guard) |
| `docs/PR_SCHED_001_CHECKLIST.md` | NEW — PR checklist with rules, evidence, scenarios |
| `docs/audits/AUDIT_SCHEDULING_RESHUFFLE.md` | NEW — This document |

---

## 6. Recommendations for Future Work

1. **Remove `OR workspace_id IS NULL` fallback** from persistence queries. Now that BUG #1 is fixed, all new plans will have a workspace_id. The NULL fallback should be deprecated after migrating legacy data.
2. **Add monotonic revision numbers** to the schedule. Currently, revisions are tracked implicitly via `commit_audit_logs` timestamps. An explicit `revision_number` column would make the "re-run produces stable diff" invariant easier to verify.
3. **Backend-side auto-mode selection**: The auto-mode logic currently runs on the frontend. Consider adding a `POST /api/v1/schedule/auto-plan` endpoint that accepts targets + workspace and internally selects the mode, removing the need for the frontend to make this decision.
4. **Incremental mode**: Currently unused in production (frontend only uses `from_scratch` and `repair`). Consider either implementing proper incremental planning or removing the enum value to reduce confusion.
