# PR_SCHED_008 Checklist

## Scope

Align Feasibility Analysis authoring with the single-order-per-run decision.

- one active pre-feasibility order only
- many targets inside that order
- recurring configuration authored on that single order
- recurring terminology updated from `Repeat pattern` to `Frequency`
- architecture note added for future left-timeline daily acquisition summaries

## Implemented

- Refactored the frontend pre-feasibility store to hold `order | null` instead of parallel local orders.
- Guarded `createOrder()` so it reuses the existing order instead of creating a second one.
- Updated `OrdersPanel` to render one order card and hide the create action once the order exists.
- Kept map-click, inline add, upload, and sample-target flows pointed at the single order.
- Updated `MissionControls` validation and analyze payload creation to read targets from the single order.
- Renamed the recurrence field label to `Frequency`.
- Updated recurring copy from `Repeats` / `repeating` wording toward `Recurring` where it affected the operator flow.

## Files Touched

### Frontend

- `frontend/src/store/preFeasibilityOrdersStore.ts`
- `frontend/src/store/preFeasibilityOrdersStore.test.ts`
- `frontend/src/store/index.ts`
- `frontend/src/components/OrdersPanel.tsx`
- `frontend/src/components/MissionControls.tsx`
- `frontend/src/components/Targets/TargetConfirmPanel.tsx`
- `frontend/src/components/Map/hooks/useEntitySelection.ts`
- `frontend/src/components/Map/GlobeViewport.tsx`
- `frontend/src/components/__tests__/MissionControls.test.tsx`
- `frontend/src/components/__tests__/defaultPriority.test.ts`
- `frontend/src/utils/recurrence.ts`
- `frontend/src/utils/recurrence.test.ts`

### Docs

- `docs/PR_SCHED_008_CHECKLIST.md`
- `docs/architecture/SINGLE_ORDER_PER_RUN.md`

## Behavioral Checks

- A second pre-feasibility order cannot be created in the same run.
- Targets can still be added many times to the single order.
- Recurring frequency remains order-level, not target-level, in the authoring UX.
- Feasibility still sends a flat `targets[]` payload to the backend, but now it comes from one run-level order.
- Legacy hydrated order fragments are normalized into a single frontend order on load.

## Visualization Note

Documented only.

- No new left-timeline visualization is implemented here.
- The future shape should summarize acquisition counts per day for the single order.
- Detailed daily or demand-level visualization remains follow-up work.

## Validation

- `npm run test:run -- src/components/__tests__/MissionControls.test.tsx src/components/__tests__/defaultPriority.test.ts src/store/preFeasibilityOrdersStore.test.ts src/utils/recurrence.test.ts`
- `npx eslint src/components/MissionControls.tsx src/components/OrdersPanel.tsx src/components/Targets/TargetConfirmPanel.tsx src/components/Map/hooks/useEntitySelection.ts src/components/Map/GlobeViewport.tsx src/store/preFeasibilityOrdersStore.ts src/store/preFeasibilityOrdersStore.test.ts src/components/__tests__/MissionControls.test.tsx src/components/__tests__/defaultPriority.test.ts src/utils/recurrence.ts src/utils/recurrence.test.ts`

## Non-Goals

- No scheduler or backend schema changes
- No full demand-day visualization
- No new schedule timeline implementation
