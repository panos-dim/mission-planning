# PR_SCHED_010 Checklist

## Goal

Implement the smallest safe Feasibility Results update needed to surface the new planning-demand contract without redesigning the panel.

## Scope

- Consume existing `mission_data.run_order`
- Consume existing `mission_data.planning_demands`
- Consume existing `mission_data.planning_demand_summary`
- Keep the current `MissionResultsPanel` shell
- Keep the current target timeline as the aggregate timeline
- Add only the minimum demand-aware summary/list needed for recurring-aware planning

## Non-goals

- No backend changes
- No scheduler changes
- No DB changes
- No dual-view redesign
- No Inspector redesign
- No Schedule / repair / reshuffle UX changes

## Files

- `frontend/src/components/MissionResultsPanel.tsx`
- `frontend/src/utils/planningDemand.ts` or a new small helper file
- `frontend/src/components/__tests__/MissionResultsPanel.test.tsx`

## Implementation checklist

### A) Demand-aware header

- [ ] Read `run_order`, `planning_demands`, and `planning_demand_summary` from `state.missionData`.
- [ ] When planning-demand data is present, replace the primary `X/Y targets` badge with `feasible_demands / total_demands`.
- [ ] Keep target count as a secondary supporting metric only.
- [ ] Show run-order name and order type in the results header.
- [ ] If the run order is recurring, show a compact recurrence badge or summary.
- [ ] Rename the current acquisition-window chip so it reads as a **global acquisition filter**, not generic demand timing.

### B) Minimal demand list

- [ ] Add a compact demand-aware section above the current timeline.
- [ ] Group recurring demands by `local_date`.
- [ ] For one-time-only runs, show a single `One-time demands` or `Current run` group rather than date groups.
- [ ] Each row must show:
  - target label
  - demand type
  - requested window
  - feasible / no opportunity status
  - matching pass count
- [ ] Clicking a row should navigate to `best_pass_index` when available.
- [ ] If `best_pass_index` is missing, fall back to the first item in `matching_pass_indexes`.
- [ ] Do not expose raw `demand_id`, `instance_key`, or `template_id` as the primary visible label.

### C) Reuse the current timeline

- [ ] Keep the existing per-target opportunity timeline.
- [ ] Rename the timeline section to `Master Timeline` or `Target Timeline`.
- [ ] Keep current target pills as filters for the timeline only.
- [ ] Do not treat target pills as the primary recurring-demand status model.
- [ ] Keep current tooltip and bar click behavior for aggregate pass inspection.

### D) Preserve current behavior for non-recurring runs

- [ ] One-time runs should still feel familiar after the change.
- [ ] If `planning_demands` is absent or empty, the panel should fall back gracefully to the current target/pass experience.
- [ ] Existing aggregate timeline interactions must continue working.

### E) Tests

- [ ] Add a test that renders demand-aware summary counts from `planning_demand_summary`.
- [ ] Add a test that renders recurring demand rows grouped by `local_date`.
- [ ] Add a test that clicking a demand row navigates to the correct pass.
- [ ] Keep or update current tests for:
  - stale target-filter reset behavior
  - acquisition-window chip rendering
  - empty-state behavior
  - constellation summary behavior

## Manual QA

1. One-time order with two targets:
   - Demand summary renders correctly.
   - Aggregate timeline still shows target lanes.
2. Daily recurring order over multiple dates:
   - Demand rows group by day.
   - Feasible and infeasible instances are obvious.
3. Recurring order where only some dates have opportunities:
   - Header counts show demand coverage, not just target coverage.
4. Target pills still filter the aggregate timeline without affecting demand grouping logic.
5. Clicking a demand row jumps the Cesium clock to the best available pass.
6. Acquisition-window copy clearly reads as a global run filter.

## Acceptance criteria

- Feasibility Results visibly consumes the existing planning-demand contract.
- Recurring runs no longer rely only on target-level coverage as the primary status signal.
- The current panel layout remains recognizable.
- The target timeline survives as the aggregate view.
- The PR stays frontend-only and avoids deep redesign.
