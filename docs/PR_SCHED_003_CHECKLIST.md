# PR_SCHED_003 Checklist

**PR**: `feat/recurring-orders-foundation-order-templates-and-instance-lineage`
**Date**: 2026-04-02

## Migration Checklist

- [x] Add `order_templates` table with recurring-template source-of-truth fields
- [x] Add `orders.template_id`
- [x] Add `orders.instance_key`
- [x] Add `orders.instance_local_date`
- [x] Add `orders.planner_target_id`
- [x] Add `orders.canonical_target_id`
- [x] Add `orders.target_lat`
- [x] Add `orders.target_lon`
- [x] Add `plan_items.template_id`
- [x] Add `plan_items.instance_key`
- [x] Add `plan_items.canonical_target_id`
- [x] Add `plan_items.display_target_name`
- [x] Add `acquisitions.template_id`
- [x] Add `acquisitions.instance_key`
- [x] Add `acquisitions.canonical_target_id`
- [x] Add `acquisitions.display_target_name`
- [x] Add unique recurring-instance protection on `(template_id, instance_key)`
- [x] Keep snapshot/rollback storage design unchanged

## Route Checklist

- [x] `POST /api/v1/order-templates`
- [x] `GET /api/v1/order-templates`
- [x] `GET /api/v1/order-templates/{id}`
- [x] `PATCH /api/v1/order-templates/{id}`
- [x] `DELETE /api/v1/order-templates/{id}`
- [x] Existing `POST /api/v1/orders` accepts recurring-instance lineage fields
- [x] Existing `GET /api/v1/orders*` responses expose recurring-instance lineage fields

## Lineage Field Matrix

| Table | New columns | Purpose |
| --- | --- | --- |
| `order_templates` | recurring template fields | Stores recurring business intent separately from actionable orders |
| `orders` | `template_id`, `instance_key`, `instance_local_date`, `planner_target_id`, `canonical_target_id`, `target_lat`, `target_lon` | Makes each actionable order a dated instance with stable recurring lineage and geometry |
| `plan_items` | `template_id`, `instance_key`, `canonical_target_id`, `display_target_name` | Preserves recurring source + operator-facing lineage through candidate plans |
| `acquisitions` | `template_id`, `instance_key`, `canonical_target_id`, `display_target_name` | Preserves recurring source + operator-facing lineage through committed schedule state and rollback |

## Uniqueness Rule Verification

- Rule: `(template_id, instance_key)` must be unique for recurring instances
- Enforcement: partial unique index `idx_orders_template_instance_unique`
- Verified: same template + different `instance_key` inserts successfully
- Verified: duplicate template + same `instance_key` is rejected with HTTP `409` at the API layer and `sqlite3.IntegrityError` in persistence tests

## Snapshot/Rollback Verification

- `schedule_snapshots` design unchanged
- `_create_snapshot()` still captures `SELECT * FROM acquisitions`
- `rollback_to_snapshot()` still reinserts acquisition rows dynamically by column set
- Verified locally: acquisition rows with `template_id`, `instance_key`, `canonical_target_id`, and `display_target_name` survive snapshot + rollback intact

## Manual API Verification Results

Local spot-checks were executed against a temporary SQLite database using FastAPI `TestClient` on 2026-04-02.

| Check | Result | Notes |
| --- | --- | --- |
| Create one-time order with no template | PASS | `template_id` remains `null`; `planner_target_id` and `canonical_target_id` default to `target_id` |
| Create order template via API | PASS | Template stored and read back with daily recurrence fields intact |
| Create two recurring instances from one template | PASS | Both inserts succeed when `instance_key` differs |
| Attempt duplicate `(template_id, instance_key)` | PASS | API returns `409` conflict |
| Write plan/acquisition lineage | PASS | `plan_items` and committed `acquisitions` persist `template_id`, `instance_key`, `canonical_target_id`, `display_target_name` |
| Create snapshot and rollback | PASS | Restored acquisition retains recurring lineage fields |
| Patch template status/notes | PASS | `PATCH` updates persisted template state |
| Delete unused template | PASS | Unused template deletes cleanly |
| Delete linked template | PASS | Deletion is rejected to avoid orphaning instance lineage |
