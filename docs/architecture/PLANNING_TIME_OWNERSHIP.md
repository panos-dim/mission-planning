# Planning Time Ownership

## Purpose

This document defines the authoritative owner for each time concept in mission planning so the system can support recurring work without duplicating controls or mixing display time with planning time.

## Authoritative time concepts

| Time concept | Meaning | Authoritative owner | Notes |
| --- | --- | --- | --- |
| Planning Horizon | The planning envelope for the current run | Mission Parameters | Start and end of the current feasibility/planning run |
| One-time order window | Requested time window for a one-time demand | Order | Demand timing, not mission timing |
| Recurring local window | Local daily or weekly collection window | Recurring template | Demand timing, not mission timing |
| Recurring effective validity | Date range when a recurring template is active | Recurring template | Governs which dated instances can materialize |
| Global run filter | Optional run-wide time-of-day feasibility filter | Mission Parameters | Advanced filter only; never a substitute for order timing |
| Display horizon | What the operator is currently looking at | Results/Schedule/Cesium | Zoom, pan, visible range, and focus only |
| Repair scope | Optional explicit operational repair slice | Planning workflow | Must be labeled as scope, not horizon ownership |

## Ownership rules

### Rule 1

Mission Parameters owns only run-level planning scope.

Mission Parameters should answer:

- "What horizon are we planning over right now?"

Mission Parameters should not answer:

- "When does this demand want to be collected?"

### Rule 2

Orders and templates own all demand timing.

That includes:

- one-time requested windows
- earliest and latest constraints
- recurring pattern
- recurring local time window
- recurring timezone
- recurring effective start and end dates

### Rule 3

Display surfaces own only display time.

That includes:

- Feasibility timeline zoom and pan
- Schedule visible range and zoom
- Cesium clock and visible window
- selected or focused time slice

Display time can change what the user sees. It must not change what the planner considers valid demand timing.

## Recurring-aware interpretation

Recurring work introduces two different meanings of time that must stay separate:

1. `When is the run analyzing?`
2. `When is each recurring demand valid?`

Those are not the same thing.

The run horizon filters which recurring instances are materialized for the run.

The recurring template defines:

- which dates may materialize
- which local time window each materialized instance inherits

## Display state is not planning truth

The following are display-only and should never be treated as the source of planning truth:

- `MissionResultsPanel` local visible range
- `scheduleStore.tStart/tEnd`
- `scheduleStore.zoom`
- `visStore.timeWindow`
- Cesium clock position

These are inspection controls.

## Global acquisition window guidance

If the mission-wide acquisition window remains in the product, it should be treated as:

- an advanced global feasibility filter
- applied across the whole run
- clearly separate from order timing

It should not duplicate:

- one-time requested windows
- recurring local windows
- recurring validity dates

## Anti-patterns to avoid

- deriving recurring validity semantics from the current visible schedule range
- treating a schedule timeline zoom range as the active planning horizon
- exposing both mission-level and order-level windows without clear ownership
- using a hidden fallback horizon in planning actions that diverges from Mission Parameters
- showing backend materialization identifiers as operator-facing time controls

## Practical product rule

If the operator asks:

- "How long is this run analyzing?" -> Mission Parameters
- "When does this order occur?" -> Orders/templates
- "What slice am I looking at?" -> Results/Schedule/Cesium

That is the intended ownership model.
