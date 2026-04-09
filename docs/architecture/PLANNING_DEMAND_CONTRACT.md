# Planning Demand Contract

## Decision

With single-order-per-run authoring in place, the feasibility and planning contract should distinguish four layers:

- `run order`: the single run-level container authored in Feasibility Analysis
- `canonical target`: the stable physical target identity
- `planning demand`: the actionable unit evaluated inside the current horizon
- `scheduled acquisition`: the eventual committed or tentative execution outcome

This keeps the authoring model simple while making results demand-aware.

## Model

### Run order

The run order is the authored container for this planning session.

- one run has one run order
- one run order can contain many targets
- recurring frequency belongs to that run order
- mission parameters still own the run horizon

### Canonical target

The canonical target is the physical target identity used for grouping and geometry.

- map identity is canonical-target based
- opportunity generation remains canonical-target based
- display labels can stay friendly while lineage remains stable underneath

### Planning demand

The planning demand is the unit that results should answer.

- a one-time target creates one `one_time` demand inside the current horizon
- a recurring target creates one `recurring_instance` demand per dated occurrence inside the horizon
- each demand owns its requested window and its feasibility summary

This is the bridge between authored intent and future schedule coverage reasoning.

## Request Contract

`POST /api/v1/mission/analyze` now accepts additive `run_order` metadata beside the existing flattened `targets[]`.

Recommended shape:

```json
{
  "run_order": {
    "id": "order-123",
    "name": "Daily Port Sweep",
    "order_type": "repeats",
    "targets": [
      {
        "canonical_target_id": "PORT_ALPHA",
        "display_target_name": "Port Alpha",
        "template_id": "tmpl-1"
      }
    ],
    "recurrence": {
      "recurrence_type": "daily",
      "interval": 1,
      "days_of_week": null,
      "window_start_hhmm": "09:00",
      "window_end_hhmm": "11:00",
      "timezone_name": "UTC",
      "effective_start_date": "2026-04-02",
      "effective_end_date": "2026-04-10"
    }
  }
}
```

The existing `targets[]` request remains the canonical opportunity-generation input for now. The additive `run_order` block formalizes demand lineage without requiring scheduler changes.

## Response Contract

`mission_data` now carries three additive demand-aware structures:

- `run_order`
- `planning_demands`
- `planning_demand_summary`

### Planning demand shape

Each entry in `planning_demands` should expose:

- `run_order_id`
- `demand_id`
- `canonical_target_id`
- `display_target_name`
- `demand_type`
- `template_id`
- `instance_key`
- `requested_window_start`
- `requested_window_end`
- `local_date`
- feasibility summary fields such as matching-pass count and best pass summary

This common shape must represent both:

- one-time target demand
- recurring dated instance demand

## Horizon Expansion

The contract rule is:

- one run order
- many targets
- many planning demands inside the analyzed horizon

For recurring work, the backend expands dated demand instances inside the horizon using the order recurrence metadata. This expansion is contract-level only in this phase.

Important:

- canonical opportunity generation stays under the hood
- the current scheduler stays unchanged
- recurring materialization logic remains the source of truth for recurrence semantics

## Results Direction

This contract prepares the next UI step without implementing it yet.

### Future Demand View

Demand View should consume `planning_demands` as the default actionable model.

- group by `local_date`
- sort within a day by canonical target and priority
- show requested window and feasibility summary per demand

### Future Master Timeline

Master Timeline should remain an aggregate projection derived from:

- canonical targets
- existing feasibility `passes`
- demand-level lineage when needed for inspection

### Left timeline note

The eventual left timeline summary should roll up demand-aware outcomes by day.

- do not implement that visualization here
- keep the response shape ready by preserving `local_date` and requested-window fields on each demand

## Non-goals

This contract alignment does not introduce:

- scheduler algorithm rewrites
- new planning heuristics
- a full Feasibility Results redesign
- direct exposure of raw planner target IDs as the operator-facing identity
