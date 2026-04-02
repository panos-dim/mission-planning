# Audit: Reshuffle Explainer

**Date**: 2026-04-02
**Scope**: Revision-to-revision evidence for schedule apply flows, including recurring lineage and auto-mode plans

## What Changed

The backend now treats reshuffle evidence as a first-class persisted artifact instead of a transient ID diff:

- Every schedule apply path in `backend/routers/schedule.py` now captures the active schedule before commit, computes a post-commit revision diff, and persists the result on the commit audit log.
- `backend/schedule_persistence.py` schema `2.9` adds:
  - `revision_id`
  - `previous_revision_id`
  - `mode_used`
  - `diff_summary_json`
  - `reshuffle_explainer_json`
- `backend/reshuffle_explainer.py` centralizes:
  - lineage-aware matching
  - diff summary generation
  - markdown rendering
  - demo artifact writes
- `backend/routers/dev.py` exposes `GET /api/v1/dev/reshuffle-explainer?workspace_id=...`

## Matching Rules

The explainer matches acquisitions across revisions in this priority order:

1. `order_id`
2. `template_id + instance_key`
3. `opportunity_id`
4. fallback target lineage (`planner_target_id + canonical_target_id`)

This keeps recurring dated instances stable across revisions and allows the diff to classify a repair outcome as:

- kept
- added
- removed
- changed timing
- changed satellite assignment

without collapsing recurring lineage into anonymous acquisition IDs.

## Persisted Summary Shape

Each audit row now carries:

- `revision_id`
- `previous_revision_id`
- `mode_used`
- `diff_summary`

The full explainer JSON is also stored so the latest workspace-level explanation can be fetched without recomputing historical state from snapshots.

## Demo / Debug Surfaces

- `artifacts/demo/RESHUFFLE_EXPLAINER.json`
- `artifacts/demo/RESHUFFLE_EXPLAINER.md`
- `GET /api/v1/dev/reshuffle-explainer?workspace_id=<workspace_id>`
- `GET /api/v1/schedule/commit-history?workspace_id=<workspace_id>`

## Tests

Added:

- `tests/unit/test_reshuffle_explainer.py`
  - recurring lineage diff keeps `order_id/template_id/instance_key`
  - markdown renderer exposes revision summary and changed sections
- `tests/unit/test_schedule_commit_conflicts.py`
  - regular `/schedule/commit` persists revision summary and the dev explainer surface

Re-run:

- `tests/unit/test_lock_management.py -k 'create_audit_log or get_audit_logs or atomic_commit'`
- `tests/unit/test_recurring_order_lineage.py`

## Residual Notes

- Batch apply (`/api/v1/batches/{id}/commit`) still writes a commit audit log, but the primary reshuffle evidence work in this PR is focused on the schedule apply endpoints and auto-mode/repair flows listed in scope.
- The explainer stores the canonical latest artifact paths; the on-disk demo files are overwritten on each new apply, which is intentional for operator/demo inspection of the most recent revision.
