# PR_SCHED_001 — Scheduling Reshuffle Deep Dive Checklist

**PR**: `audit/scheduling-reshuffle-deep-dive-auto-mode-selection-and-hidden-modes-in-ui`
**Date**: 2026-03-05

---

## Auto Mode Selection Rules

The system deterministically selects a planning mode based on workspace/schedule state.
No mode selector is exposed in the mission planner UI.

| Revision State | New Targets? | Conflicts? | Expected Mode | Reason |
|---|---|---|---|---|
| No schedule (0 acquisitions) | N/A | N/A | `from_scratch` | Empty workspace — build fresh |
| No schedule (0 acquisitions) | Yes | N/A | `from_scratch` | Empty workspace — build fresh |
| Existing schedule | Yes | Any | `from_scratch` | New targets require full re-analysis (cached opps don't include them) |
| Existing schedule | No | > 0 | `repair` | Fix conflicts while preserving locks |
| Existing schedule | No | 0 | `repair` | Optimize unlocked items around locked ones |

### Implementation

- **Backend module**: `backend/auto_mode_selection.py` — `select_planning_mode()`
- **Frontend auto-detect**: `frontend/src/components/MissionPlanning.tsx` — `handleRunPlanning()`
- **Backend endpoints**: `/api/v1/schedule/plan`, `/api/v1/schedule/repair`

### Mode selection is logged with

- `workspace_id`
- `existing_acquisition_count`
- `new_target_count`
- `conflict_count`
- `request_payload_hash`

---

## Evidence Capture Fields

Each planning pipeline run records an audit trail (dev-only breadcrumbs):

| Field | Description |
|---|---|
| `run_id` | Unique ID per planning run (e.g. `plan_20260305_140000_a1b2c3d4`) |
| `request_hash` | SHA-256 prefix of deterministic request payload |
| `planning_mode` | Chosen mode: `from_scratch` / `incremental` / `repair` |
| `workspace_id` | Active workspace |
| `acq_ids_before` | Acquisition IDs in schedule before apply |
| `acq_ids_after` | Acquisition IDs in schedule after apply |
| `diff.kept_count` | Acquisitions preserved |
| `diff.added_count` | New acquisitions |
| `diff.removed_count` | Dropped acquisitions |

### Dev endpoint

`GET /api/v1/dev/last-planning-run` returns the full audit trail from the most recent planning run.

---

## Artifacts

| Path | Description |
|---|---|
| `backend/auto_mode_selection.py` | Auto-mode selection + audit trail module |
| `backend/routers/schedule.py` | Plan/repair endpoints with audit breadcrumbs |
| `backend/routers/dev.py` | `/dev/last-planning-run` diagnostics endpoint |
| `docs/audits/AUDIT_SCHEDULING_RESHUFFLE.md` | Deep audit document |

---

## Bugs Found & Fixes

### BUG #1: NULL workspace_id leakage in plan creation

- **Root cause**: `effective_workspace_id` was set to `None` for `from_scratch` plans (no existing acquisitions). Acquisitions committed from these plans had `NULL` workspace_id.
- **Impact**: 11 persistence queries use `OR workspace_id IS NULL` fallback, causing NULL-workspace acquisitions to leak into ALL workspace queries.
- **Fix**: Always use `request.workspace_id or "default"` when creating plans.
- **Files**: `backend/routers/schedule.py` — both `/plan` and `/repair` endpoints.

### BUG #2: Missing double-commit guard in `commit_plan`

- **Root cause**: `commit_plan()` (non-atomic path) did not check `plan.status == "committed"` before creating acquisitions. The atomic variant `commit_plan_atomic()` already had this guard.
- **Impact**: Double-clicking Apply or retrying could create duplicate acquisitions.
- **Fix**: Added `if plan_row["status"] == "committed": raise ValueError` guard.
- **File**: `backend/schedule_persistence.py`

---

## Verification Scenarios

### Scenario 1: Empty workspace → Apply

- **Expected mode**: `from_scratch`
- **Expected outcome**: rev1 created, acquisitions committed with correct `workspace_id`
- **Verify**: `GET /api/v1/dev/schedule-snapshot?workspace_id=<ws>` shows acquisitions

### Scenario 2: Add 5 targets → Apply

- **Expected mode**: `from_scratch` (new targets detected)
- **Expected outcome**: rev2 created, diff non-empty
- **Verify**: `GET /api/v1/dev/last-planning-run` shows `new_target_count > 0`

### Scenario 3: No changes → Apply

- **Expected mode**: `repair`
- **Expected outcome**: rev3 created, diff near-zero (schedule stable)
- **Verify**: audit trail shows `kept_count ≈ previous count`, `added_count ≈ 0`

### Scenario 4: Re-run without changes → stable

- **Expected**: Schedule is stable (diff near-zero), deterministic output
- **Verify**: Same `request_hash` → same output

---

## Manual Scenario Run Results

> Fill in after running the 3-scenario demo (10 → 15 → 20 targets)

| Scenario | Targets | Mode Chosen | Rev Before | Rev After | Added | Removed | Kept |
|---|---|---|---|---|---|---|---|
| 1 (initial) | 10 | | | | | | |
| 2 (+5) | 15 | | | | | | |
| 3 (+5) | 20 | | | | | | |
| 3 (re-run) | 20 | | | | | | |
