# API Surface Used by UI

**Last Updated:** 2026-02-05  
**Source:** End-to-end audit of frontend API calls

---

## Summary

| Category | Total Endpoints | Used by UI | Admin Only | Not Used |
|----------|-----------------|------------|------------|----------|
| Schedule | 12 | 10 | 0 | 2 |
| Orders | 8 | 3 | 0 | 5 |
| Workspaces | 8 | 8 | 0 | 0 |
| Batching | 7 | 2 | 5 | 0 |
| Config | 6 | 6 | 0 | 0 |
| Mission | 3 | 3 | 0 | 0 |
| **Total** | **44** | **32** | **5** | **7** |

---

## 1. Schedule Endpoints (`/api/v1/schedule/*`)

### Used by UI

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| POST | `/api/v1/schedule/commit/direct` | `commitScheduleDirect()` | LeftSidebar | Commit plan to acquisitions |
| GET | `/api/v1/schedule/horizon` | `getScheduleHorizon()` | MissionPlanning | Get committed schedule range |
| GET | `/api/v1/schedule/state` | `getScheduleState()` | MissionPlanning | Get acquisition counts |
| GET | `/api/v1/schedule/conflicts` | `getConflicts()` | ConflictsPanel | List detected conflicts |
| POST | `/api/v1/schedule/conflicts/recompute` | `recomputeConflicts()` | ConflictsPanel | Refresh conflict detection |
| POST | `/api/v1/schedule/repair` | `createRepairPlan()` | MissionPlanning | Generate repair plan |
| POST | `/api/v1/schedule/repair/commit` | `commitRepairPlan()` | RepairCommitModal | Commit repair changes |
| PATCH | `/api/v1/schedule/acquisitions/{id}/lock` | `updateAcquisitionLock()` | - | Update single lock |
| PATCH | `/api/v1/schedule/acquisitions/lock` | `bulkUpdateLocks()` | MissionPlanning | Bulk lock update |
| POST | `/api/v1/schedule/context` | `getScheduleContext()` | MissionPlanning | Get planning context |

### Not Used by UI

| Method | Endpoint | Backend Location | Notes |
|--------|----------|------------------|-------|
| POST | `/api/v1/schedule/commit` | schedule.py:653 | Plan-based commit (UI uses direct) |
| GET | `/api/v1/schedule/audit` | schedule.py:849 | Commit history (no UI panel) |

---

## 2. Orders Endpoints (`/api/v1/orders/*`)

### Used by UI

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| GET | `/api/v1/orders` | `listOrders()` | (indirect) | List orders |
| GET | `/api/v1/orders/{id}` | - | - | Get single order |
| PATCH | `/api/v1/orders/{id}` | `updateOrderStatus()` | - | Update order status |

### Not Used by UI (API-only or Admin)

| Method | Endpoint | Backend Location | Notes |
|--------|----------|------------------|-------|
| POST | `/api/v1/orders` | orders.py:325 | Create order - UI uses promote flow |
| POST | `/api/v1/orders/import` | orders.py:385 | Bulk import - no UI |
| GET | `/api/v1/orders/inbox` | orders.py:254 | Inbox with scoring - no panel |
| POST | `/api/v1/orders/{id}/reject` | orders.py:520 | Reject order - no button |
| POST | `/api/v1/orders/{id}/defer` | orders.py:591 | Defer order - no button |

---

## 3. Workspace Endpoints (`/api/v1/workspaces/*`)

### All Used by UI

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| GET | `/api/v1/workspaces` | `listWorkspaces()` | WorkspacePanel | List saved workspaces |
| POST | `/api/v1/workspaces` | `createWorkspace()` | WorkspacePanel | Create workspace |
| GET | `/api/v1/workspaces/{id}` | `getWorkspace()` | WorkspacePanel | Load workspace |
| PUT | `/api/v1/workspaces/{id}` | `updateWorkspace()` | WorkspacePanel | Update workspace |
| DELETE | `/api/v1/workspaces/{id}` | `deleteWorkspace()` | WorkspacePanel | Delete workspace |
| POST | `/api/v1/workspaces/save-current` | `saveCurrentMission()` | WorkspacePanel | Save current state |
| POST | `/api/v1/workspaces/{id}/export` | `exportWorkspace()` | WorkspacePanel | Export to JSON |
| POST | `/api/v1/workspaces/import` | `importWorkspace()` | WorkspacePanel | Import from JSON |

---

## 4. Batching Endpoints (`/api/v1/batches/*`)

### Used by UI (Admin Panel)

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| GET | `/api/v1/batches/policies` | `listPolicies()` | AdminPanel | List planning policies |
| GET | `/api/v1/batches` | `listBatches()` | AdminPanel | List batches |

### Admin Only (Not Exposed in Mission Planner Mode)

| Method | Endpoint | Backend Location | Notes |
|--------|----------|------------------|-------|
| POST | `/api/v1/batches/create` | batching.py:246 | Create batch |
| GET | `/api/v1/batches/{id}` | batching.py:334 | Get batch details |
| POST | `/api/v1/batches/{id}/plan` | batching.py:398 | Plan batch |
| POST | `/api/v1/batches/{id}/commit` | batching.py:555 | Commit batch |
| POST | `/api/v1/batches/{id}/cancel` | batching.py:688 | Cancel batch |

---

## 5. Config Endpoints (`/api/config/*`, `/api/satellites`, etc.)

### Used by UI

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| GET | `/api/satellites` | `fetch('/api/satellites')` | MissionControls, AdminPanel | List satellites |
| PUT | `/api/satellites/{id}` | `fetch(PUT)` | AdminPanel | Update satellite |
| DELETE | `/api/satellites/{id}` | `fetch(DELETE)` | AdminPanel | Delete satellite |
| GET | `/api/config/sar-modes` | `getSarModes()` | AdminPanel | List SAR modes |
| GET | `/api/config/ground-stations` | `getGroundStations()` | AdminPanel | List ground stations |
| GET | `/api/config/mission-settings` | `getMissionSettings()` | AdminPanel | Get mission defaults |

---

## 6. Mission/Planning Endpoints

### Used by UI

| Method | Endpoint | Frontend Caller | Component | Purpose |
|--------|----------|-----------------|-----------|---------|
| POST | `/api/analyze` | MissionContext dispatch | MissionControls | Run mission analysis |
| POST | `/api/planning/schedule` | `fetch('/api/planning/schedule')` | MissionPlanning | Run scheduling |
| GET | `/api/planning/opportunities` | - | MissionPlanning | Get cached opps |

---

## Request/Response Field Mapping

### Key Types

#### `DirectCommitRequest` (Frontend → Backend)

```typescript
interface DirectCommitRequest {
  items: DirectCommitItem[];
  algorithm: string;
  mode?: "from_scratch" | "incremental";
  lock_level?: "soft" | "hard";
  workspace_id?: string;
}

interface DirectCommitItem {
  opportunity_id: string;
  satellite_id: string;
  target_id: string;
  start_time: string;
  end_time: string;
  roll_angle_deg: number;
  pitch_angle_deg: number;
  value?: number;
  incidence_angle_deg?: number;
  sar_mode?: string;
  look_side?: string;
  pass_direction?: string;
}
```

**Backend Model:** `DirectCommitRequest` in `schedule.py:106`

#### `DirectCommitResponse` (Backend → Frontend)

```typescript
interface DirectCommitResponse {
  success: boolean;
  message?: string;
  plan_id?: string;
  acquisitions_created?: number;
  acquisition_ids?: string[];
  conflicts_detected?: number;
}
```

**Backend Model:** `DirectCommitResponse` in `schedule.py:152`

---

#### `RepairPlanRequest` (Frontend → Backend)

```typescript
interface RepairPlanRequest {
  workspace_id: string;
  horizon_from: string;
  horizon_to: string;
  repair_objectives: {
    maximize_score: boolean;
    minimize_conflicts: boolean;
    preserve_hard_locks: boolean;
  };
  opportunities: Opportunity[];
  // Algorithm config fields...
}
```

**Backend Model:** `RepairRequest` in `schedule.py:179`

#### `RepairPlanResponse` (Backend → Frontend)

```typescript
interface RepairPlanResponse {
  success: boolean;
  message?: string;
  plan_id?: string;
  existing_acquisitions: { count: number; ids: string[] };
  new_plan_items: PlanItem[];
  repair_diff: RepairDiff;
  metrics_comparison: MetricsComparison;
  commit_preview: CommitPreview;
}
```

**Backend Model:** `RepairResponse` in `schedule.py:224`

---

#### `Conflict` Type

```typescript
interface Conflict {
  id: string;
  type: "temporal_overlap" | "slew_infeasible" | string;
  severity: "error" | "warning" | "info";
  description?: string;
  acquisition_ids: string[];
  detected_at: string;
  resolved_at?: string;
}
```

**Backend Model:** `Conflict` dataclass in `schedule_persistence.py:324`

---

## Field Consistency Audit

### ✅ Consistent Fields

| Field | Frontend Type | Backend Model | DB Column | Status |
|-------|---------------|---------------|-----------|--------|
| `satellite_id` | string | str | satellite_id | ✅ |
| `target_id` | string | str | target_id | ✅ |
| `start_time` | string (ISO) | str | start_time | ✅ |
| `end_time` | string (ISO) | str | end_time | ✅ |
| `roll_angle_deg` | number | float | roll_angle_deg | ✅ |
| `pitch_angle_deg` | number | float | pitch_angle_deg | ✅ |
| `incidence_angle_deg` | number? | Optional[float] | incidence_angle_deg | ✅ |
| `sar_mode` | string? | Optional[str] | sar_mode | ✅ |
| `look_side` | string? | Optional[str] | look_side | ✅ |
| `pass_direction` | string? | Optional[str] | pass_direction | ✅ |

### ⚠️ Naming Inconsistencies (Minor)

| Frontend | Backend | Notes |
|----------|---------|-------|
| `value` | `quality_score` | Both used, mapped in handler |
| `roll_angle` | `roll_angle_deg` | Frontend uses both interchangeably |
| `droll_deg` | `delta_roll` | Legacy AcceptedOrders vs new |

---

## Error Codes

| HTTP Code | API Meaning | UI Display |
|-----------|-------------|------------|
| 200 | Success | Success toast / update state |
| 400 | Validation error | Show `detail` field |
| 404 | Resource not found | "Not found" message |
| 409 | Conflict (commit) | Show conflict details |
| 422 | Unprocessable entity | Show validation errors |
| 500 | Server error | "Something went wrong" + log |

### Error Response Shape

```json
{
  "success": false,
  "message": "Human-readable error",
  "detail": "Technical detail (optional)",
  "errors": ["field-specific errors"]
}
```

---

## API Versioning

- **Current Version:** v1
- **Base Path:** `/api/v1/`
- **Legacy Endpoints:** Some endpoints at `/api/` (non-versioned) for backwards compatibility
  - `/api/analyze`
  - `/api/satellites`
  - `/api/planning/schedule`

**Recommendation:** Migrate legacy endpoints to `/api/v1/` in future release.
