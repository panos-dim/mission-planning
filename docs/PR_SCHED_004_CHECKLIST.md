# PR_SCHED_004 Checklist

## Auto-Mode Decision Table

| Condition | Expected mode | Notes |
| --- | --- | --- |
| No active schedule exists for the workspace | `from_scratch` | Includes first run and cleared/empty schedule state |
| Schedule exists and new actionable work appears | `incremental` | New work includes new one-time targets plus outstanding recurring instances in the active horizon |
| Schedule exists and no new work appears | `repair` | Stable non-incremental path; avoids inventing fake additive work |
| Schedule exists but scheduled items are stale, invalid, or conflicting | `repair` | Includes removed targets, invalid lineage, and unresolved conflicts |
| New work appears but incremental extension is unsafe | `repair` with `fallback_from_mode=incremental` | Explicit fallback branch for invalid existing state |
| New work is materially higher priority and weights favor reshuffling | `repair` | Preserves existing weight-aware reshuffle behavior |

## Example Inputs -> Expected Mode

| Example | Expected mode |
| --- | --- |
| Empty workspace, no acquisitions | `from_scratch` |
| Existing committed schedule + one new recurring dated instance | `incremental` |
| Existing committed schedule + same horizon + no new targets or instances | `repair` |
| Existing schedule + new work + stale scheduled acquisition still present | `repair` with `fallback_from_mode=incremental` |
| Same canonical target already scheduled on day 1, new recurring instance appears on day 2 | `incremental` |
| Existing schedule + new one-time target + new recurring instance | `incremental` |

## Log / Audit Fields Captured

- `workspace_id`
- `chosen_mode`
- `reason`
- `previous_schedule_revision_id`
- `existing_committed_acquisition_count`
- `current_materialized_instance_count`
- `outstanding_instance_count`
- `new_instance_count`
- `new_target_count`
- `new_one_time_order_count`
- `removed_scheduled_target_count`
- `stale_acquisition_count`
- `conflict_count`
- `fallback_from_mode`
- `request_payload_hash`

## Unit / Integration Tests Added

- `tests/unit/test_scheduling_mode.py`
  - no schedule -> `from_scratch`
  - schedule + newly materialized recurring instances -> `incremental`
  - schedule + no new work -> stable non-incremental path
  - invalid incremental candidate -> `repair` fallback
  - same canonical target on multiple recurring days treated as new dated work
  - mixed one-time + recurring workload
- Existing regressions re-run:
  - `tests/unit/test_schedule_commit_conflicts.py -k TestPlanningModeSelection`
  - `tests/unit/test_recurring_order_materialization.py`
  - `tests/unit/test_recurring_order_lineage.py`
- Frontend planner regression re-run:
  - `frontend/src/components/__tests__/MissionPlanning.test.tsx`

## Manual Verification Results

- Backend mode-selection endpoint scenarios were verified through targeted TestClient coverage with explicit horizon inputs.
- Frontend planner UI was verified through the MissionPlanning Vitest suite after removing raw mode labels from the visible banner.
- Interactive click-through in a live browser was not run in this session.

## Verification Commands Run

```bash
PYTHONPATH=. ./.venv/bin/python -m py_compile \
  backend/scheduling_mode.py \
  backend/routers/schedule.py \
  backend/schedule_persistence.py \
  backend/main.py \
  backend/routers/dev.py \
  backend/schemas/planning.py

PYTHONPATH=. ./.venv/bin/pytest -q -o addopts='' tests/unit/test_scheduling_mode.py
PYTHONPATH=. ./.venv/bin/pytest -q -o addopts='' tests/unit/test_recurring_order_materialization.py tests/unit/test_recurring_order_lineage.py
PYTHONPATH=. ./.venv/bin/pytest -q -o addopts='' tests/unit/test_schedule_commit_conflicts.py -k 'TestPlanningModeSelection'

cd frontend
./node_modules/.bin/tsc -p tsconfig.json --noEmit
./node_modules/.bin/vitest run src/components/__tests__/MissionPlanning.test.tsx
```
