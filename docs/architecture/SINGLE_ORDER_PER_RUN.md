# Single Order Per Run

## Decision

Feasibility Analysis authors exactly one order per run.

- `order` is the run-level demand container.
- `targets` remain a many-valued list inside that order.
- `recurrence` or `frequency` is authored once on that order definition.
- The frontend must not allow multiple parallel pre-feasibility orders.

This keeps the operator model aligned with the team decision:

- one run
- one order definition for that run
- many targets inside it

## Frontend Authoring Model

The pre-feasibility store should hold a single order object, not an array of parallel authoring orders.

Recommended shape:

```ts
type PreFeasibilityState = {
  order: {
    id: string
    name: string
    targets: TargetData[]
    orderType: 'one_time' | 'repeats'
    recurrence?: OrderRecurrenceSettings
    templateIds?: string[]
    templateStatus?: 'active' | 'paused' | 'ended' | null
    createdAt: string
  } | null
  activeOrderId: string | null
}
```

Implementation rules:

- `createOrder()` creates the order only if missing and otherwise returns the existing ID.
- map-click and file-upload flows always target the single order
- removing the order resets the run-level authoring state
- validation is order-scoped, then target-scoped inside that order

## Recurring Ownership

Recurring configuration belongs to the single order definition.

- `Order type = One-time` means the order has no recurring frequency.
- `Order type = Recurring` means the order owns one shared frequency definition.
- `Frequency` replaces the older `Repeat pattern` label in the UI.
- all targets inside the order inherit that same recurring definition for template sync

This does not change the backend template storage pattern yet. The backend can still persist one template record per target while the frontend authors recurrence once at the order level.

## Hydration And Legacy Multi-Order State

Existing recurring template records may still arrive as multiple grouped fragments.

Frontend handling should be:

- merge hydrated fragments into one run-level order
- preserve all targets
- prefer recurring metadata when choosing the order-level recurrence settings
- treat any previously parallel local authoring groups as legacy state and normalize them into one order on load

This is a UI normalization rule, not a new backend data model.

## Terminology

Use the following terms consistently:

- `Order`: the single run-level demand container used by Feasibility Analysis
- `Target`: a requested site inside that order
- `Frequency`: the recurring cadence for the order, such as daily or weekly
- `Recurring template`: backend persistence of recurring intent

Avoid:

- `Repeat pattern`
- language that implies multiple parallel pre-feasibility orders in one run

## Visualization Preparation

Do not implement the new visualization in this change.

For the future left-side feasibility timeline, the intended summary is:

- summarize how many acquisitions happen per day
- summarize at the order level first, not as multiple authoring-order lanes
- keep the current detailed visualization work for a later PR

Prepared shape for a future aggregation layer:

```ts
type DailyAcquisitionSummary = {
  date: string
  acquisitionCount: number
  targetCount: number
  targetIds: string[]
}

type OrderTimelineSummary = {
  orderId: string
  orderName: string
  frequency: 'one_time' | 'daily' | 'weekly'
  days: DailyAcquisitionSummary[]
}
```

The left timeline should consume a summary like this instead of rendering separate pre-feasibility order lanes.

## Non-Goals

This decision record does not introduce:

- scheduler algorithm changes
- backend schema changes
- full recurring demand visualization
- full demand-day breakdown UI
