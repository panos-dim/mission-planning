# Audit: Recurring Orders Architecture

**Date**: 2026-04-02
**Status**: Audit + implementation-ready design
**Scope**: Order model, feasibility inputs, schedule persistence, incremental/repair behavior, daily time-window reuse, minimal UI
**Related docs**:
- `docs/audits/AUDIT_SCHEDULING_RESHUFFLE.md`
- `docs/PR_UI_040_CHECKLIST.md`

---

## 1. Executive Verdict

Recurring orders are **not feasible with the current architecture as-is** if they reuse the same planner-visible `target_id`.

The main blocker is identity, not recurrence math:

- feasibility is target-centric, not order-centric
- the scheduler only schedules one opportunity per `target_id`
- incremental/repair logic dedupes by `target_id`
- the schedule router skips future opportunities for already-scheduled `(satellite_id, target_id)` pairs
- persisted acquisitions only know about a single `order_id`, with no recurring lineage

Recurring orders become feasible **without scheduler algorithm changes** if the system adopts this model:

1. store recurrence in a separate order-template entity
2. materialize dated instances per planning horizon window
3. give each dated instance its own planner-visible target identity
4. persist template/instance lineage through plan items and acquisitions

The cleanest near-term path is:

- keep feasibility target-centric
- keep the scheduler unchanged
- make recurring instances look like ordinary dated orders to planning and commit

---

## 2. Current Architecture Summary

## 2.1 Orders and Persistence

- `backend/schedule_persistence.py` stores `orders` as single requests with `target_id`, priority, optional requested window, and PS2.5 workflow fields.
- The `orders` table has **no recurrence rule**, **no template linkage**, and **no target geometry**.
- `backend/routers/orders.py` exposes backend order CRUD/import, but the main create path still reflects one-time orders.
- Order status semantics are already inconsistent across files (`new`, `planned`, `committed`, `cancelled`, `completed` vs comments mentioning `queued`, `rejected`, `expired`).

## 2.2 Feasibility Inputs

- `POST /api/v1/mission/analyze` consumes `targets[]`, not orders.
- `backend/schemas/target.py` defines a target as geometry plus presentation/priority fields.
- `backend/main.py` caches mission passes/opportunities keyed by target name, and that target name becomes planner `target_id`.
- Current frontend pre-feasibility orders (`frontend/src/store/preFeasibilityOrdersStore.ts`) are only local grouping; `frontend/src/components/MissionControls.tsx` flattens all targets from all pre-feasibility orders into one `targets[]` payload.

## 2.3 Scheduling and Repair

- There are effectively two planning paths today:
  - `POST /api/v1/planning/schedule` in `backend/main.py`
  - `POST /api/v1/schedule/repair` and related schedule endpoints in `backend/routers/schedule.py`
- `src/mission_planner/scheduler.py` explicitly tracks `covered_targets` / `scheduled_targets` and only selects one opportunity per `target_id`.
- `backend/incremental_planning.py` repair logic also operates on `target_id` coverage and contains explicit per-target dedup stages.
- `backend/routers/schedule.py` filters out opportunities when the same `(satellite_id, target_id)` is already scheduled in the future.

## 2.4 Schedule Persistence and Snapshots

- `plan_items` optionally store `order_id`, but no recurring lineage.
- `acquisitions` optionally store `order_id`, but no recurring lineage.
- `schedule_snapshots` store full acquisition rows as JSON and rollback reinserts columns dynamically.
- This is important: if recurrence lineage is added to acquisition rows, snapshots will preserve it automatically without a new snapshot table design.

## 2.5 Workspace and UI Persistence

- Frontend “accepted orders” are not normalized backend orders. They are UI wrappers stored in Zustand/local storage and saved into workspace `orders_state`.
- `frontend/src/utils/recoveredOrders.ts` rebuilds “orders” by grouping schedule items via `order_id || plan_id`.
- `backend/routers/workspaces.py` still saves/loads `orders_state` as a frontend blob and migrates legacy blobs into acquisitions, not into a recurring-order model.

## 2.6 Daily Acquisition Time Window

- `backend/time_windows.py` already implements a strong reusable primitive:
  - `HH:MM` parsing
  - IANA timezone validation
  - midnight-crossing windows
  - local-time comparison against UTC datetimes
- `backend/schemas/mission.py` and `backend/main.py` use it as a **mission-wide feasibility filter**.
- This is reusable for recurring-order windows, but it should not become the recurrence source of truth by itself because recurrence is per template, not per mission.

---

## 3. Gap Analysis

| Area | Current state | Gap | Why it matters |
| --- | --- | --- | --- |
| Recurrence source of truth | No template entity exists | No place to store daily/weekly recurrence cleanly | Recurrence would be scattered across UI-only order groups or overloaded one-time orders |
| Actionable order identity | `orders` represent one-time requests | No stable notion of a dated recurring instance | Planning, commit, and rollback need a concrete occurrence ID |
| Geometry ownership | Backend `orders` do not store target lat/lon | Order instances cannot independently drive planning filters | A recurring instance must know which physical target it refers to |
| Planner identity | Scheduler and repair dedupe on `target_id` | Same physical target cannot be requested repeatedly in horizon | Recurring daily/weekly instances would collapse into one scheduled target |
| Schedule lineage | `plan_items` and `acquisitions` only know `order_id` | No template/instance relationship in commit history | Operators cannot trace an acquisition back to a recurring source |
| Auto-mode behavior | Mode selection reasons about targets and schedule state | New recurring instances are invisible or misclassified | Repair/incremental cannot safely absorb recurring arrivals today |
| Workspace portability | Workspaces persist accepted-order blobs and acquisitions | Recurring templates would not round-trip cleanly | Save/load/export/import would drift from backend truth |
| UI cleanliness | Pre-feasibility orders and accepted orders are already split concepts | A naive recurring implementation would add a third visible concept | Mission planner UI would get noisier instead of cleaner |
| Timezone handling | Daily window helper exists, UI currently defaults to UTC | Recurring templates need explicit per-template timezone semantics | Daily/weekly rules become wrong around local day boundaries |

---

## 4. Direct Answers to the Audit Questions

## 4.1 Where should recurrence live?

Recurrence should live in a **separate order-template entity**, not on `Target`, and not directly on the existing `orders` rows.

Reasoning:

- `Target` is a physical site / geometry concept.
- Existing `orders` already look like dated, actionable requests and should stay that way.
- A template entity cleanly represents “repeat this business intent over time.”

Recommended model:

- `order_templates` = recurring business definition
- `orders` = dated actionable instances

For one-time orders, `orders.template_id = NULL`.

## 4.2 When should recurring orders expand?

Recurring orders should expand **per planning horizon window**, with idempotent materialization into dated instances.

Not recommended:

- **Creation-time expansion**: unbounded row growth and no natural stop point
- **Feasibility-time-only expansion**: no stable instance IDs for commit, rollback, or audit

Recommended:

- on plan generation for horizon `[from, to]`, materialize all missing instances whose local windows intersect that horizon
- persist them in `orders`
- reuse them across preview, commit, repair, rollback, and reporting

## 4.3 What new IDs and fields are required?

Minimum new identities:

- `template_id`: recurring template identity
- `order_id`: dated instance identity
- `instance_key`: deterministic occurrence key per template, used for idempotent generation
- `planner_target_id`: unique scheduler-facing identity for that instance
- `canonical_target_id`: physical target identity for UI, grouping, and reuse of feasibility results

Minimum new template fields:

- `id`
- `workspace_id`
- `name`
- `status` (`active | paused | ended`)
- `canonical_target_id`
- `target_lat`
- `target_lon`
- `priority`
- `constraints_json`
- `requested_satellite_group`
- `recurrence_type` (`daily | weekly`)
- `interval`
- `days_of_week_json` (weekly only)
- `window_start_hhmm`
- `window_end_hhmm`
- `timezone_name`
- `effective_start_date`
- `effective_end_date`
- `notes`
- `external_ref`

Minimum new instance/order fields:

- `template_id` nullable
- `instance_key`
- `instance_local_date`
- `planner_target_id`
- `canonical_target_id`
- `target_lat`
- `target_lon`
- `expires_at` or reuse `requested_window_end` plus harmonized `expired` status

## 4.4 How should schedule persistence link acquisitions back to template / instance / original order?

The cleanest design is to avoid three parallel order concepts:

- `order_templates.id` = recurring template
- `orders.id` = dated instance / actionable order
- `acquisitions.order_id` = instance ID
- `acquisitions.template_id` = template ID when applicable

That means the “original order” for a recurring occurrence is the **materialized instance row**. The template is linked separately.

Recommended persistence fields on `plan_items` and `acquisitions`:

- `order_id` = dated instance ID
- `template_id`
- `instance_key`
- `canonical_target_id`
- `display_target_name`

Keep existing `target_id` in `plan_items` and `acquisitions` as the planner-facing identity for backward compatibility, but stop treating it as the only operator-facing target name.

## 4.5 How will incremental / repair behave when new recurring instances appear?

**Today:** not safely.

Current blockers:

- repair logic dedupes by `target_id`
- current mode selection reasons about “new targets” in ways that do not include recurring-instance lineage
- new recurring instances are not first-class requested objects today

Recommended v1 behavior:

- when a template materializes new instances inside the planning horizon, treat them as **new planner targets**
- choose **`from_scratch`** for those runs
- keep `repair` for adjusting already materialized instances and preserving locks

Recommended later behavior:

- once instance-aware request assembly is in place, `incremental` can treat a newly materialized instance exactly like a new target
- `repair` should remain a schedule-adjustment mode, not the first expansion path for new recurring work

## 4.6 What is the minimum clean UI?

Minimum clean UI:

- no new top-level recurring dashboard
- no visible list of auto-generated instances by default
- one optional recurrence section in the order editor:
  - `One-time` or `Repeats`
  - `Daily` or `Weekly`
  - weekday picker for weekly
  - local time window
  - timezone
- one compact summary chip on the order card:
  - `Daily 15:00-17:00 Asia/Dubai`
  - `Mon/Wed/Fri 09:00-11:00 UTC`

Generated instances should remain backend-managed and only appear in operator UI when inspecting history or a specific acquisition lineage.

---

## 5. Recommended Recurring-Order Model

## 5.1 Entity Model

```text
Canonical Target (physical site)
        |
        v
Order Template (recurring definition)
        |
        v
Materialized Order Instance (dated actionable order)
        |
        v
Plan Item
        |
        v
Acquisition
```

Key principle:

- the template is the recurring business intent
- the instance is the thing the planner actually schedules

## 5.2 Why the Existing `orders` Table Should Represent Instances

The current `orders` table already looks like a dated request:

- requested window start/end
- priority
- constraints
- status transitions
- batch/inbox workflow fields

That is much closer to a materialized recurring instance than to a recurrence template.

Recommended interpretation going forward:

- `orders` remain actionable, dated work items
- recurring behavior is introduced above them via `order_templates`

## 5.3 How Feasibility Should Integrate

Do **not** make mission feasibility fully order-aware in v1.

Instead:

1. Keep feasibility target-centric for canonical physical targets.
2. Cache passes/opportunities once per canonical target.
3. Before planning, materialize recurring instances for the planning horizon.
4. Build instance-scoped opportunities by:
   - selecting feasible opportunities for the canonical target
   - filtering them to the instance requested window
   - rewriting planner `target_id` to the instance `planner_target_id`
   - attaching `order_id` and `template_id` lineage

Why this is the cleanest path:

- no scheduler algorithm change
- no duplicate orbital analysis per recurring instance
- no recurrence logic inside `mission/analyze`
- direct reuse of existing target geometry and pass generation

## 5.4 Why a Unique `planner_target_id` Is Required

This is the most important design choice.

The current planner assumes one scheduleable unit per `target_id`. Therefore:

- one physical target requested on three different days cannot reuse the same planner `target_id`
- each dated recurring instance needs its own planner-visible identity

Example:

- canonical target: `KUWAIT_PORT`
- template: `tmpl_01`
- dated instance for 2026-04-05 local date:
  - `order_id = ord_abc123`
  - `planner_target_id = tmpl_01::2026-04-05`
  - `canonical_target_id = KUWAIT_PORT`

The scheduler only sees `planner_target_id`.
The UI mostly shows `canonical_target_id` / display name plus recurrence summary.

---

## 6. Proposed API and Data Model Changes

## 6.1 New Backend Entity

Add a new template surface:

- `POST /api/v1/order-templates`
- `GET /api/v1/order-templates`
- `GET /api/v1/order-templates/{id}`
- `PATCH /api/v1/order-templates/{id}`
- `DELETE /api/v1/order-templates/{id}`

Template payload shape:

```json
{
  "name": "Kuwait Port Daily Collect",
  "canonical_target_id": "KUWAIT_PORT",
  "target": {
    "latitude": 29.3772,
    "longitude": 47.9906
  },
  "priority": 2,
  "constraints": {
    "max_incidence_deg": 30
  },
  "recurrence": {
    "type": "daily",
    "interval": 1,
    "days_of_week": null,
    "window_start_hhmm": "15:00",
    "window_end_hhmm": "17:00",
    "timezone": "Asia/Dubai"
  },
  "effective_start_date": "2026-04-01",
  "effective_end_date": "2026-06-30"
}
```

## 6.2 Order / Instance API Changes

Extend `orders` responses to include lineage and geometry:

- `template_id`
- `instance_key`
- `instance_local_date`
- `planner_target_id`
- `canonical_target_id`
- `target_lat`
- `target_lon`

Filter support should include:

- `template_id`
- `instance_from`
- `instance_to`
- `include_expired`

## 6.3 Planning API Changes

Planning endpoints should not require the frontend to manually expand recurring instances.

Recommended backend behavior:

- planning request provides `workspace_id` and horizon as today
- backend automatically materializes missing recurring instances for that horizon
- backend automatically builds instance-scoped opportunities from canonical feasibility data

Planning and schedule API responses should expose lineage fields:

- `order_id`
- `template_id`
- `canonical_target_id`
- `display_target_name`
- `instance_key`

## 6.4 Frontend Type Changes

Introduce explicit frontend types:

- `OrderTemplate`
- `OrderInstance`

Reduce reliance on:

- `AcceptedOrder` as a long-term source of truth
- `plan_id` as a fallback “order ID”

`AcceptedOrder` can remain as a local presentation model, but its backing data should come from normalized schedule/order/template records.

---

## 7. Proposed Schedule Persistence Changes

## 7.1 Tables and Columns

Add:

- new `order_templates` table
- new lineage columns on `orders`
- new lineage columns on `plan_items`
- new lineage columns on `acquisitions`

Recommended acquisition columns:

- `template_id`
- `instance_key`
- `canonical_target_id`
- `display_target_name`

Recommended plan-item columns:

- `template_id`
- `instance_key`
- `canonical_target_id`
- `display_target_name`

## 7.2 Commit Path

At commit time:

- `plan_items.order_id` must already point to the dated instance
- commit copies `order_id` and new template/canonical lineage fields into `acquisitions`
- `orders.status` is updated for the instance row
- template status is unchanged unless explicitly paused/ended

## 7.3 Snapshot and Rollback

No new snapshot table design is required.

Why:

- `_create_snapshot()` already captures `SELECT * FROM acquisitions`
- `rollback_to_snapshot()` already reinserts columns dynamically from JSON

Requirement:

- once new recurrence lineage columns exist on `acquisitions`, snapshots and rollback will preserve them automatically

## 7.4 Workspace Export / Import

Workspace persistence must stop treating recurring intent as only a frontend blob.

Follow-up implementation should export/import:

- order templates
- materialized order instances
- acquisitions with recurrence lineage

`orders_state` can remain as a convenience cache for UI presentation, but it should not be the authoritative recurring-order source of truth.

---

## 8. Proposed UI Shape

Keep UI intentionally small:

1. Author recurrence where orders are already authored.
2. Keep recurring controls collapsed unless enabled.
3. Show a compact recurrence summary, not a generated-instance manager.
4. Keep timeline and schedule views focused on acquisitions, not template administration.

Recommended minimal authoring controls:

- `One-time` / `Repeats`
- `Daily` / `Weekly`
- weekday selector for weekly
- local start/end time
- timezone
- effective start/end dates

Recommended display conventions:

- show canonical target name to operators
- show recurrence summary chip
- hide synthetic planner target IDs from UI
- only reveal dated instances in detail drawers, audit/history views, or explicit backend order tables

---

## 9. Recommended Phased Implementation Plan

## Phase 0: Audit and design

- This document
- `docs/PR_SCHED_002_CHECKLIST.md`

## Phase 1: Persistence and template foundation

- add `order_templates`
- extend `orders` with instance lineage
- define deterministic `instance_key`
- add unique `(template_id, instance_key)` protection
- harmonize order statuses to include `expired`

## Phase 2: Materialization and planning integration

- build horizon-based materializer
- clone/filter canonical feasible opportunities into instance-scoped opportunities
- propagate `order_id` / `template_id` / canonical target lineage through plan items and commit
- keep scheduler algorithms unchanged

## Phase 3: Minimal UI and workspace round-trip

- add compact recurrence editor
- add summary chips
- persist templates through workspace save/load/export/import
- stop relying on `plan_id` as a fake order identity in UI recovery

## Phase 4: Incremental / repair hardening

- update auto-mode selection to reason about materialized instance targets
- support instance-aware incremental planning
- keep repair scoped to already materialized items and lock/conflict resolution

---

## 10. Risks and Edge Cases

## 10.1 Daily recurrence

Risk:

- multiple days inside one horizon must produce exactly one instance per local date

Recommendation:

- generate one instance per local day in template timezone
- derive UTC `requested_window_start/end` from that local day

## 10.2 Weekly recurrence

Risk:

- weekday evaluation is wrong if computed in UTC rather than template timezone

Recommendation:

- evaluate weekday membership on the template local date
- store `days_of_week_json` explicitly

## 10.3 Time-window interaction

Risk:

- template local window and mission-wide acquisition time window can conflict or double-filter opportunities

Recommendation:

- reuse `DailyTimeWindow` helper and validation logic
- keep mission-wide `acquisition_time_window` as a separate global filter
- when both exist, apply intersection semantics

## 10.4 Expired instances

Risk:

- stale unplanned instances accumulate or keep reappearing

Recommendation:

- mark an instance `expired` after its requested window closes without commitment
- exclude expired instances from normal planning unless explicitly requested
- keep them for audit/reporting

## 10.5 Duplicate generation

Risk:

- repeated planning runs generate the same occurrence twice

Recommendation:

- deterministic `instance_key`
- unique constraint on `(template_id, instance_key)`
- materializer uses upsert / insert-ignore semantics

## 10.6 Timezone handling

Risk:

- local date boundaries drift if timezone is implied from browser or mission horizon

Recommendation:

- store explicit IANA timezone on template
- materialize windows in template timezone
- persist UTC timestamps for requested windows
- never derive recurrence timezone from browser locale

## 10.7 Midnight-crossing windows

Risk:

- `22:00-02:00` can create the wrong local anchor date or duplicate two instances

Recommendation:

- anchor the instance to the local start date
- derive end timestamp on the following local date
- reuse existing `DailyTimeWindow` midnight-crossing semantics

---

## 11. Final Recommendation

Recurring orders are **not ready to implement safely on top of the current target-centric identity model**.

They **are** implementable with a clean, low-noise design if the follow-up work does the following first:

- add a separate template entity
- treat `orders` as dated instances
- materialize instances per planning horizon
- give each instance a unique planner-visible target identity
- persist template/instance lineage on plan items and acquisitions

That path preserves the current scheduler, keeps the UI small, and gives repair/rollback/history a stable model to work with.
