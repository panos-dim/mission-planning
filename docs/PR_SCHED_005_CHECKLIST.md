# PR_SCHED_005 Checklist

## Diff Fields

Each applied revision now records a lineage-aware diff with:

- `revision_id`
- `previous_revision_id`
- `mode_used`
- `diff_summary`
- `diff.added[]`
- `diff.removed[]`
- `diff.kept[]`
- `diff.changed_timing[]`
- `diff.changed_satellite_assignment[]`

Each diff entry carries recurring lineage when present:

- `order_id`
- `template_id`
- `instance_key`
- `canonical_target_id`
- `planner_target_id`
- `display_target_name`
- `identity_key`
- `match_strategy`

## Revision Summary Example

```json
{
  "revision_id": 3,
  "previous_revision_id": 2,
  "mode_used": "repair",
  "diff_summary": {
    "before_count": 15,
    "after_count": 20,
    "added_count": 5,
    "removed_count": 0,
    "kept_count": 15,
    "unchanged_kept_count": 12,
    "changed_timing_count": 2,
    "changed_satellite_assignment_count": 1
  }
}
```

## Artifact Paths

- `artifacts/demo/RESHUFFLE_EXPLAINER.json`
- `artifacts/demo/RESHUFFLE_EXPLAINER.md`
- Dev endpoint: `GET /api/v1/dev/reshuffle-explainer?workspace_id=<workspace_id>`
- Commit history surface: `GET /api/v1/schedule/commit-history?workspace_id=<workspace_id>`

## Manual Scenario Verification

Recommended demo sequence:

1. Apply an initial schedule with 10 acquisitions. Verify `revision_id=2`, `added_count=10`, and no timing/satellite changes.
2. Apply an incremental run that grows the schedule from 10 to 15. Verify `added_count=5`, `kept_count=10`, and recurring instance lineage appears for newly materialized dated instances.
3. Apply a repair/reshuffle run that grows or rebalances the schedule from 15 to 20. Verify the explainer shows meaningful `changed_timing` and/or `changed_satellite_assignment` entries instead of only raw adds/removes.
4. Confirm the latest workspace explainer is available from both:
   - `artifacts/demo/RESHUFFLE_EXPLAINER.{json,md}`
   - `/api/v1/dev/reshuffle-explainer`
5. Confirm `/api/v1/schedule/commit-history` exposes `revision_id`, `previous_revision_id`, `mode_used`, and `diff_summary` for the same apply.

## Verification Commands Run

```bash
PYTHONPATH=. python -m py_compile \
  backend/reshuffle_explainer.py \
  backend/schedule_persistence.py \
  backend/routers/schedule.py \
  backend/routers/dev.py \
  tests/unit/test_reshuffle_explainer.py

PYTHONPATH=. ./.venv/bin/python -m pytest -q -o addopts='' tests/unit/test_reshuffle_explainer.py
PYTHONPATH=. ./.venv/bin/python -m pytest -q -o addopts='' tests/unit/test_schedule_commit_conflicts.py -k 'commit_plan_persists_revision_summary_and_dev_explainer'
PYTHONPATH=. ./.venv/bin/python -m pytest -q -o addopts='' tests/unit/test_lock_management.py -k 'create_audit_log or get_audit_logs or atomic_commit'
PYTHONPATH=. ./.venv/bin/python -m pytest -q -o addopts='' tests/unit/test_recurring_order_lineage.py
```
