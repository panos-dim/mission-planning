# PR_SCHED_012 Checklist

## Screenshots

### One-time inspector state
Screenshot: pending manual capture in the running planner UI.

Notes:
- Select a one-time demand from Feasibility Results.
- Confirm the Inspector shows target, demand type, requested/run window, feasibility status, best opportunity, and acquisitions.

### Recurring inspector state
Screenshot: pending manual capture in the running planner UI.

Notes:
- Select a recurring demand instance from Feasibility Results.
- Confirm the Inspector shows the recurring summary plus the instance date without exposing raw backend IDs.

### No-opportunity empty state
Screenshot: pending manual capture in the running planner UI.

Notes:
- Select a demand with no feasible opportunities.
- Confirm the Best Opportunity section shows `No feasible opportunities in current planning horizon`.

### Acquisitions list state
Screenshot: pending manual capture in the running planner UI.

Notes:
- Select a demand or scheduled acquisition with committed work in the current schedule window.
- Confirm the Acquisitions section is chronological and shows start time, satellite, and off-nadir angle.

## Selection Flow Notes

- Feasibility Results demand rows now select a demand-aware target context in the Inspector. If a best pass exists, the click also jumps the mission clock to that pass window.
- Feasibility pass bars now resolve the most likely planning demand for that target/time, then update the Inspector before jumping to the pass window.
- Schedule timeline acquisition clicks now resolve the matching demand context first, then focus the acquisition. When no demand match is available, the UI falls back to plain acquisition selection.
- Demand-aware target and acquisition selections keep the Inspector grounded in readable labels such as target name, demand type, recurrence summary, and requested window instead of raw template or instance identifiers.

## Polling Persistence Notes

- Schedule polling persistence still keys off the selected acquisition id.
- If a polling refresh returns the same acquisition id, the timeline highlight and Inspector selection remain intact.
- If the acquisition disappears from the refreshed schedule, the selection is cleared to avoid stale Inspector content.
- Demand context is rehydrated from the selected acquisition plus current planning-demand windows, which keeps recurring-instance context stable when the acquisition still exists.

## Manual Verification Results

1. Select a one-time target in Feasibility Results.
Result: Automated coverage added for demand selection plus pass jump. Manual browser verification and screenshot capture are still pending.

2. Select a recurring demand.
Result: Automated coverage added for recurring-demand matching and demand-aware selection. Manual browser verification and screenshot capture are still pending.

3. Select a target/demand with no opportunities.
Result: Automated coverage added for inspectable no-opportunity demands and clean empty-state messaging. Manual browser verification and screenshot capture are still pending.

4. Click a scheduled acquisition in Schedule.
Result: Implemented in the schedule timeline flow. Manual browser verification is still pending.

5. Let polling refresh happen and confirm the selection remains if the item still exists.
Result: Existing acquisition-id persistence path is preserved and demand context now rehydrates from the surviving acquisition. Manual browser verification is still pending.

6. Build passes.
Result: Confirmed on 2026-04-09 with `npm run build` and targeted `vitest` coverage for Mission Results, Schedule Panel wiring, and planning-demand helpers.
