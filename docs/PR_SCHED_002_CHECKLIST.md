# PR_SCHED_002 Checklist

**Title**: Recurring Orders Foundation
**Goal**: Add the backend and API foundation for recurring orders without adding UI noise or changing scheduler algorithms
**Reference**: `docs/audits/AUDIT_RECURRING_ORDERS.md`

---

## Locked Architecture Decisions

- [ ] Recurrence lives in a separate `order_templates` entity, not on `Target`
- [ ] Existing `orders` rows represent dated actionable instances
- [ ] Recurring instances are materialized per planning horizon window
- [ ] Each dated instance gets a unique `planner_target_id`
- [ ] `acquisitions.order_id` points to the dated instance
- [ ] `template_id` is persisted separately on plan items and acquisitions
- [ ] Existing scheduler algorithms remain unchanged
- [ ] Generated instances stay backend-managed and hidden by default in UI
- [ ] `backend.time_windows.DailyTimeWindow` is reused for recurrence windows

---

## Backend Persistence Checklist

- [ ] Add `order_templates` table
- [ ] Add `template_id` to `orders`
- [ ] Add `instance_key` to `orders`
- [ ] Add `instance_local_date` to `orders`
- [ ] Add `planner_target_id` to `orders`
- [ ] Add `canonical_target_id` to `orders`
- [ ] Add `target_lat` and `target_lon` to `orders`
- [ ] Add `expired` to the normalized order-status vocabulary
- [ ] Add unique protection on `(template_id, instance_key)`
- [ ] Add `template_id` to `plan_items`
- [ ] Add `instance_key` to `plan_items`
- [ ] Add `canonical_target_id` to `plan_items`
- [ ] Add `display_target_name` to `plan_items`
- [ ] Add `template_id` to `acquisitions`
- [ ] Add `instance_key` to `acquisitions`
- [ ] Add `canonical_target_id` to `acquisitions`
- [ ] Add `display_target_name` to `acquisitions`
- [ ] Verify snapshots/rollback preserve new acquisition columns

---

## API Checklist

- [ ] Add template CRUD endpoints under `/api/v1/order-templates`
- [ ] Extend order responses with instance/template lineage fields
- [ ] Extend order list filters with `template_id`, `instance_from`, `instance_to`, `include_expired`
- [ ] Extend planning preview responses with `order_id`, `template_id`, `instance_key`, `canonical_target_id`
- [ ] Extend schedule/master-schedule responses with recurring lineage fields
- [ ] Ensure workspace export/import includes templates and materialized instances

---

## Materialization Checklist

- [ ] Build a horizon-based recurring-instance materializer
- [ ] Materialize only instances overlapping the requested planning horizon
- [ ] Reuse deterministic `instance_key` generation
- [ ] Use insert-ignore/upsert semantics to prevent duplicate generation
- [ ] Mark stale unfulfilled instances as `expired`
- [ ] Support `daily` recurrence
- [ ] Support `weekly` recurrence
- [ ] Support midnight-crossing windows
- [ ] Require explicit IANA timezone on templates

---

## Planning Integration Checklist

- [ ] Keep mission feasibility target-centric for canonical targets
- [ ] Reuse cached canonical opportunities/passes rather than recomputing per instance
- [ ] Build instance-scoped planning opportunities by cloning/filtering canonical feasible opportunities
- [ ] Rewrite scheduler-facing `target_id` to the instance `planner_target_id`
- [ ] Propagate `order_id` and `template_id` into persisted plan items
- [ ] Propagate `order_id` and `template_id` into committed acquisitions
- [ ] Stop assuming planner `target_id` is the operator-facing target label
- [ ] Update auto-mode selection to reason about newly materialized instance targets
- [ ] V1 behavior: if new recurring instances enter the horizon, choose `from_scratch`
- [ ] Keep `repair` scoped to already materialized instance targets and lock/conflict adjustments

---

## Frontend Checklist

- [ ] Introduce `OrderTemplate` and `OrderInstance` frontend types
- [ ] Add a minimal recurrence block to the order editor
- [ ] Keep recurrence controls collapsed until enabled
- [ ] Support `One-time` vs `Repeats`
- [ ] Support `Daily` vs `Weekly`
- [ ] Add weekday picker for weekly
- [ ] Add local start/end time inputs
- [ ] Add timezone input/select
- [ ] Show one compact recurrence summary chip on order cards
- [ ] Hide generated instances by default
- [ ] Stop using `plan_id` as a fallback order identity when real lineage exists
- [ ] Keep timeline/schedule surfaces focused on acquisitions, not instance administration

---

## Verification Scenarios

- [ ] Daily recurring order creates one instance per local day in horizon
- [ ] Weekly recurring order creates instances only on selected weekdays
- [ ] Midnight-crossing window (`22:00-02:00`) creates the correct UTC window
- [ ] Re-running materialization for the same horizon does not duplicate instances
- [ ] New instance entering horizon causes expected planning mode selection
- [ ] Repair mode preserves existing locked acquisitions for already materialized instances
- [ ] Instance-aware planning can schedule the same physical target on multiple dates
- [ ] Acquisition rows retain `order_id` and `template_id` after commit
- [ ] Snapshot rollback restores recurrence lineage correctly
- [ ] Workspace save/load/export/import preserves templates and instances
- [ ] Expired unfulfilled instances are not regenerated indefinitely
- [ ] Non-UTC timezone templates behave correctly around local date boundaries
- [ ] Global mission `acquisition_time_window` and template window intersect correctly when both are set

---

## Evidence to Capture

- [ ] Example template payload for daily recurrence
- [ ] Example template payload for weekly recurrence
- [ ] Example materialized instance row
- [ ] Example plan item carrying recurrence lineage
- [ ] Example committed acquisition carrying recurrence lineage
- [ ] Example snapshot/rollback before-and-after with recurrence fields
- [ ] Example UI recurrence summary chip

---

## Explicitly Out of Scope

- [ ] No scheduler algorithm redesign
- [ ] No monthly/yearly RRULE support in v1
- [ ] No exception-calendar / holiday-blackout system in v1
- [ ] No bulk instance-management screen in v1
- [ ] No major timeline or map redesign in v1

---

## Done Definition

- [ ] Audit recommendation remains true in code: template -> instance -> plan item -> acquisition
- [ ] A recurring order can produce multiple dated acquisitions for the same physical target without identity collisions
- [ ] Schedule history, rollback, and workspace portability preserve recurring lineage
- [ ] UI remains compact and does not expose generated-instance noise by default
