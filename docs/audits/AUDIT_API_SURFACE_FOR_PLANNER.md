# AUDIT: API Surface for Planner

> PR-AUD-OPS-UI-LOCKS-PARITY — Ops Readiness Audit
> Generated: 2025-02-10

---

## 1. Summary of Current Behavior

The frontend communicates with the backend via a REST API centralized in `frontend/src/api/config.ts` and consumed through typed client functions in `frontend/src/api/scheduleApi.ts`. All endpoints use the `/api/v1/` prefix.

---

## 2. Complete Endpoint Map

### 2.1 Mission Analysis (Feasibility)

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/mission/analyze` | POST | `MissionContext.tsx` (fetch) | `backend/main.py` | Run feasibility analysis (orbit propagation + visibility) |
| `/api/v1/mission/czml` | GET | `MissionContext.tsx` | `backend/main.py` | Get CZML visualization data for Cesium |
| `/api/v1/mission/passes` | GET | `MissionResultsPanel.tsx` | `backend/main.py` | Get enriched pass data |
| `/api/v1/mission/geometry` | POST | Not directly used | `backend/main.py` | Point-in-time geometry analysis |
| `/api/v1/mission/lighting` | POST | Not directly used | `backend/main.py` | Lighting analysis at location |

### 2.2 TLE / Satellites

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/satellites` | GET | `MissionControls.tsx:207` | `backend/main.py` | List active satellites |
| `/api/v1/tle/parse` | POST | `AdminPanel.tsx` | `backend/main.py` | Parse TLE data |

### 2.3 Configuration

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/config/satellite-config-summary` | GET | `MissionPlanning.tsx:159` | `backend/routers/config_admin.py` | Read-only satellite bus/sensor specs |
| `/api/v1/config/sar-modes` | GET | `MissionParameters.tsx:76` | `backend/routers/config_admin.py` | SAR mode specifications |
| `/api/v1/config/satellites` | GET/PUT | `AdminPanel.tsx` | `backend/routers/config_admin.py` | Satellite config CRUD |
| `/api/v1/config/ground-stations` | GET | `AdminPanel.tsx` | `backend/routers/config_admin.py` | Ground station list |
| `/api/v1/config/mission-settings` | GET/PUT | `AdminPanel.tsx` | `backend/routers/config_admin.py` | Global mission settings |

### 2.4 Planning / Scheduling

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/planning/run` | POST | `MissionPlanning.tsx` (fetch) | `backend/main.py` | Run planning algorithm |
| `/api/planning/opportunities` | GET | `MissionPlanning.tsx:291` | `backend/main.py` | Get available opportunities |
| `/api/v1/schedule/plan` | POST | `scheduleApi.ts:createIncrementalPlan()` | `backend/routers/schedule.py` | Create incremental plan |
| `/api/v1/schedule/repair` | POST | `scheduleApi.ts:createRepairPlan()` | `backend/routers/schedule.py` | Create repair plan |
| `/api/v1/schedule/commit` | POST | `scheduleApi.ts:commitScheduleDirect()` | `backend/routers/schedule.py` | Commit plan to schedule |
| `/api/v1/schedule/repair/commit` | POST | `scheduleApi.ts:commitRepairPlan()` | `backend/routers/schedule.py` | Commit repair plan results |

### 2.5 Schedule State

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/schedule/state` | GET | `scheduleApi.ts:getScheduleState()` | `backend/routers/schedule.py` | Full schedule state snapshot |
| `/api/v1/schedule/horizon` | GET | `scheduleApi.ts:getScheduleHorizon()` | `backend/routers/schedule.py` | Schedule horizon with acquisitions |
| `/api/v1/schedule/context` | GET | `scheduleApi.ts:getScheduleContext()` | `backend/routers/schedule.py` | Schedule context for incremental planning |
| `/api/v1/schedule/conflicts` | GET | `scheduleApi.ts:getConflicts()` | `backend/routers/schedule.py` | Get scheduling conflicts |
| `/api/v1/schedule/conflicts/recompute` | POST | `scheduleApi.ts:recomputeConflicts()` | `backend/routers/schedule.py` | Recompute conflicts for workspace |

### 2.6 Lock Operations

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/schedule/acquisition/{id}/lock` | PUT | `scheduleApi.ts:updateAcquisitionLock()` | `backend/routers/schedule.py` | Update single acquisition lock |
| `/api/v1/schedule/acquisitions/bulk-lock` | POST | `scheduleApi.ts:bulkUpdateLocks()` | `backend/routers/schedule.py` | Bulk lock update |
| `/api/v1/schedule/acquisitions/hard-lock-committed` | POST | `scheduleApi.ts:hardLockAllCommitted()` | `backend/routers/schedule.py` | Hard-lock all committed in workspace |

### 2.7 Orders

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/orders` | GET | `scheduleApi.ts:getOrders()` | `backend/routers/orders.py` | List orders |
| `/api/v1/orders` | POST | `scheduleApi.ts:createOrder()` | `backend/routers/orders.py` | Create order |
| `/api/v1/orders/{id}` | PUT | `scheduleApi.ts:updateOrder()` | `backend/routers/orders.py` | Update order |
| `/api/v1/orders/{id}` | DELETE | `scheduleApi.ts:deleteOrder()` | `backend/routers/orders.py` | Delete order |

### 2.8 Workspaces

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/workspaces` | GET | `scheduleApi.ts:getWorkspaces()` | `backend/routers/workspaces.py` | List workspaces |
| `/api/v1/workspaces` | POST | `scheduleApi.ts:createWorkspace()` | `backend/routers/workspaces.py` | Create workspace |
| `/api/v1/workspaces/{id}` | GET | `scheduleApi.ts:getWorkspace()` | `backend/routers/workspaces.py` | Get workspace detail |
| `/api/v1/workspaces/{id}` | DELETE | `scheduleApi.ts:deleteWorkspace()` | `backend/routers/workspaces.py` | Delete workspace |

### 2.9 Batching

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/batch/run` | POST | `scheduleApi.ts:runBatch()` | `backend/routers/batching.py` | Execute batch planning |
| `/api/v1/batch/policies` | GET | `scheduleApi.ts:getBatchPolicies()` | `backend/routers/batching.py` | List batch policies |
| `/api/v1/batch/status` | GET | `scheduleApi.ts:getBatchStatus()` | `backend/routers/batching.py` | Get batch run status |

### 2.10 Validation

| Endpoint | Method | Frontend Client | Backend Router | Purpose |
| -------- | ------ | --------------- | -------------- | ------- |
| `/api/v1/validation/run` | POST | Not directly used | `backend/routers/validation.py` | Run validation scenario |
| `/api/v1/validation/scenarios` | GET | Not directly used | `backend/routers/validation.py` | List available scenarios |

---

## 3. Frontend API Client Architecture

### 3.1 Endpoint Constants

All endpoint URLs defined in `frontend/src/api/config.ts:1-73`:

```typescript
export const API_BASE = "/api/v1";
export const ENDPOINTS = {
  MISSION_ANALYZE: `${API_BASE}/mission/analyze`,
  SCHEDULE_STATE: `${API_BASE}/schedule/state`,
  SCHEDULE_HORIZON: `${API_BASE}/schedule/horizon`,
  SCHEDULE_COMMIT: `${API_BASE}/schedule/commit`,
  SCHEDULE_PLAN: `${API_BASE}/schedule/plan`,
  SCHEDULE_REPAIR: `${API_BASE}/schedule/repair`,
  // ... etc
};
```

### 3.2 Client Functions

Primary client in `frontend/src/api/scheduleApi.ts:1-1066`. All functions:
- Use `fetch()` with `Content-Type: application/json`
- Handle errors via `ApiError`, `NetworkError`, `TimeoutError` classes from `api/errors.ts`
- Return typed responses matching backend Pydantic schemas
- No authentication headers (no auth system implemented)

### 3.3 Type Generation

`frontend/scripts/generate-api-types.sh` generates TypeScript types from backend OpenAPI schema into `frontend/src/api/generated/api-types.ts`. The generated types mirror backend Pydantic models.

---

## 4. Request/Response Shapes for Key Workflows

### 4.1 Feasibility Analysis

**Request** (`MissionRequest` — `backend/schemas/mission.py:62-150`):

```typescript
{
  satellites: [{ name, line1, line2 }],  // TLE data
  targets: [{ name, latitude, longitude, priority, color }],
  start_time: "2025-02-10T00:00:00Z",
  end_time: "2025-02-11T00:00:00Z",
  mission_type: "imaging",
  imaging_type: "optical" | "sar",
  max_spacecraft_roll_deg: 45,
  sar?: { imaging_mode, incidence_min_deg, incidence_max_deg, look_side, pass_direction }
}
```

**Response** (`MissionResponse` — `backend/schemas/mission.py:153-157`):

```typescript
{
  success: boolean,
  message: string,
  data: {
    passes: [...],  // Per-target pass windows
    czml: [...],    // Cesium visualization data
    satellites: [...],  // Satellite info with colors
    summary: { total_passes, coverage, ... }
  }
}
```

### 4.2 Planning (Repair Mode)

**Request** (`RepairPlanRequest` — `scheduleApi.ts:468-498`):

```typescript
{
  workspace_id: "default",
  horizon_start: "2025-02-10T00:00:00Z",
  horizon_end: "2025-02-17T00:00:00Z",
  include_tentative: true,
  repair_scope: "workspace_horizon",
  max_changes: 100,
  objective: "maximize_score",
  look_window_s: 600,
  // ... slew config, weight config
}
```

**Response** (`RepairPlanResponse` — `scheduleApi.ts:500-530`):

```typescript
{
  success: boolean,
  message: string,
  plan_id: string,
  diff: {
    kept: [...],      // Unchanged acquisitions
    dropped: [...],   // Removed acquisitions
    added: [...],     // New acquisitions
    moved: [...]      // Rescheduled acquisitions
  },
  metrics: { kept_count, dropped_count, added_count, moved_count, changes_made, max_changes }
}
```

### 4.3 Lock Update

**Request** (PUT `/api/v1/schedule/acquisition/{id}/lock`):

```typescript
{ lock_level: "none" | "hard" }
```

**Response**:

```typescript
{ success: boolean, message: string }
```

---

## 5. Two Legacy Planning Paths (Inconsistency)

There are **two separate planning code paths**:

| Path | Trigger | Endpoint | Backend Handler | Notes |
| ---- | ------- | -------- | --------------- | ----- |
| Legacy (main.py) | "Run Planning" button | `/api/planning/run` | `backend/main.py` | Original algorithm runner; returns results directly |
| Persistent (schedule router) | Repair/Incremental mode | `/api/v1/schedule/repair` | `backend/routers/schedule.py` | New persistent path; creates plan in DB |

**Risk**: The legacy path (`/api/planning/run`) creates in-memory results that are NOT persisted. The new path (`/api/v1/schedule/repair`) writes to the schedule DB. Both are active and reachable from the UI. The frontend MissionPlanning component can trigger either depending on mode:
- `from_scratch` mode → legacy path
- `repair` / `incremental` mode → persistent path

---

## 6. Risks / Inconsistencies

1. **Two planning code paths**: Legacy (`/api/planning/run`) and persistent (`/api/v1/schedule/repair`) — should consolidate to persistent path only.
2. **No authentication**: All endpoints are unauthenticated. No user identity for audit trails.
3. **Workspace ID hardcoded**: Frontend often uses `"default"` workspace ID (`MissionPlanning.tsx:310`). Multi-workspace support exists in backend but is underutilized in UI.
4. **Mixed URL patterns**: Analysis endpoints use `/api/v1/mission/...` while planning uses both `/api/planning/...` (legacy) and `/api/v1/schedule/...` (new). Should consolidate under `/api/v1/`.
5. **Large `main.py` handler**: The main router (`backend/main.py`, 4058 lines) handles analysis, legacy planning, and CZML — should be split into focused routers.
6. **Generated types may drift**: `api-types.ts` is generated from OpenAPI but may not be regenerated after every backend change.

---

## 7. File References

| File | Lines | Purpose |
| ---- | ----- | ------- |
| `frontend/src/api/config.ts` | 1-73 | All API endpoint URL constants |
| `frontend/src/api/scheduleApi.ts` | 1-1066 | Typed API client functions |
| `frontend/src/api/errors.ts` | 1-~80 | Error classes (ApiError, NetworkError, TimeoutError) |
| `frontend/src/api/generated/api-types.ts` | whole file | Auto-generated TypeScript types from OpenAPI |
| `backend/main.py` | 1-4058 | Legacy analysis + planning routes |
| `backend/routers/schedule.py` | 1-2300 | Persistent schedule management routes |
| `backend/routers/orders.py` | whole file | Order CRUD routes |
| `backend/routers/workspaces.py` | whole file | Workspace management routes |
| `backend/routers/batching.py` | whole file | Batch planning routes |
| `backend/routers/config_admin.py` | whole file | Configuration admin routes |
| `backend/routers/validation.py` | whole file | Validation scenario routes |
| `backend/schemas/mission.py` | 1-157 | Mission request/response schemas |
| `backend/schemas/planning.py` | 1-105 | Planning request/response schemas |

---

## 8. Recommended Minimal Change Strategy

1. **Deprecate legacy planning path**: Add a deprecation warning to `/api/planning/run`. Route all planning through `/api/v1/schedule/repair` (persistent path). This ensures all plans are persisted and auditable.
2. **Consolidate URL patterns**: Move remaining `/api/planning/...` endpoints under `/api/v1/schedule/...` with backward-compatible redirects.
3. **Regenerate API types**: Run `frontend/scripts/generate-api-types.sh` after any backend schema changes to keep `api-types.ts` in sync.
