# Recurring-Aware Planning and Feasibility Audit

## Executive verdict

The system should evolve from a target-first feasibility tool into a demand-aware mission planner.

The correct ownership model is:

- `Mission Parameters` owns the `Planning Horizon` for the current run.
- `Orders` and `recurring templates` own all demand timing.
- `Feasibility Results`, `Schedule`, and `Cesium` own only display state such as zoom, pan, and visible range.

The correct planning unit is not the physical target. It is the `planning demand`:

- a one-time order demand, or
- a materialized dated recurring instance.

The cleanest architecture given the current backend is:

`canonical target -> order template or one-time order -> materialized dated instance when needed -> planning demand -> demand-scoped opportunity set -> scheduled acquisition`

The recommended Feasibility Results UX is a `dual-view model`:

- `Demand View` as the default actionable view
- `Master Timeline` as the secondary aggregate view

This preserves low-noise target overview while making recurring work operationally correct.

## Current system model

Today the system is split across two mental models:

1. `Feasibility` is still target-centric.
2. `Scheduling` is already partially recurring-aware.

Observed current flow:

1. The frontend pre-feasibility orders UI groups targets into local "orders".
2. On analyze, repeating orders are synced to backend templates, but all targets from all pre-feasibility orders are still flattened into one `missionData.targets` list.
3. `backend/main.py` runs mission analysis against a single mission horizon and optional mission-wide acquisition window.
4. Feasibility results render one lane per target and one merged opportunity timeline per target across the horizon.
5. During scheduling, `backend/order_materialization.py` materializes recurring instances for the planning horizon and clones canonical opportunities into per-instance `planner_target_id` identities.
6. `backend/schedule_persistence.py` and `backend/routers/schedule.py` already persist recurring lineage such as `template_id`, `instance_key`, `planner_target_id`, and `canonical_target_id`.
7. Frontend schedule and inspector surfaces still mostly render `target_id`, so recurring lineage exists in backend data but is not yet expressed cleanly in operator UX.

In one sentence: the system currently does `target-centric feasibility + instance-aware scheduling`.

That asymmetry was acceptable when everything behaved like one-time target selection. Recurring orders make it a primary design gap.

## Time ownership audit

### Current state

| Time concept | Current behavior | Problem | Recommended owner |
| --- | --- | --- | --- |
| Planning Horizon | `Mission Parameters` start/end define feasibility run bounds | Correct concept, but not used consistently by all planning paths | Keep in `Mission Parameters` |
| Mission-wide acquisition window | Mission Parameters can apply one recurring daily time-of-day filter across the horizon | Duplicates order timing if overused; can be confused with demand windows | Keep only as an advanced global run filter, not as order timing |
| One-time requested window | Supported on backend orders, but not first-class in pre-feasibility flattening flow | One-time demand timing is not the primary feasibility unit yet | Move fully under `Orders` |
| Recurring local window | Stored on recurring templates | Correct, but frontend still defaults values from mission horizon | Keep in `Orders/templates` |
| Recurring effective start/end | Stored on recurring templates | Correct ownership, but should not be mistaken for run horizon | Keep in `Orders/templates` |
| Feasibility visible range | Local timeline view state in results panel | Can be mistaken for planning truth if unlabeled | Display-only |
| Schedule visible range | `scheduleStore.tStart/tEnd` and zoom drive timeline/master schedule fetches | Query scope is mixed with plan scope in operator mental model | Display-only |
| Cesium time window | Viewer clock/window follows selected schedule or timeline state | Purely visual, but easily conflated with planning horizon | Display-only |
| Scheduling mode-selection horizon | `MissionPlanning.tsx` currently uses a separate hardcoded `now -> now+7d` context | Hidden second planning horizon | Replace with explicit planning scope later; do not treat as time ownership source |

### Recommended ownership model

#### What should stay in Mission Parameters

- `Planning Horizon` for the current run
- optional `global run filter` controls only if they apply to the whole run and not to individual demands

Mission Parameters should answer:

- "What planning envelope are we analyzing right now?"
- not "When does this order want to be collected?"

#### What belongs inside Orders or recurring templates

- one-time requested window
- one-time earliest/latest constraints
- recurring daily or weekly timing
- recurring local start/end window
- recurring timezone
- recurring effective start and end dates
- order priority and order-specific constraints

Orders should answer:

- "What demand exists?"
- "When is it valid?"
- "How often does it repeat?"

#### What should be display-only state

- Feasibility Results zoom, pan, and visible timeline range
- Schedule timeline range and zoom mode
- Cesium clock position and visible time window
- selected day, focused acquisition, expanded groups, and inspector focus

Display state should answer:

- "What am I looking at?"
- not "What is the planner allowed to schedule?"

### Ownership rule

The system should have exactly one authoritative owner for each time concept:

- run envelope -> Mission Parameters
- demand timing -> Orders/templates
- visual inspection window -> Results/Schedule/Cesium

Any control that mixes two of those concerns should be treated as duplication risk.

## Feasibility model audit

### How feasibility works today

Today feasibility is:

- target-centric
- flattened from pre-feasibility orders
- evaluated over one static horizon
- displayed as opportunities grouped by target

The key behaviors are:

1. Pre-feasibility orders are a frontend grouping convenience.
2. Analyze sends flattened targets, not normalized demands.
3. Mission analysis computes opportunities for canonical targets across one mission horizon.
4. Results show one merged timeline per target.

### Why this breaks once recurring orders exist

Recurring orders change the unit of work from "can we image Athens at some point in this horizon?" to "can we satisfy each Athens demand instance on each required date and window?"

Pure target-centric results break down because they:

- merge distinct recurring instances into one target lane
- hide whether a specific date is uncovered
- overstate feasibility when a target is generally observable but a dated recurring instance is not
- do not give the operator an actionable object to schedule, reshuffle, repair, or explain
- make one-time and recurring demands look like different products even though the scheduler ultimately needs both as work items

### Should feasibility remain target-centric?

Not as the canonical planning model.

Target-centric opportunity generation can remain as a lower-level backend step because orbital opportunities are naturally computed from canonical targets.

But feasibility as an operator-facing planning model should become `demand-aware`.

### Should feasibility become order-centric or demand-centric?

It should become `demand-centric`.

Reason:

- one UI order may contain multiple targets
- one recurring template produces many dated instances
- the scheduler already reasons correctly only after recurring instances are split into unique planner identities
- what the operator needs to know is the status of each actionable demand, not the abstract target alone

The cleanest model is:

- `canonical target` for geometry and base opportunity generation
- `planning demand` for feasibility, scheduling, reshuffle, repair, and satisfaction tracking

### Cleanest architecture given the current backend foundation

The backend already points in the right direction:

- recurring templates already exist
- recurring instances are already materialized by horizon
- recurring opportunities are already cloned into unique per-instance planner identities
- lineage is already persisted through plan items and acquisitions

So the safest architectural move is not a scheduler rewrite. It is to formalize the existing pattern:

1. Keep canonical opportunity generation by physical target.
2. Bind those opportunities to normalized planning demands.
3. Evaluate feasibility and schedule coverage per demand.
4. Derive target-level aggregate views as secondary projections.

This is a low-risk evolution because it aligns the feasibility model with the schedule model that already exists in backend data.

## Recurring demand model

### Recommended conceptual model

| Concept | Meaning | Primary purpose |
| --- | --- | --- |
| Canonical target | Stable physical point or AOI identity | Geometry, map identity, base opportunity generation |
| Order template | Persistent recurring intent definition | "Repeat this work under these rules" |
| Materialized dated instance | Concrete dated occurrence generated inside a horizon | One actionable recurring occurrence |
| Planning demand | Unified actionable work unit for planning | One-time order or materialized recurring instance |
| Opportunity set | Candidate collection opportunities for one planning demand | Feasibility evaluation and scheduling inputs |
| Scheduled acquisition | Committed or tentative scheduled collection | Execution outcome |

### Relationship between concepts

- A canonical target can have zero or more order templates.
- A recurring order template can materialize zero or more dated instances within a horizon.
- A one-time order creates one planning demand directly.
- A recurring dated instance creates one planning demand indirectly.
- A planning demand owns an opportunity set.
- A scheduled acquisition satisfies a planning demand, fully or partially depending on policy.

### Visibility by product surface

| Concept | Orders UI | Feasibility Results | Schedule | Inspector |
| --- | --- | --- | --- | --- |
| Canonical target | Primary label | Primary label | Primary label | Visible |
| Order template | Visible for recurring authoring | Usually hidden | Secondary badge only | Visible |
| Materialized dated instance | Hidden by default | Visible | Visible as secondary metadata | Visible |
| Planning demand | Not named explicitly | Primary actionable row/card | Primary scheduling unit | Visible |
| Opportunity set | Hidden | Visible | Hidden except details | Visible |
| Scheduled acquisition | Linked summary only | Coverage outcome only | Primary object | Primary object |

### Practical interpretation

The operator should mostly see:

- target name
- demand date
- requested window
- recurrence badge when relevant
- current status

The operator should not have to think about:

- `planner_target_id`
- `instance_key`
- template storage details
- opportunity cloning mechanics

## Comparison of UX options

### target-centric

Option 1.

Definition:

- one target
- one merged opportunity list or timeline across the full horizon

Pros:

- lowest immediate implementation change
- preserves current Feasibility Results layout
- low visual density for small missions

Cons:

- wrong primary abstraction once recurring work exists
- merges separate daily or weekly demands into one apparent target status
- cannot reliably answer whether a specific dated instance is covered
- encourages operators to plan against "general target observability" instead of actual demand satisfaction

Verdict:

- acceptable only as a secondary aggregate view
- not acceptable as the primary recurring-aware results model

### demand-centric

Option 2.

Definition:

- each dated instance is shown separately
- one-time orders and recurring instances both appear as demands

Pros:

- operationally correct
- aligns with scheduling, reshuffle, repair, and fulfillment
- makes uncovered recurring dates explicit
- gives the operator a real planning object

Cons:

- can become visually noisy over longer horizons
- can overwhelm operators if shown as one flat ungrouped list
- loses some broad target-level awareness unless paired with an aggregate layer

Verdict:

- correct data model
- not sufficient alone unless carefully grouped

### dual-view

Option 3.

Definition:

- `Demand View` for actionable work
- `Master Timeline` for aggregate target overview

Pros:

- best operator UX
- most faithful to real planning work
- lowest noise when paired with grouping and collapse
- cleanest migration path because current target-centric timeline can survive as the aggregate view

Cons:

- slightly more UI surface than a single-view design
- requires disciplined naming so both views feel complementary instead of duplicate

Verdict:

- recommended

### Best operator UX

`Option 3: Dual-view`

Because military planners need both:

- a precise answer for each actionable demand
- a fast strategic overview across the whole horizon

### Cleanest military-grade flow

`Option 3: Dual-view`

Because it separates:

- actionable demand readiness
- broad target situational awareness

without asking the operator to mentally decode recurring lineage from merged target lanes.

### Lowest-noise implementation path

`Option 3: Dual-view`

Because it allows:

- the current target-centric feasibility panel to be preserved as the secondary `Master Timeline`
- the new work to focus on adding one normalized `Demand View`

That is lower risk than replacing the entire results surface in one step.

## Recommended mission-planner UX

### Core principles

1. The operator sets the `Planning Horizon` once in Mission Parameters.
2. The operator defines demand timing only in Orders.
3. The system silently materializes recurring demands inside the horizon.
4. Feasibility answers readiness per demand.
5. Schedule, reshuffle, and repair act on demands.
6. Aggregate target views are derived, not authoritative.

### Recommended Feasibility Results structure

#### Default: Demand View

Show one actionable row per planning demand:

- `Athens | 03 Apr`
- `Athens | 04 Apr`
- `Depot North | one-time`

Recommended grouping:

- group by day inside the current Planning Horizon
- within each day, group or sort by canonical target and priority

Each demand row should show only:

- target name
- date label
- requested local window
- recurrence badge if recurring
- feasibility status
- best opportunity summary
- expandable list of opportunities

#### Secondary: Master Timeline

Keep a compressed aggregate timeline by canonical target across the current horizon.

Use it for:

- broad situational awareness
- spotting density and competition
- quick map-to-target scanning

Do not use it as the authoritative answer to "is this recurring work covered?"

### Orders UI

Orders UI should remain the place where intent is authored:

- one-time order window
- recurring pattern
- recurring effective validity
- priority and constraints

It should not explode every future recurring instance into the main authoring surface.

Recurring materialization belongs downstream.

### Schedule

Schedule should show the execution picture:

- scheduled acquisitions as the primary objects
- canonical target as the primary visible label
- recurring lineage as secondary metadata

The lane model should not expose raw per-instance planner IDs as first-class operator labels.

### Inspector

Inspector is the correct place for full lineage and backend detail:

- canonical target
- order/template source
- instance date
- planning demand identity
- acquisition linkage

## Schedule/reshuffle implications

### How recurring instances should appear in reshuffle logic

Recurring instances should enter reshuffle as independent planning demands.

Reason:

- each instance has its own date and requested window
- each instance may be independently satisfied, unsatisfied, locked, or repairable
- merging them back to the physical target loses the scheduling unit that matters

### Should schedule master view show recurring lineage?

Yes, but only as secondary metadata.

Recommended operator presentation:

- primary label: canonical target name
- secondary badge or subtitle: recurring, template name, or instance date
- full lineage in inspector or details drawer

Do not make `planner_target_id` or raw instance IDs visible as the lane identity.

### Should feasibility results show instance grouping by day?

Yes.

Grouping recurring instances by day is the cleanest way to keep Demand View actionable without flattening the screen into noise.

### How should one-time and recurring coexist visually?

They should use one common demand card model.

Shared card anatomy:

- target name
- date or "one-time" label
- requested window
- feasibility status
- opportunity count

Recurring adds:

- repeat badge
- optional series label in details

One-time adds:

- no repeat badge
- same card structure otherwise

### How should schedule, repair, and incremental planning reason about demand vs physical target?

They should reason about:

- `demand` for planning, dedupe, lock, repair, coverage, and audit trail
- `canonical target` for geometry, grouping, map label, and high-level aggregation

This is the most important conceptual split in the recurring-aware planner.

## Minimal UI rules

### What not to expose

- `planner_target_id`
- `instance_key`
- backend materialization mechanics
- cloned opportunity identities
- canonical suppression rules used during recurring opportunity preparation

### What should be grouped or collapsed

- recurring demand rows in Feasibility Results by day
- recurring lineage in schedule cards and tiles
- advanced mission-wide filters in Mission Parameters

### What should be visible only in detail drawers or inspector

- template ID and template status
- instance lineage
- canonical target ID
- exact order-template linkage
- backend-derived satisfaction and lineage audit fields

### What should remain backend-managed and hidden

- materialization of recurring instances within a horizon
- internal demand identity normalization
- target-to-demand opportunity cloning
- dedupe against already scheduled future instances
- planner-facing target substitution

### Minimal military-planner UI

The minimum clean UI is:

- one `Planning Horizon` control in Mission Parameters
- all one-time and recurring timing in Orders
- one default `Demand View` in Feasibility Results
- one secondary `Master Timeline`
- one common demand visual model for one-time and recurring work
- lineage and backend detail only in drawers and inspector

## Phased implementation plan

### Phase 0: this PR

- document the ownership model
- document the demand model
- document the recommended Feasibility Results direction

No feature changes, scheduler changes, migrations, or UI rewrites.

### Phase 1: align contracts and naming

- define `planning demand` in backend and frontend terminology
- stop treating flattened target lists as the long-term planning abstraction
- make planning paths consume an explicit planning scope instead of hidden fallback horizons
- keep `Planning Horizon` language consistent across Mission Parameters and planning actions

### Phase 2: normalize demand-aware data without changing the scheduler

- represent one-time work as one planning demand per order
- keep recurring materialization as the source of recurring demands
- bind canonical opportunities to demands
- add demand-level summary fields to feasibility and schedule response shapes

This phase should reuse the existing backend lineage fields rather than inventing a new algorithm.

### Phase 3: ship dual-view Feasibility Results

- introduce `Demand View` as the default
- preserve a compressed target-level `Master Timeline`
- group demand results by day
- show recurring lineage only as secondary metadata

### Phase 4: normalize Schedule, reshuffle, and repair UX

- ensure schedule items group by canonical target for display while preserving demand identity for actions
- make repair summaries and coverage reasoning demand-based
- expose recurring lineage in details rather than lane identity

### Phase 5: remove or hide duplicated time controls

- review the continued value of the mission-wide acquisition window
- keep it only if it remains a true run-wide filter
- hide or retire controls that duplicate order timing

## Questions the audit must answer explicitly

### Should the Planning Horizon stay in Mission Parameters?

Yes. It is the planning envelope for the current run and should remain the authoritative run-level time control.

### Should recurring timing live only in Orders or templates?

Yes. Recurrence pattern, local recurring window, timezone, and effective validity belong to recurring templates, not Mission Parameters.

### Should Feasibility Results become demand-centric?

Yes, as the primary actionable model. Target-centric views should remain only as aggregate projections.

### Should one-time and recurring demands appear together in one results model?

Yes. They are both planning demands and should share one common results and scheduling model.

### Should there be two Feasibility modes: Demand View and Master Timeline?

Yes. `Demand View` should be the default. `Master Timeline` should be the secondary aggregate view.

### What is the minimum clean UI for military planners?

One Planning Horizon control, order-owned timing, default demand view, secondary master timeline, and lineage details hidden until inspection.

### What should stay hidden from operators even though it exists in backend?

Internal planner identities, instance keys, template linkage internals, materialization rules, and opportunity cloning mechanics.

### What is the safest phased path from current system to that target UX?

Keep canonical target opportunity generation, formalize planning demands above it, add demand-aware response models, ship dual-view results, then normalize schedule and repair surfaces. Do not rewrite the scheduler first.

## Final recommendation

The target state should be:

- `Mission Parameters` owns the run horizon
- `Orders/templates` own demand timing
- `Feasibility Results` becomes demand-aware by default
- `Master Timeline` survives as a derived aggregate view
- `Schedule/repair/reshuffle` act on demands, not abstract targets
- backend lineage remains mostly hidden from operators

This gives the product a clean path from a one-time feasibility tool to a recurring-aware mission-planning console without adding UI noise.
