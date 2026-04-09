# PR_SCHED_007 Checklist

## Scope

Design and audit PR only.

- No feature implementation
- No scheduler algorithm changes
- No DB migrations
- No UI rewrite

## Inspected files list

### Backend and schemas

- `backend/main.py`
- `backend/order_materialization.py`
- `backend/scheduling_mode.py`
- `backend/schedule_persistence.py`
- `backend/time_windows.py`
- `backend/routers/orders.py`
- `backend/routers/order_templates.py`
- `backend/routers/schedule.py`
- `backend/schemas/mission.py`
- `backend/schemas/order_templates.py`

### Frontend

- `frontend/src/components/MissionPlanning.tsx`
- `frontend/src/components/MissionControls.tsx`
- `frontend/src/components/MissionParameters.tsx`
- `frontend/src/components/MissionResultsPanel.tsx`
- `frontend/src/components/SchedulePanel.tsx`
- `frontend/src/components/ScheduleTimeline.tsx`
- `frontend/src/components/OrdersPanel.tsx`
- `frontend/src/components/OrdersArea.tsx`
- `frontend/src/components/ObjectExplorer/Inspector.tsx`
- `frontend/src/context/MissionContext.tsx`
- `frontend/src/store/preFeasibilityOrdersStore.ts`
- `frontend/src/store/scheduleStore.ts`
- `frontend/src/store/visStore.ts`
- `frontend/src/utils/orderTemplateSync.ts`
- `frontend/src/utils/recurrence.ts`

### Existing docs and prior audits

- `docs/audits/AUDIT_RECURRING_ORDERS.md`
- `docs/audits/AUDIT_SCHEDULING_RESHUFFLE.md`
- `docs/audits/AUDIT_PARAMETER_GOVERNANCE_GAPS.md`
- `docs/audits/AUDIT_TIMELINE_REALISM.md`
- `docs/architecture/RECURRING_ORDER_LINEAGE.md`
- `docs/PARAMETER_GOVERNANCE_MATRIX.md`
- `docs/PR_UI_040_CHECKLIST.md`
- `docs/AUDIT_MISSION_PLANNER_READINESS.md`

## Core questions answered

- `Should Planning Horizon stay in Mission Parameters?`
  - Yes. It remains the authoritative run envelope.
- `Should recurring timing live only in Orders/templates?`
  - Yes. Recurrence pattern, local windows, timezone, and effective validity belong there.
- `Should one-time timing live in Orders?`
  - Yes. One-time requested windows are order-owned timing, not mission-owned timing.
- `Should Feasibility Results remain target-centric?`
  - No as the primary model. Keep target-centric only as an aggregate view.
- `Should Feasibility Results become demand-centric?`
  - Yes, as the actionable planning model.
- `Should one-time and recurring demands appear together?`
  - Yes. Both are planning demands and should share the same result and scheduling model.
- `Should there be two Feasibility modes?`
  - Yes. Default `Demand View` plus secondary `Master Timeline`.
- `How should schedule and reshuffle reason about work?`
  - By planning demand for action, by canonical target for grouping and geometry.

## Recommended UX model

- Default Feasibility Results to `Demand View`.
- Keep a secondary `Master Timeline` for aggregate target overview.
- Show one-time and recurring work in one common demand card model.
- Group recurring demand results by day to control noise.
- Use canonical target name as the main visible label.
- Show recurring lineage only as a secondary badge or in details.
- Keep Orders UI focused on authoring intent, not exploding every materialized recurring instance.

## Recommended time ownership model

- `Mission Parameters`
  - Owns the Planning Horizon for the current run.
- `Orders`
  - Own one-time requested windows and order-specific timing.
- `Recurring templates`
  - Own recurrence pattern, local recurring window, timezone, and effective validity dates.
- `Feasibility Results / Schedule / Cesium`
  - Own display-only range, zoom, pan, focus, and inspection state.
- `Mission-wide acquisition window`
  - Treat as an advanced global run filter only, not as demand timing.

## Phased implementation plan summary

### Phase 0

- Land this audit and decision record.

### Phase 1

- Align terminology around `planning demand`.
- Remove hidden second-horizon semantics from planning flows.

### Phase 2

- Normalize one-time and recurring work into a common demand model.
- Reuse existing recurring lineage fields instead of rewriting the scheduler.

### Phase 3

- Ship dual-view Feasibility Results with `Demand View` as default.

### Phase 4

- Normalize Schedule, reshuffle, and repair UX around demand-first actions and target-first grouping.

### Phase 5

- Hide or retire duplicate time controls that overlap with order timing.

## Risks and open questions

- Current feasibility still flattens frontend orders into targets, so one-time order timing is not yet first-class in analyze.
- Scheduling mode selection currently uses a hidden `now -> now+7d` horizon, which can diverge from the Mission Parameters horizon.
- Mission-wide acquisition window can duplicate order timing if it remains too prominent in the UI.
- Schedule timeline lanes still key heavily on `target_id`, which can surface per-instance planner identities as visual noise.
- Existing schedule and repair summaries still lean on target-oriented language even when recurring instances are already demand-like under the hood.
- The frontend currently hardcodes recurring template timezone handling to UTC in template sync.

## Recommended PR outcome

- Add the audit docs only.
- Treat this PR as the architectural decision point for recurring-aware planning and feasibility.
- Defer implementation to follow-up PRs that use the phased plan above.
