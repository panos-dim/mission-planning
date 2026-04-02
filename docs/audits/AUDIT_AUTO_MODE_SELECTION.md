# Audit: Auto Mode Selection

## Goal

Keep mission-planner UX mode-free while letting the backend choose the correct scheduling behavior internally:

- `from_scratch`
- `incremental`
- `repair`

The scheduler algorithm itself is unchanged. This phase only changes orchestration and auditability.

## Decision Rules

### `from_scratch`

Use when:

- no active schedule exists for the workspace, or
- the workspace schedule was cleared and no active acquisitions remain

Meaning:

- build a fresh schedule from the active horizon inputs

### `incremental`

Use when:

- a schedule already exists, and
- new actionable work appears, and
- the existing schedule is still safe enough to extend

New actionable work includes:

- newly materialized recurring order instances in the planning horizon
- previously materialized recurring instances that are still outstanding and not yet backed by committed acquisitions
- newly added one-time targets
- newly added one-time orders since the last committed revision

### `repair`

Use when:

- scheduled items are stale or out of scope
- acquisitions reference missing or inactive orders
- unresolved conflicts exist
- incremental extension would be unsafe and must fall back
- no new work exists, but a valid existing schedule is present and reshuffle/correction remains the stable non-incremental path

The existing priority-aware reshuffle rule is preserved:

- if new work is materially higher priority and the active scoring weights favor reshuffling, choose `repair`

## Recurring Orders Are First-Class

Recurring instances are not compared by canonical target identity alone.

Key rule:

- `order_templates` = recurring business intent
- `orders` = actionable dated instances
- `order_id` = dated instance identity
- `template_id` = recurring template identity
- `planner_target_id` = unique scheduler-facing identity for one dated instance
- `canonical_target_id` = physical target identity for grouping/operator meaning

Mode selection therefore evaluates recurring work using instance-scoped planner identities, not just canonical targets.

Example:

- `PORT_A` on `2026-04-02` and `PORT_A` on `2026-04-03` are two different actionable scheduling units
- if `2026-04-02` is already committed and `2026-04-03` is newly materialized, the resolver counts the second one as new work

## Audit Breadcrumbs

Every planning run records the mode decision with:

- workspace ID
- chosen mode
- reason string
- previous schedule revision ID
- existing committed acquisition count
- current materialized recurring instance count
- outstanding recurring instance count
- new instance count
- new target count
- stale acquisition count
- conflict count
- fallback origin when `incremental -> repair`
- request payload hash

These breadcrumbs are available through the existing dev diagnostics path and structured logs.

## Endpoint Behavior

### `/api/v1/schedule/mode-selection`

- materializes recurring instances for the requested horizon
- resolves the internal mode deterministically
- returns the reason and audit counters

### `/api/v1/schedule/repair`

- now uses recurring-materialized planner inputs as well
- preserves recurring lineage on persisted repair plan items
- records the same mode-decision breadcrumbs

### `/api/v1/planning/schedule`

- auto-resolves `from_scratch` vs `incremental` internally when the caller does not force a non-default mode
- rejects requests that truly require `repair` so the wrong planner path is not run silently

## UI Contract

Planner-facing UI must not expose raw scheduling modes as user choices.

Visible planner actions remain:

- Generate Mission Plan
- Apply

Internal mode data may still exist in payloads, but frontend labels should stay in plain scheduling language rather than exposing `from_scratch`, `incremental`, or `repair` directly.
