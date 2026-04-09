# PR_SCHED_009 Checklist

## Scope

Align feasibility/planning contracts with the single-order-per-run architecture by introducing demand-aware request and response models.

- keep one run order as the authored container
- keep many targets inside that order
- expand recurring work into dated planning demands inside the horizon
- expose normalized demand-level summaries in feasibility results
- avoid scheduler algorithm changes and UI rewrites in this phase

## Implemented

- Added additive `run_order` metadata to the mission analyze contract.
- Added normalized demand-aware response fields:
  - `mission_data.run_order`
  - `mission_data.planning_demands`
  - `mission_data.planning_demand_summary`
- Formalized one common planning demand shape for:
  - one-time target demand
  - recurring dated instance demand
- Reused recurring lineage vocabulary already present elsewhere:
  - `canonical_target_id`
  - `template_id`
  - `instance_key`
- Kept canonical opportunity generation and the current scheduler unchanged.
- Updated the frontend request builder to send the single run-order contract from the new pre-feasibility store shape.
- Updated frontend runtime validation so the new demand-aware fields are preserved instead of stripped.

## Files Touched

### Backend

- `backend/main.py`
- `backend/planning_demands.py`
- `backend/schemas/mission.py`
- `tests/unit/test_planning_demands.py`

### Frontend

- `frontend/src/types/index.ts`
- `frontend/src/api/mission.ts`
- `frontend/src/api/schemas/index.ts`
- `frontend/src/api/__tests__/missionSchema.test.ts`
- `frontend/src/context/MissionContext.tsx`
- `frontend/src/components/MissionControls.tsx`
- `frontend/src/components/__tests__/MissionControls.test.tsx`
- `frontend/src/utils/planningDemand.ts`

### Docs

- `docs/PR_SCHED_009_CHECKLIST.md`
- `docs/architecture/PLANNING_DEMAND_CONTRACT.md`

## Behavioral Checks

- A one-time run order yields one planning demand per target.
- A recurring run order yields one dated planning demand per target occurrence inside the horizon.
- Demand summaries are filtered by each demand's requested window, not just by canonical target label.
- Existing `targets[]` and `passes[]` remain available so current UI surfaces stay intact.
- Demand-aware fields are additive and ready for future `Demand View` and `Master Timeline` work.

## Non-goals

- No scheduler algorithm changes
- No planning heuristic changes
- No full Feasibility Results redesign
- No new timeline visualization implementation
