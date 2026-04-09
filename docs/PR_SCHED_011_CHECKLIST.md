# PR_SCHED_011 Checklist

## File used / scenario description

- primary file: `tests/fixtures/audit_100_targets.csv`
- audit style: live end-to-end backend/frontend behavior, not mock-only testing
- baseline workspace: `b8d116c2-4859-4595-a014-f6023c4da26c`
- recurring-only verification workspace: `5068554e-6f6e-42b6-8800-fca65f2a9afb`
- incremental bug reproduction workspace: `68680115-d0de-45b0-b7ac-654a60a37922`
- post-fix incremental verification workspace: `741c5d61-e4da-4f80-b9be-515ddcef9281`
- satellite used: `CUSTOM-45DEG-450KM`
- observed analyzed pass envelope: `2026-04-10T00:07:28Z` through `2026-04-12T23:54:12Z`

## Invariant checklist

| Check | Result | Notes |
| --- | --- | --- |
| 100 imported targets preserved through workspace state | Pass | 100 targets persisted in baseline planning state |
| Opportunity generation does not silently drop the file input | Pass | 194 passes generated; 62 distinct targets had opportunities |
| Scheduler baseline is explainable | Pass | `from_scratch` with explicit reason and 59 scheduled acquisitions |
| High-priority new work reshuffles instead of quietly appending | Pass | auto-mode selected `repair` and added 3 acquisitions |
| No-change rerun avoids fake churn | Pass | `62 kept / 0 added / 0 dropped / 0 moved` |
| Recurring instances behave like real new work | Pass | recurring-only incremental run scheduled exactly 3 dated items |
| Recurring lineage persists through commit | Pass | `template_id` and `instance_key` persisted for direct and repair flows |
| Incremental does not duplicate committed baseline when new work is infeasible | Pass after fix | post-fix live verification returned `schedule_count=0` |
| Cross-workspace direct-commit dedupe is isolated | Pass after fix | identical payloads may commit in different workspaces |
| Demand-aware feasibility summary is available in import-only path | Deferred | file-import analysis still leaves `planning_demand_summary = null` |

## Bug table

| Bug | Outcome |
| --- | --- |
| Incremental replayed baseline when a new target had no feasible opportunities | Fixed in `backend/main.py` |
| Repair commit crashed while building audit/explainer output | Fixed in `backend/routers/schedule.py` |
| Direct commit dropped recurring lineage | Fixed across frontend commit payload and backend request handling |
| Direct commit audit lost the actual planning mode | Fixed across frontend commit payload and backend persistence |
| Repair-added recurring items lost lineage | Fixed in `backend/routers/schedule.py` |
| Duplicate direct-commit detection leaked across workspaces | Fixed in `backend/routers/schedule.py` |
| Parallel feasibility could fail silently after broken process pool | Fixed in `src/mission_planner/parallel.py` |
| Import-only feasibility omits demand-aware summary payload | Documented as deferred |

## Regression tests added

- `tests/unit/test_recurring_order_materialization.py`
  - `test_direct_commit_preserves_recurring_lineage_from_planning_schedule`
  - `test_repair_commit_preserves_recurring_lineage_for_added_instances`
- `tests/unit/test_schedule_commit_conflicts.py`
  - `test_direct_commit_persists_explicit_planning_mode_in_audit_explainer`
  - `test_repair_commit_persists_repair_mode_in_audit_explainer`
  - `test_direct_commit_allows_identical_payload_in_different_workspaces`
  - `test_incremental_with_no_new_target_opportunities_does_not_replay_baseline`
- `tests/unit/test_parallel.py`
  - `test_get_visibility_windows_reraises_broken_process_pool`
- `tests/unit/test_visibility_core.py`
  - `test_parallel_broken_pool_falls_back_to_serial`

## Revision diff evidence

### Main audit workspace `b8d116c2-4859-4595-a014-f6023c4da26c`

- revision 2: `from_scratch`, `added=59`
- revision 3: `repair`, `added=3`, `kept=59`
- revision 4: `repair`, `added=0`, `kept=62`
- revision 5: `repair`, `added=3`, `kept=62`

### Recurring-only workspace `5068554e-6f6e-42b6-8800-fca65f2a9afb`

- revision 2: `from_scratch`, `added=59`
- revision 3: `incremental`, `added=3`, `kept=59`

### Incremental bug reproduction workspace `68680115-d0de-45b0-b7ac-654a60a37922`

- revision 3 previously showed the bug: `incremental` added 59 duplicate acquisitions and inflated `after_count` to 118
- post-fix live verification on workspace `741c5d61-e4da-4f80-b9be-515ddcef9281` returned `schedule_count=0` for the same class of infeasible low-priority additive work

## Auto-mode evidence

| Scenario | Observed mode | Evidence |
| --- | --- | --- |
| Baseline 100-target file | `from_scratch` | mode-selection reason cited no existing active schedule |
| Low-priority additive one-time work | `incremental` | mode-selection reason cited `1 new one-time/target addition` |
| High-priority additive one-time work | `repair` | reason cited better priority than current baseline |
| Recurring-only new instances | `incremental` | reason cited `3 new recurring instance(s)` |
| Mixed recurring plus high-priority work | `repair` | reason remained priority-driven repair |

## Final pass/fail summary

- Live 100-target flow executed end to end: Pass
- Concrete bugs found and fixed or documented: Pass
- Reproducible audit doc created: Pass
- Checklist doc created: Pass
- Regression tests added for real bugs: Pass
- Reshuffle behavior explainable via revision diffs: Pass
- Auto-mode behavior validated for `from_scratch`, `incremental`, and `repair`: Pass
- Backend verification sweep: `116 passed`
- Frontend verification: `npx tsc --noEmit` passed

Overall verdict: Pass, with one documented deferred limitation for the import-only demand-aware feasibility summary path.
