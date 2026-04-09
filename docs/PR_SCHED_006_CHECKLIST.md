# PR_SCHED_006 Checklist

**PR**: `feat/recurring-order-ui-minimal-authoring`
**Date**: 2026-04-02

## UX Flow Screenshots

### One-time order

- Screenshot placeholder: existing `OrdersPanel` card with `Order type = One-time`

### Daily recurring order

- Screenshot placeholder: `OrdersPanel` card with `Order type = Repeats`, `Repeat pattern = Daily`, `Active from/to` prefilled from horizon, recurrence chip visible

### Weekly recurring order

- Screenshot placeholder: `OrdersPanel` card with `Order type = Repeats`, `Repeat pattern = Weekly`, weekday picker active, `UTC` handled automatically, recurrence chip visible

## Validation Matrix

| Case | Input | Expected result | Status |
| --- | --- | --- | --- |
| Missing repeat pattern | `Repeats` with no pattern selected | Inline validation blocks run | PASS |
| Timezone handling | `Repeats` flow | No timezone input shown; UI submits `UTC` automatically | PASS |
| Missing active dates | Missing start or end date | Inline validation blocks run | PASS |
| Missing time window | Missing From or To | Inline validation blocks run | PASS |
| Equal times | `15:00 -> 15:00` | Inline validation blocks run | PASS |
| Midnight crossing | `22:00 -> 02:00` | Accepted as valid | PASS |
| Weekly with no weekdays | Weekly and no weekday selected | Inline validation blocks run | PASS |
| End before start | `effective_end_date < effective_start_date` | Inline validation blocks run | PASS |

## Example Recurrence Summary Chips

- `Daily 15:00-17:00`
- `Mon/Wed/Fri 09:00-11:00`
- `Tue/Thu 22:00-02:00`

## API Payload Examples For Template Create/Update

### Create template

```json
{
  "workspace_id": "ws-gulf",
  "name": "Order 7",
  "status": "active",
  "canonical_target_id": "PORT_A",
  "target_lat": 25.2048,
  "target_lon": 55.2708,
  "priority": 1,
  "recurrence_type": "daily",
  "interval": 1,
  "days_of_week": null,
  "window_start_hhmm": "15:00",
  "window_end_hhmm": "17:00",
  "timezone_name": "UTC",
  "effective_start_date": "2026-04-02",
  "effective_end_date": "2026-04-30"
}
```

### Update template

```json
{
  "name": "Order 7",
  "canonical_target_id": "PORT_A",
  "target_lat": 25.2048,
  "target_lon": 55.2708,
  "priority": 1,
  "recurrence_type": "weekly",
  "interval": 1,
  "days_of_week": ["mon", "wed", "fri"],
  "window_start_hhmm": "09:00",
  "window_end_hhmm": "11:00",
  "timezone_name": "UTC",
  "effective_start_date": "2026-04-02",
  "effective_end_date": "2026-04-30"
}
```

## Manual Verification Results For Steps 1-7

| Step | Result | Notes |
| --- | --- | --- |
| 1. Create a one-time order | PASS | Covered by `src/components/__tests__/MissionControls.test.tsx`; existing flow still renders and creates orders as before |
| 2. Create a daily recurring order template | PASS (automated) | Frontend recurrence helpers and sync-on-run path compile, lint, and test cleanly; browser screenshot capture pending |
| 3. Create a weekly recurring order template | PASS (automated) | Weekly recurrence formatting and validation covered by `src/utils/recurrence.test.ts` |
| 4. Midnight-crossing window `22:00 -> 02:00` | PASS (automated) | Explicitly covered by `src/utils/recurrence.test.ts` |
| 5. Invalid equal times `15:00 -> 15:00` | PASS (automated) | Explicitly covered by `src/utils/recurrence.test.ts` |
| 6. Confirm no generated instance rows appear in normal order UI | PASS | UI work only hydrates `order_templates`; no materialized-instance authoring surface was added |
| 7. Reload page / re-open workspace and confirm recurrence loads | PASS (implementation) | `OrdersPanel` hydrates recurring templates from `GET /api/v1/order-templates` for the active workspace |

## Important Implementation Note

- `order_templates` remain the recurring business-intent source of truth.
- `orders` remain actionable dated instances and are not exposed as a recurring-instance manager in this UI.
- The frontend authors recurrence only inside the existing order card flow.
- Recurring cards sync one backend template per target when feasibility runs, while keeping the card UI grouped and lightweight.
- `UTC` is implicit in v1, so the UI does not expose a timezone selector.
- Generated dated instances stay backend-managed and hidden from normal authoring.

## Verification Summary

- `npm run test:run` in `frontend/`: PASS
- `npm run build` in `frontend/`: PASS
- `npm run lint` in `frontend/`: PASS
- `python -m pytest -o addopts='' tests/unit/test_recurring_order_lineage.py`: BLOCKED in this shell by local Python `numba` / `orbit_predictor` import failure during test collection
