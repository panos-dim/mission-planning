# 100-Target and Reshuffle Reliability Audit

## Executive verdict

The current planning pipeline is materially more reliable after this audit pass.

The most important reliability defects found during the 100-target stress run were real and surgical to fix:

- incremental planning could replay an entire committed baseline when a newly added low-priority target had no feasible opportunities
- direct commits were dropping recurring lineage and audit mode metadata
- repair commits could crash while creating audit/explainer output
- direct-commit duplicate detection leaked across workspaces
- parallel feasibility could silently degrade to empty results after a broken process pool

Those defects are fixed in this PR, covered by regression tests, and validated against live end-to-end runs using the current backend/frontend pipeline.

One limitation remains documented rather than fixed:

- the import-only 100-target flow still produces a target-centric feasibility snapshot with `planning_demand_summary = null`, so demand-aware feasibility counts were validated by inspecting the raw analyzed opportunities instead of a dedicated summary payload

Recommendation: safe to use for MOD/demo after these fixes, with the above feasibility-summary limitation called out as remaining follow-up work rather than a blocker.

## Scenario/setup

### File used

The originally referenced external "real 100-target file" was not present in the repository or local workspace at audit time.

To keep the audit reproducible, this PR adds a checked-in deterministic fixture generated from the repo's seeded scalability data:

- `tests/fixtures/audit_100_targets.csv`

### Real execution path used

The live audit used the running application stack, not mocks:

1. import the 100-target CSV
2. run feasibility / mission analysis
3. generate a mission plan
4. apply the result
5. add new work or recurring work
6. re-run with auto-mode and inspect `from_scratch`, `incremental`, and `repair`
7. inspect schedule state, revision history, and reshuffle explainers

### Baseline scenario

- main baseline workspace: `b8d116c2-4859-4595-a014-f6023c4da26c`
- recurring-only verification workspace: `5068554e-6f6e-42b6-8800-fca65f2a9afb`
- low-priority incremental bug reproduction workspace: `68680115-d0de-45b0-b7ac-654a60a37922`
- post-fix low-priority incremental verification workspace: `741c5d61-e4da-4f80-b9be-515ddcef9281`
- satellite used by the audit scenario: `CUSTOM-45DEG-450KM`
- acquisition mode persisted in resulting acquisitions: `OPTICAL`
- observed pass envelope in analyzed data: `2026-04-10T00:07:28Z` through `2026-04-12T23:54:12Z`
- baseline analyzed targets: 100
- baseline analyzed opportunities: 194 passes

### Evidence captured

- `/tmp/audit_sched_011_trace.json`
- `/tmp/audit_sched_011_incremental_commit.json`
- `/tmp/audit_sched_011_modes.json`
- `/tmp/audit_sched_011_recurring_direct.json`
- workspace blobs in `data/workspaces.db`
- schedule commit history from `/api/v1/schedule/commit-history`
- reshuffle explainer artifacts in `artifacts/demo/RESHUFFLE_EXPLAINER.json` and `artifacts/demo/RESHUFFLE_EXPLAINER.md`

## Observed current behavior

### Baseline 100-target run

- auto-mode selected `from_scratch`
- reason: no active prior schedule revision existed
- 100 targets were present in workspace planning state
- 194 passes were generated
- 62 targets had at least one feasible pass in the analyzed opportunity set
- the scheduler produced 59 scheduled acquisitions
- apply created revision 2 with 59 added acquisitions

### High-priority new work after baseline

- adding `AUDIT_NEW_WORK` did not choose `incremental`
- auto-mode selected `repair`
- reason explicitly cited higher-priority new work versus existing best `P5` work at a 40% normalized priority weight
- repair preview reported `kept=59`, `added=3`, `dropped=0`, `moved=0`
- after apply, the workspace contained 62 acquisitions

### No-change rerun after absorbing that work

- auto-mode still selected `repair`
- this was believable because the high-priority outstanding work remained part of the scenario
- preview and committed diff both showed no fake churn:
  - `kept=62`
  - `added=0`
  - `dropped=0`
  - `moved=0`

### Recurring mixed case

- adding a recurring template on `SCALE_T0011` materialized 3 instances
- the mixed workspace still selected `repair` because high-priority one-time work was also outstanding
- mode-selection breadcrumbs reported:
  - `current_materialized_instance_count=3`
  - `outstanding_instance_count=3`
  - `new_instance_count=3`
- repair preview added 3 recurring acquisitions without dropping unrelated work

### Recurring-only case

- recurring-only mode selection chose `incremental`
- reason: `Detected 3 new recurring instance(s) and 0 new one-time/target addition(s). Planning incrementally around 59 committed acquisition(s).`
- planning returned exactly 3 schedule items
- planner target IDs were materialized instance IDs:
  - `tmpl_98311c4f00d7::2026-04-10`
  - `tmpl_98311c4f00d7::2026-04-11`
  - `tmpl_98311c4f00d7::2026-04-12`
- direct commit persisted:
  - `template_id`
  - `instance_key`
  - recurring acquisitions count `3`

## Bug list

| Bug | Reproducible symptom | Root cause | Fix applied | Status |
| --- | --- | --- | --- | --- |
| Incremental replayed the baseline when new low-priority work had no opportunities | Workspace `68680115-d0de-45b0-b7ac-654a60a37922` showed revision 3 adding 59 duplicate acquisitions under `incremental` | `/api/v1/planning/schedule` compared against opportunity target IDs only, so a newly added target with zero opportunities never survived into `new_target_ids` filtering | `backend/main.py` now builds current target IDs from the union of mission-scope targets and opportunity target IDs | Fixed |
| Repair apply could 500 while writing audit/explainer data | `mode_used` / revision variables were referenced before initialization in repair commit flow | Repair commit audit bookkeeping was initialized too late | `backend/routers/schedule.py` now initializes `previous_revision_id`, `before_acquisitions`, and `mode_used` before audit/explainer creation | Fixed |
| Direct commit dropped recurring lineage | recurring direct commits produced acquisitions without `template_id` / `instance_key` lineage | frontend direct-commit payload omitted recurring lineage fields | frontend commit payload and backend request model were expanded to carry recurring lineage fields through `plan_items` and acquisitions | Fixed |
| Direct commit audit always looked like `direct_commit` | commit history / explainers lost the real planning mode behind direct apply | frontend direct commit did not send the chosen planning mode through to the backend | frontend and backend now persist explicit `planning_mode` on direct commits | Fixed |
| Repair-added recurring instances lost lineage | recurring items introduced by repair could appear as generic additions | repair flow did not persist recurring lineage for added opportunities | repair commit now copies recurring lineage from planner metadata into `plan_items` | Fixed |
| Duplicate direct-commit detection leaked across workspaces | identical payloads in different workspaces could be rejected as duplicates | duplicate-plan lookup ignored workspace scoping | `_find_existing_direct_commit_plan()` now scopes by effective workspace | Fixed |
| Broken process pool could silently collapse feasibility | parallel visibility execution could fail into misleading empty results | `BrokenProcessPool` handling did not force a visible fallback path | `src/mission_planner/parallel.py` now re-raises and tears down the pool so the caller falls back to serial evaluation | Fixed |
| Import-only feasibility path does not expose demand-aware summary counts | `planning_demand_summary` is `null` in the 100-target file-import analysis snapshot | file import still feeds a target-centric analysis model rather than a normalized demand summary payload | no code change in this PR; counts were validated directly from `analysis_state_json` instead | Deferred and documented |

## Pipeline invariant checks

| Invariant | Result | Evidence |
| --- | --- | --- |
| Single run-order remains correct | Pass for the audited file-import path | the import flow produced one analyzed target set and one baseline schedule per run; no duplicate run-order payloads were observed |
| All imported targets are preserved | Pass | baseline workspaces persisted 100 imported targets in `planning_state_json.current_target_ids` |
| Recurring and one-time work can coexist | Pass | mixed workspace `b8d116c2-4859-4595-a014-f6023c4da26c` carried high-priority one-time work plus 3 recurring instances |
| No duplicate recurring demand generation | Pass | recurring instance keys persisted once each for `2026-04-10`, `2026-04-11`, and `2026-04-12` |
| No missing joins across `target_id` / `canonical_target_id` / `planner_target_id` / recurring lineage | Pass after fixes | direct and repair commits now preserve `canonical_target_id`, `template_id`, `instance_key`, and planner target identities |
| Opportunity generation works across the 100-target input | Pass | 194 passes were generated; 62 distinct targets had at least one opportunity in the 100-target baseline analysis |
| No silent target drops in feasibility | Pass | 100 imported targets remained present in workspace planning state; infeasible targets were absent from the pass set but not silently removed from the target set |
| Horizon and time-window filters apply consistently | Pass for observed runs | all analyzed and scheduled timestamps stayed inside the observed 3-day audit envelope |
| Demand-aware summary counts match actual opportunities | Partial | import-only analysis snapshots still omit `planning_demand_summary`; actual opportunity counts were verified by reading `analysis_state_json` directly |
| Planning does not collapse recurring instances into one target | Pass | recurring schedule returned 3 distinct planner target IDs, one per materialized date |
| Scheduler output is deterministic for the same input | Pass in no-change rerun | stable repair preview and commit both reported `kept=62`, `added=0`, `dropped=0`, `moved=0` |
| Auto-mode chooses a believable mode and logs why | Pass | live mode-selection responses and breadcrumbs explained `from_scratch`, `incremental`, and `repair` choices with counts and reasons |
| Schedule rows write to the correct workspace | Pass after fix | duplicate detection regression test now allows identical payloads in different workspaces |
| Revisions increase correctly | Pass | observed revision chains: `2 -> 3 -> 4 -> 5` for the main audit workspace and `2 -> 3` for the recurring-only workspace |
| Apply does not merge stale schedule state incorrectly | Pass after fix | no-change rerun kept 62 acquisitions unchanged; recurring-only incremental apply added only 3 new acquisitions |
| Incremental does not duplicate existing acquisitions | Pass after fix | post-fix live verification for workspace `741c5d61-e4da-4f80-b9be-515ddcef9281` returned `schedule_count=0` for infeasible new low-priority work |
| Repair does not wipe unrelated acquisitions | Pass | repair previews kept all prior acquisitions while adding only the new work required |

## Reshuffle correctness findings

- The reshuffle explainer diff matched the actual committed schedule changes for the audited repair cases.
- High-priority new work produced an explainable repair diff of `59 kept / 3 added / 0 dropped / 0 moved`.
- No-change rerun produced an explainable zero-change diff of `62 kept / 0 added / 0 dropped / 0 moved`.
- Mixed recurring plus high-priority work produced `62 kept / 3 added / 0 dropped / 0 moved`.
- Repair did not wipe unrelated acquisitions in any audited case.
- Recurring instances appeared as real new work in both the preview and persisted acquisitions once lineage persistence was fixed.

## Mode-selection findings

| Scenario | Expected mode | Observed mode | Verdict |
| --- | --- | --- | --- |
| Fresh 100-target baseline | `from_scratch` | `from_scratch` | Correct |
| New low-priority one-time target with no feasible opportunities | `incremental` | `incremental` | Correct after fix |
| New high-priority one-time target | `repair` | `repair` | Correct |
| Recurring-only new instances | `incremental` | `incremental` | Correct |
| Mixed high-priority one-time plus recurring instances | `repair` | `repair` | Correct |

The important edge-case fix here was not mode selection itself. Auto-mode was already choosing `incremental` for low-priority additive work. The real bug was that the incremental planner could still replay the committed baseline when that new work had zero opportunities. That backend behavior is now aligned with mode selection.

## Recurring-demand findings at scale

- recurring materialization remained stable at 3 instances over the audited 3-day horizon
- recurring planner target IDs were date-specific and traceable
- recurring direct commit now preserves:
  - `template_id`
  - `instance_key`
  - `canonical_target_id`
  - `display_target_name`
  - `planning_mode`
- repair apply now preserves recurring lineage for newly added recurring items as well
- recurring-only incremental apply produced revision 3 with `added=3` and `kept=59`, which is the expected behavior for materialized recurring work

## Performance findings

- baseline 100-target analyze + scheduling flow completed locally in about `0.76s`
- the high-priority repair rerun completed locally in about `0.82s`
- no large-input UI payload collapse or silent frontend assumption failure was observed during the audited runs
- the main performance-related reliability issue found was not raw speed but failure visibility: `BrokenProcessPool` could previously degrade feasibility silently, which is now fixed to force a safe fallback

These timings are local-dev observations, not production benchmarks.

## Final recommendation / remaining risks

This PR should be accepted as the highest-value reliability pass before demo use.

The fixes are targeted, test-backed, and tied to real failures observed under the 100-target stress case. Auto-mode is now explainable for `from_scratch`, `incremental`, and `repair`; reshuffle diffs are believable; recurring instances persist as first-class scheduled work; and the most dangerous duplication failure in incremental mode has been removed.

Remaining risks:

- the audit used a checked-in deterministic 100-target fixture because the originally referenced external file was unavailable locally
- import-only feasibility snapshots still do not populate `planning_demand_summary`, so demand-aware summary verification in this path required raw opportunity inspection
- performance findings are strong enough for demo confidence, but they are not a substitute for a dedicated longer-horizon benchmark pass
