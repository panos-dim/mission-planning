# Recurring Order Lineage

This phase implements the backend identity split required by the recurring-orders audit without changing scheduler algorithms.

## Architectural Rule

- `order_templates` = recurring business intent
- `orders` = actionable dated instances
- `order_id` = dated instance identity
- `template_id` = recurring template identity
- `planner_target_id` = unique scheduler-facing identity for each instance
- `canonical_target_id` = physical target identity used for grouping/operator meaning

## Entity Flow

`Canonical Target -> Order Template -> Order Instance -> Plan Item -> Acquisition`

- `Canonical Target` is the physical site operators care about.
- `Order Template` stores the repeat rule and local window.
- `Order Instance` is the dated actionable row planning and commit use.
- `Plan Item` carries the chosen opportunity plus instance/template lineage.
- `Acquisition` is the committed schedule record, still keyed by `order_id` for the actionable instance.

## Worked Example

Daily recurring order for one target:

- Canonical target: `PORT_A`
- Template: `tmpl_port_daily`
- Rule: daily, `15:00-17:00`, `Asia/Dubai`

Two dated instances:

1. `ord_port_2026_04_02`
   - `template_id = tmpl_port_daily`
   - `instance_key = PORT_A:2026-04-02`
   - `instance_local_date = 2026-04-02`
   - `planner_target_id = planner::PORT_A::2026-04-02`
   - `canonical_target_id = PORT_A`

2. `ord_port_2026_04_03`
   - `template_id = tmpl_port_daily`
   - `instance_key = PORT_A:2026-04-03`
   - `instance_local_date = 2026-04-03`
   - `planner_target_id = planner::PORT_A::2026-04-03`
   - `canonical_target_id = PORT_A`

Expected downstream lineage:

- `plan_items.order_id = ord_port_2026_04_02`
- `plan_items.template_id = tmpl_port_daily`
- `plan_items.instance_key = PORT_A:2026-04-02`
- `plan_items.canonical_target_id = PORT_A`
- `plan_items.display_target_name = PORT_A`

- `acquisitions.order_id = ord_port_2026_04_02`
- `acquisitions.template_id = tmpl_port_daily`
- `acquisitions.instance_key = PORT_A:2026-04-02`
- `acquisitions.canonical_target_id = PORT_A`
- `acquisitions.display_target_name = PORT_A`

## Notes For This Phase

- No scheduler algorithm changes are introduced here.
- No materialization engine is introduced here.
- No frontend UI is introduced here.
- Snapshot/rollback stays compatible because schedule snapshots already store `SELECT * FROM acquisitions`; once lineage columns exist on `acquisitions`, rollback preserves them automatically.
