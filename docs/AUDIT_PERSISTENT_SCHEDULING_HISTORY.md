# Audit: Persistent Schedule History + Reshuffling Planner UX

**Branch:** `audit/persistent-scheduling-history-reshuffle`
**Date:** 2025-01-22
**Status:** Audit + Discovery + Minimal Instrumentation

---

## Table of Contents

1. [Section 1 — As-Is (Current State)](#section-1--as-is-current-state)
2. [Section 2 — To-Be (Industry Model)](#section-2--to-be-industry-model)
3. [Section 3 — Scheduling Modes](#section-3--scheduling-modes)
4. [Section 4 — Reshuffling Policy Options](#section-4--reshuffling-policy-options)
5. [Section 5 — UX Proposal (Mission Planner Grade)](#section-5--ux-proposal-mission-planner-grade)
6. [Section 6 — API Proposals](#section-6--api-proposals)
7. [Section 7 — Data Model Proposal](#section-7--data-model-proposal)
8. [Audit Checklist Answers](#audit-checklist-answers)
9. [Instrumentation Added](#instrumentation-added)

---

## Section 1 — As-Is (Current State)

### 1.1 Current Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CURRENT PLANNING WORKFLOW                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   ANALYSIS   │───▶│   PLANNING   │───▶│   PROMOTE    │───▶│  DISAPPEARS  │
│              │    │              │    │  TO ORDERS   │    │              │
│ POST /api/   │    │ POST /api/   │    │  (Frontend   │    │ (Page reload │
│ mission/     │    │ planning/    │    │   only)      │    │  loses all)  │
│ analyze      │    │ schedule     │    │              │    │              │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
       │                   │                   │                    │
       ▼                   ▼                   ▼                    ▼
  Passes stored       Schedule in          AcceptedOrder       Orders exist
  in memory           response only        in Zustand +        only in
  (global var)        (no persistence)     localStorage        workspace blob
```

### 1.2 Current Input Contract (Planning Request)

**Endpoint:** `POST /api/planning/schedule`

**Request Model (`PlanningRequest`):**
```python
class PlanningRequest(BaseModel):
    # Agility parameters
    imaging_time_s: float = 5.0           # Time on target (tau)
    max_roll_rate_dps: float = 1.0        # Max roll rate (deg/s)
    max_roll_accel_dps2: float = 10000.0  # Max roll acceleration
    max_pitch_rate_dps: float = 1.0       # Max pitch rate (deg/s)
    max_pitch_accel_dps2: float = 10000.0 # Max pitch acceleration

    # Algorithm selection
    algorithms: List[str] = ["first_fit"]

    # Value source
    value_source: str = "uniform"  # uniform | target_priority | custom
    custom_values: Optional[Dict[str, float]] = None

    # Algorithm parameters
    look_window_s: float = 600.0

    # Quality model
    quality_model: str = "monotonic"  # off | monotonic | band
    ideal_incidence_deg: float = 35.0
    band_width_deg: float = 7.5

    # Multi-criteria weights
    weight_priority: float = 40.0
    weight_geometry: float = 40.0
    weight_timing: float = 20.0
    weight_preset: Optional[str] = None
```

### 1.3 Current Object Models

#### Opportunity (Input to Scheduler)
```python
@dataclass
class Opportunity:
    id: str                           # Generated: "{sat}_{target}_{idx}_{time_type}"
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float = 0.0

    # Pointing angles (SIGNED)
    incidence_angle: Optional[float]  # Off-nadir angle
    pitch_angle: Optional[float]      # Along-track pointing

    # Priority/value
    value: float = 1.0
    priority: int = 1

    # SAR-specific fields
    mission_mode: Optional[str]       # "SAR" | "OPTICAL"
    sar_mode: Optional[str]           # "spot" | "strip" | "scan" | "dwell"
    look_side: Optional[str]          # "LEFT" | "RIGHT"
    pass_direction: Optional[str]     # "ASCENDING" | "DESCENDING"
    incidence_center_deg: Optional[float]
    swath_width_km: Optional[float]
    scene_length_km: Optional[float]
    sar_quality_score: Optional[float]
```

#### ScheduledOpportunity (Output from Scheduler)
```python
@dataclass
class ScheduledOpportunity:
    opportunity_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime

    # Maneuver details
    delta_roll: float         # Degrees change from previous
    delta_pitch: float = 0.0
    roll_angle: float = 0.0   # Absolute roll from nadir
    pitch_angle: float = 0.0  # Absolute pitch from nadir
    maneuver_time: float = 0.0
    slack_time: float = 0.0

    # Metrics
    value: float = 1.0
    density: float = 0.0      # value / maneuver_time
    incidence_angle: Optional[float]

    # Satellite position (for visualization)
    satellite_lat: Optional[float]
    satellite_lon: Optional[float]
    satellite_alt: Optional[float]

    # SAR-specific fields (copied from Opportunity)
    mission_mode: Optional[str]
    sar_mode: Optional[str]
    look_side: Optional[str]
    pass_direction: Optional[str]
    incidence_center_deg: Optional[float]
    swath_width_km: Optional[float]
    scene_length_km: Optional[float]
    swath_polygon: Optional[List[Tuple[float, float]]]
```

#### AcceptedOrder (Frontend Only)
```typescript
interface AcceptedOrder {
  order_id: string;           // Generated: "order_{timestamp}_{random}"
  name: string;               // "{algorithm}-{datetime}"
  created_at: string;
  algorithm: "first_fit" | "best_fit" | "roll_pitch_first_fit" | "roll_pitch_best_fit" | "optimal";

  metrics: {
    accepted: number;
    rejected: number;
    total_value: number;
    mean_incidence_deg: number;
    imaging_time_s: number;
    maneuver_time_s: number;
    utilization: number;
    runtime_ms: number;
  };

  schedule: Array<{
    opportunity_id: string;
    satellite_id: string;
    target_id: string;
    start_time: string;
    end_time: string;
    droll_deg: number;
    t_slew_s: number;
    slack_s: number;
    value: number;
    density: number | "inf";
  }>;

  satellites_involved?: string[];
  targets_covered?: string[];
}
```

### 1.4 How "Accept Order" Currently Works

**Location:** `frontend/src/components/LeftSidebar.tsx:handlePromoteToOrders()`

**Current Flow:**
1. User clicks "Promote to Orders" button in PlanningPanel
2. Frontend creates `AcceptedOrder` object with:
   - Generated `order_id`: `order_{Date.now()}_{random}`
   - Copy of schedule items from `AlgorithmResult`
   - Aggregated metrics
3. Order added to Zustand store (`useOrdersStore`)
4. Order persisted to `localStorage` key: `acceptedOrders`
5. **On workspace save:** Orders included in `orders_state` blob

**Where Orders Are Lost:**
- Page reload without workspace save
- Backend restart loses `current_mission_data`
- No backend persistence of accepted orders
- No unique constraint enforcement (can accept same schedule multiple times)

### 1.5 Current Persistence Layer

**Database:** SQLite via `backend/workspace_persistence.py`

**Schema:**
```sql
-- Core workspace table
CREATE TABLE workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    schema_version TEXT DEFAULT '1.0',
    app_version TEXT,
    mission_mode TEXT,
    time_window_start TEXT,
    time_window_end TEXT,
    satellites_count INTEGER DEFAULT 0,
    targets_count INTEGER DEFAULT 0,
    last_run_status TEXT,
    last_run_timestamp TEXT
);

-- State blobs (JSON storage)
CREATE TABLE workspace_blobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id),
    scenario_config_json TEXT,      -- Satellites, targets, constraints
    analysis_state_json TEXT,        -- Passes, opportunities
    planning_state_json TEXT,        -- Algorithm results
    orders_state_json TEXT,          -- AcceptedOrders (JSON blob!)
    ui_state_json TEXT,
    czml_blob BLOB,                  -- Compressed CZML
    config_hash TEXT,
    UNIQUE(workspace_id)
);
```

**Key Observation:** Orders are stored as unstructured JSON blobs inside `orders_state_json`. There is **no normalized orders table** with proper indexing or query capability.

### 1.6 Current Identifiers & Determinism

| Entity | ID Format | Stable Across Runs? | Notes |
|--------|-----------|---------------------|-------|
| `target_id` | User-provided name | ✅ Yes | e.g., "Athens", "Berlin" |
| `satellite_id` | TLE name | ✅ Yes | e.g., "ICEYE-X44" |
| `opportunity_id` | `{sat}_{target}_{idx}_{time_type}` | ⚠️ Partially | Index depends on pass order |
| `order_id` | `order_{timestamp}_{random}` | ❌ No | Random component |
| `workspace_id` | UUID | ✅ Yes | Generated once on create |

**Reproducibility Gaps:**
- No config hash stored with planning results
- No seed for deterministic scheduling
- Pass index in opportunity_id varies with analysis parameters

---

## Section 2 — To-Be (Industry Model)

### 2.1 Operational Concepts

#### Order (User Intent)
A **request** from the customer or mission planner to acquire imagery of a target.

```
Order = "I want to image Target X within time window [T1, T2] with priority P"
```

**Properties:**
- Represents **intent**, not execution
- May have multiple fulfillment options
- Can be cancelled, modified, or superseded
- Has lifecycle: `new` → `planned` → `committed` → `executed` → `archived`

#### Acquisition (Scheduled Execution)
A **committed slot** in the satellite's timeline that will result in an image.

```
Acquisition = "Satellite S will image Target X at time T with geometry G"
```

**Properties:**
- Represents **commitment** to execute
- Consumes satellite resources (time, attitude, memory)
- Has lock level: `tentative` | `soft_locked` | `hard_locked`
- State: `tentative` → `locked` → `committed` → `executing` → `completed/failed`

#### Plan (Candidate Schedule)
A **proposed arrangement** of acquisitions that satisfies constraints.

```
Plan = "Here's how we could fulfill Orders O1-O5 using Satellites S1-S3"
```

**Properties:**
- Ephemeral until committed
- Can be compared with alternatives
- Has score/metrics for evaluation
- Multiple plans can exist simultaneously for comparison

### 2.2 Schedule Horizon

The **time window** for which a schedule is valid and managed.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         SCHEDULE HORIZON                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  FROZEN ZONE    │  PLANNING ZONE          │  FORECAST ZONE              │
│  (T-2h to T)    │  (T to T+48h)           │  (T+48h to T+7d)            │
│                 │                          │                             │
│  - Hard locked  │  - Active planning       │  - Tentative only           │
│  - No changes   │  - Soft locks allowed    │  - No commitments           │
│  - Executing    │  - Reshuffling possible  │  - Opportunity analysis     │
│                 │                          │                             │
└─────────────────────────────────────────────────────────────────────────┘
         NOW ──────────────────────────────────────────────────────▶ TIME
```

### 2.3 Lock Levels

| Level | Description | Can Move? | Can Delete? |
|-------|-------------|-----------|-------------|
| `tentative` | Candidate, not committed | ✅ Yes | ✅ Yes |
| `soft_locked` | Committed but flexible | ⚠️ Within window | ❌ No |
| `hard_locked` | Frozen, immutable | ❌ No | ❌ No |

### 2.4 Conflict Types

1. **Temporal Overlap** — Two acquisitions on same satellite overlap in time
2. **Resource Contention** — Insufficient slew time between consecutive acquisitions
3. **Downlink Window** — Data acquired but no downlink opportunity before memory full
4. **Ground Conflict** — Same target requested by multiple orders with different constraints
5. **Slew Infeasibility** — Required attitude change exceeds spacecraft agility

---

## Section 3 — Scheduling Modes

### Mode 1: Plan from Scratch (Empty Horizon)

**Use Case:** Initial planning for a new mission or clean horizon.

**Behavior:**
- Ignores any existing acquisitions
- Full optimization freedom
- All opportunities considered equally

**API:**
```http
POST /api/v1/schedule/plan
{
  "mode": "from_scratch",
  "horizon": { "start": "...", "end": "..." },
  "orders": [...],
  "config": { ... }
}
```

### Mode 2: Plan with History (Respect Existing)

**Use Case:** Add new orders to existing schedule without disruption.

**Behavior:**
- Loads existing acquisitions as constraints
- New opportunities evaluated around locked items
- No modification of existing schedule

**API:**
```http
POST /api/v1/schedule/plan
{
  "mode": "incremental",
  "horizon": { "start": "...", "end": "..." },
  "orders": [...],  // New orders only
  "respect_existing": true,
  "config": { ... }
}
```

### Mode 3: Reshuffle / Repair

**Use Case:** Optimize schedule while respecting locks and constraints.

**Behavior:**
- Hard-locked items remain fixed
- Soft-locked items can move within windows
- Tentative items freely rescheduled
- Goal: Improve metrics while honoring commitments

**API:**
```http
POST /api/v1/schedule/reshuffle
{
  "horizon": { "start": "...", "end": "..." },
  "policy": "soft_reoptimize",  // See Section 4
  "freeze_window_hours": 2,
  "config": { ... }
}
```

---

## Section 4 — Reshuffling Policy Options

### Policy 1: Hard-Lock Accepted Acquisitions

```yaml
policy: "hard_lock_committed"
description: "Once committed, acquisition cannot move or be deleted"
behavior:
  - All committed acquisitions are immutable
  - New planning works around them
  - Only way to change: explicit manual unlock
use_case: "High-reliability missions, customer commitments"
```

### Policy 2: Soft-Lock (Move Within Window)

```yaml
policy: "soft_lock_windowed"
description: "Committed acquisitions can shift within original order window"
behavior:
  - Acquisition must stay within order's requested_window
  - Can move earlier/later to accommodate better fits
  - Cannot change target or satellite
use_case: "Flexible commercial operations"
parameters:
  max_shift_minutes: 30  # Maximum time shift allowed
```

### Policy 3: Replace-If-Better

```yaml
policy: "replace_if_better"
description: "Replace existing acquisition if new option scores higher"
behavior:
  - Compare current vs proposed acquisition score
  - Replace only if improvement exceeds threshold
  - Requires explicit score function
use_case: "Quality-optimizing archival missions"
parameters:
  improvement_threshold_pct: 10  # Must be 10% better to replace
  score_function: "geometry"     # or "priority", "composite"
```

### Policy 4: Freeze Horizon Segments

```yaml
policy: "time_based_freeze"
description: "Freeze acquisitions within N hours of execution"
behavior:
  - Acquisitions within freeze_window: hard-locked
  - Acquisitions outside: soft-locked or tentative
  - Automatic promotion as time passes
use_case: "Standard operational planning"
parameters:
  freeze_window_hours: 2
  soft_lock_window_hours: 24
```

---

## Section 5 — UX Proposal (Mission Planner Grade)

### 5.1 Layout Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  MISSION PLANNING WORKBENCH                                    [User] [⚙️]  │
├────────────────┬───────────────────────────────────────┬────────────────────┤
│                │                                       │                    │
│  LEFT PANEL    │          CENTER PANEL                 │   RIGHT PANEL      │
│  (300px)       │          (flex)                       │   (350px)          │
│                │                                       │                    │
│ ┌────────────┐ │  ┌─────────────────────────────────┐ │ ┌────────────────┐ │
│ │ INBOX      │ │  │                                 │ │ │ INSPECTOR      │ │
│ │ [3 new]    │ │  │      TIMELINE VIEW              │ │ │                │ │
│ ├────────────┤ │  │      (Gantt-style)              │ │ │ Selected:      │ │
│ │ • Order-1  │ │  │                                 │ │ │ Athens Acq #3  │ │
│ │ • Order-2  │ │  │  SAT-1  ████░░████░░░░████      │ │ │                │ │
│ │ • Order-3  │ │  │  SAT-2  ░░████░░░░████░░██      │ │ │ Target: Athens │ │
│ └────────────┘ │  │                                 │ │ │ Sat: ICEYE-X44 │ │
│                │  │  [Now]──────────────────▶       │ │ │ Start: 14:32   │ │
│ ┌────────────┐ │  └─────────────────────────────────┘ │ │ Roll: +23.4°   │ │
│ │ SCHEDULED  │ │                                       │ │ Quality: 0.87  │ │
│ │ [12 items] │ │  ┌─────────────────────────────────┐ │ │                │ │
│ ├────────────┤ │  │                                 │ │ │ Lock: [soft ▼] │ │
│ │ ✓ Athens   │ │  │      MAP VIEW                   │ │ │                │ │
│ │ ✓ Berlin   │ │  │      (Cesium)                   │ │ │ [Unlock] [Del] │ │
│ │ ○ Paris    │ │  │                                 │ │ └────────────────┘ │
│ │ ✓ Rome     │ │  │   [Satellite tracks]            │ │                    │
│ └────────────┘ │  │   [Target markers]              │ │ ┌────────────────┐ │
│                │  │   [Swath footprints]            │ │ │ CONFLICTS [2]  │ │
│ ┌────────────┐ │  │                                 │ │ ├────────────────┤ │
│ │ CONFLICTS  │ │  └─────────────────────────────────┘ │ │ ⚠️ Paris:       │ │
│ │ [2 issues] │ │                                       │ │   Slew infeas. │ │
│ ├────────────┤ │                                       │ │ ⚠️ Milan:       │ │
│ │ ⚠️ Paris   │ │                                       │ │   Time overlap │ │
│ │ ⚠️ Milan   │ │                                       │ └────────────────┘ │
│ └────────────┘ │                                       │                    │
│                │                                       │                    │
│ [+ New Order]  │  [Commit Plan] [Reshuffle] [Compare]  │ [Export Schedule]  │
└────────────────┴───────────────────────────────────────┴────────────────────┘
```

### 5.2 UI Surfaces

#### Left Panel: Orders & Schedule

**Inbox Section:**
- Shows unplanned orders (new requests)
- Badge count for pending items
- Click to select and view in inspector
- Drag to timeline to manually assign (future)

**Scheduled Section:**
- List of planned/committed acquisitions
- Status indicators: ✓ committed, ○ tentative, 🔒 locked
- Grouped by target or by satellite (toggle)
- Filter by time range, status, satellite

**Conflicts Section:**
- Real-time conflict detection results
- Click to highlight conflicting items
- Suggested resolution actions

#### Center Panel: Timeline + Map

**Timeline View (Gantt):**
- Horizontal timeline per satellite
- Acquisition blocks with color coding:
  - Green: committed
  - Yellow: tentative
  - Red: conflict
  - Gray: locked (frozen zone)
- Hover for quick info
- Click to select and inspect
- Zoom: hour / day / week views

**Map View (Cesium):**
- Satellite ground tracks
- Target markers with status icons
- Swath footprints for selected acquisitions
- Pass visibility cones (optional)

#### Right Panel: Inspector

**Acquisition Inspector:**
- Full details of selected acquisition
- Editable fields (when unlocked)
- Lock level control dropdown
- Delete/unlock actions
- Related order reference

**Conflict Inspector:**
- Details of conflict type
- Affected acquisitions list
- Resolution options with preview
- "Apply Resolution" button

### 5.3 Mission Planner Actions

| Action | Description | Trigger |
|--------|-------------|---------|
| **Commit Plan** | Promote tentative items to committed | Button + confirmation |
| **Lock/Unlock Item** | Change lock level of acquisition | Inspector dropdown |
| **Reshuffle** | Re-optimize with constraints | Button → config modal |
| **Compare Plans** | Side-by-side plan comparison | After reshuffle, before commit |
| **Drag-Drop** (future) | Manual acquisition placement | Timeline drag |
| **Create Order** | Add new imaging request | "+ New Order" button |
| **Export** | Download schedule as JSON/CSV | Export button |

### 5.4 Compare Plans View

```
┌──────────────────────────────────────────────────────────────────────┐
│  COMPARE PLANS                                          [×]          │
├────────────────────────────────┬─────────────────────────────────────┤
│  CURRENT PLAN                  │  PROPOSED PLAN (Reshuffle)          │
├────────────────────────────────┼─────────────────────────────────────┤
│  Coverage: 12/15 (80%)         │  Coverage: 14/15 (93%) ▲            │
│  Avg Quality: 0.72             │  Avg Quality: 0.78 ▲                │
│  Total Maneuver: 342s          │  Total Maneuver: 298s ▼             │
│  Conflicts: 2                  │  Conflicts: 0 ▲                     │
├────────────────────────────────┼─────────────────────────────────────┤
│  CHANGES:                                                            │
│  • Athens: moved +12min (soft lock respected)                        │
│  • Paris: NEW acquisition added                                      │
│  • Milan: conflict resolved by satellite switch                      │
├────────────────────────────────┴─────────────────────────────────────┤
│  [Keep Current]                              [Accept Proposed Plan]  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Section 6 — API Proposals

### 6.1 Schedule Horizon

```http
GET /api/v1/schedule/horizon
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | ISO datetime | Horizon start (default: now) |
| `to` | ISO datetime | Horizon end (default: +7 days) |
| `satellite_group` | string | Filter by satellite group ID |
| `include_tentative` | boolean | Include tentative acquisitions |

**Response:**
```json
{
  "success": true,
  "horizon": {
    "start": "2025-01-22T00:00:00Z",
    "end": "2025-01-29T00:00:00Z",
    "freeze_cutoff": "2025-01-22T02:00:00Z"
  },
  "acquisitions": [
    {
      "id": "acq_abc123",
      "satellite_id": "ICEYE-X44",
      "target_id": "Athens",
      "start_time": "2025-01-22T14:32:00Z",
      "end_time": "2025-01-22T14:32:05Z",
      "state": "committed",
      "lock_level": "soft",
      "order_id": "ord_xyz789",
      "geometry": { "roll_deg": 23.4, "pitch_deg": 0.0 }
    }
  ],
  "statistics": {
    "total_acquisitions": 12,
    "by_state": { "committed": 8, "tentative": 4 },
    "by_satellite": { "ICEYE-X44": 7, "ICEYE-X45": 5 }
  }
}
```

### 6.2 Create Plan

```http
POST /api/v1/schedule/plan
```

**Request:**
```json
{
  "mode": "incremental",
  "horizon": {
    "start": "2025-01-22T00:00:00Z",
    "end": "2025-01-29T00:00:00Z"
  },
  "orders": [
    {
      "id": "ord_new001",
      "target_id": "Paris",
      "priority": 4,
      "requested_window": {
        "start": "2025-01-23T00:00:00Z",
        "end": "2025-01-25T00:00:00Z"
      },
      "constraints": {
        "max_incidence_deg": 40,
        "preferred_satellite": null
      }
    }
  ],
  "respect_existing": true,
  "config": {
    "algorithm": "roll_pitch_best_fit",
    "quality_model": "band",
    "weights": { "priority": 40, "geometry": 40, "timing": 20 }
  }
}
```

**Response:**
```json
{
  "success": true,
  "plan": {
    "id": "plan_def456",
    "created_at": "2025-01-22T12:00:00Z",
    "status": "candidate",
    "input_hash": "sha256:abc123...",
    "config_snapshot": { ... },
    "items": [
      {
        "id": "planitem_001",
        "order_id": "ord_new001",
        "opportunity_id": "ICEYE-X44_Paris_3_max",
        "satellite_id": "ICEYE-X44",
        "target_id": "Paris",
        "start_time": "2025-01-24T08:15:00Z",
        "end_time": "2025-01-24T08:15:05Z",
        "geometry": { "roll_deg": 18.2, "pitch_deg": 2.1 },
        "quality_score": 0.89
      }
    ],
    "metrics": {
      "coverage": 14,
      "total_targets": 15,
      "coverage_pct": 93.3,
      "total_value": 142.5,
      "avg_quality": 0.78,
      "conflicts": 0
    }
  },
  "opportunities_considered": ["ICEYE-X44_Paris_3_max", "ICEYE-X44_Paris_3_early_30", ...],
  "run_id": "run_ghi789"
}
```

### 6.3 Commit Plan

```http
POST /api/v1/schedule/commit
```

**Request:**
```json
{
  "plan_id": "plan_def456",
  "items_to_commit": ["planitem_001", "planitem_002"],
  "lock_level": "soft",
  "notes": "Weekly planning batch"
}
```

**Response:**
```json
{
  "success": true,
  "committed": 2,
  "acquisitions_created": [
    { "id": "acq_new001", "plan_item_id": "planitem_001" },
    { "id": "acq_new002", "plan_item_id": "planitem_002" }
  ],
  "orders_updated": ["ord_new001"]
}
```

### 6.4 Reshuffle

```http
POST /api/v1/schedule/reshuffle
```

**Request:**
```json
{
  "horizon": {
    "start": "2025-01-22T00:00:00Z",
    "end": "2025-01-29T00:00:00Z"
  },
  "policy": "soft_lock_windowed",
  "freeze_window_hours": 2,
  "optimization_goal": "maximize_quality",
  "config": {
    "algorithm": "roll_pitch_best_fit",
    "quality_model": "band"
  }
}
```

**Response:**
```json
{
  "success": true,
  "current_plan_id": "plan_current",
  "proposed_plan_id": "plan_reshuffled",
  "comparison": {
    "coverage_change": "+2 targets",
    "quality_change": "+0.06 avg",
    "conflicts_resolved": 2,
    "items_moved": 3,
    "items_added": 1,
    "items_unchanged": 9
  },
  "changes": [
    { "type": "moved", "acquisition_id": "acq_abc", "old_time": "...", "new_time": "..." },
    { "type": "added", "target_id": "Paris", "new_acquisition": { ... } }
  ]
}
```

### 6.5 Get Conflicts

```http
GET /api/v1/schedule/conflicts
```

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `horizon_start` | ISO datetime | Start of analysis window |
| `horizon_end` | ISO datetime | End of analysis window |
| `satellite_id` | string | Filter by satellite |

**Response:**
```json
{
  "success": true,
  "conflicts": [
    {
      "id": "conflict_001",
      "type": "temporal_overlap",
      "severity": "error",
      "acquisitions": ["acq_abc", "acq_def"],
      "description": "Acquisitions overlap by 12 seconds on ICEYE-X44",
      "resolution_options": [
        { "action": "move_later", "acquisition_id": "acq_def", "shift_seconds": 15 },
        { "action": "delete", "acquisition_id": "acq_def" }
      ]
    },
    {
      "id": "conflict_002",
      "type": "slew_infeasible",
      "severity": "warning",
      "acquisitions": ["acq_ghi", "acq_jkl"],
      "description": "Insufficient slew time: need 45s, have 32s",
      "resolution_options": [
        { "action": "use_pitch", "acquisition_id": "acq_jkl", "new_pitch_deg": 8.2 }
      ]
    }
  ],
  "summary": {
    "total": 2,
    "by_type": { "temporal_overlap": 1, "slew_infeasible": 1 },
    "by_severity": { "error": 1, "warning": 1 }
  }
}
```

---

## Section 7 — Data Model Proposal

### 7.1 Database Entities

#### orders

```sql
CREATE TABLE orders (
    id TEXT PRIMARY KEY,                    -- UUID: "ord_abc123"
    created_at TEXT NOT NULL,               -- ISO timestamp
    updated_at TEXT NOT NULL,

    -- Status lifecycle
    status TEXT NOT NULL DEFAULT 'new',     -- new | planned | committed | cancelled | completed

    -- Target reference
    target_id TEXT NOT NULL,                -- Reference to target name

    -- Priority and constraints
    priority INTEGER NOT NULL DEFAULT 3,    -- 1-5 scale
    constraints_json TEXT,                  -- JSON: max_incidence, preferred_sat, etc.

    -- Requested window (optional)
    requested_window_start TEXT,            -- ISO timestamp (null = ASAP)
    requested_window_end TEXT,              -- ISO timestamp (null = no deadline)

    -- Metadata
    source TEXT DEFAULT 'manual',           -- manual | api | batch
    notes TEXT,
    external_ref TEXT,                      -- Customer order ID if applicable

    -- Workspace association
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_target ON orders(target_id);
CREATE INDEX idx_orders_window ON orders(requested_window_start, requested_window_end);
CREATE INDEX idx_orders_workspace ON orders(workspace_id);
```

#### acquisitions

```sql
CREATE TABLE acquisitions (
    id TEXT PRIMARY KEY,                    -- UUID: "acq_def456"
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    -- Core scheduling data
    satellite_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    start_time TEXT NOT NULL,               -- ISO timestamp
    end_time TEXT NOT NULL,                 -- ISO timestamp

    -- Mission mode
    mode TEXT NOT NULL DEFAULT 'OPTICAL',   -- OPTICAL | SAR

    -- Geometry
    roll_angle_deg REAL NOT NULL,
    pitch_angle_deg REAL DEFAULT 0.0,
    incidence_angle_deg REAL,

    -- SAR-specific (nullable for optical)
    look_side TEXT,                         -- LEFT | RIGHT
    pass_direction TEXT,                    -- ASCENDING | DESCENDING
    sar_mode TEXT,                          -- spot | strip | scan | dwell
    swath_width_km REAL,
    scene_length_km REAL,

    -- State management
    state TEXT NOT NULL DEFAULT 'tentative', -- tentative | locked | committed | executing | completed | failed
    lock_level TEXT DEFAULT 'none',          -- none | soft | hard

    -- Provenance
    source TEXT NOT NULL DEFAULT 'auto',    -- auto | manual | reshuffle
    order_id TEXT REFERENCES orders(id),
    plan_id TEXT REFERENCES plans(id),
    opportunity_id TEXT,                    -- Reference to original opportunity

    -- Quality metrics
    quality_score REAL,
    maneuver_time_s REAL,
    slack_time_s REAL,

    -- Workspace association
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE INDEX idx_acq_satellite_time ON acquisitions(satellite_id, start_time);
CREATE INDEX idx_acq_target ON acquisitions(target_id);
CREATE INDEX idx_acq_state ON acquisitions(state);
CREATE INDEX idx_acq_time_range ON acquisitions(start_time, end_time);
CREATE INDEX idx_acq_order ON acquisitions(order_id);
CREATE INDEX idx_acq_workspace ON acquisitions(workspace_id);
```

#### plans

```sql
CREATE TABLE plans (
    id TEXT PRIMARY KEY,                    -- UUID: "plan_ghi789"
    created_at TEXT NOT NULL,

    -- Algorithm info
    algorithm TEXT NOT NULL,                -- roll_pitch_best_fit, etc.
    config_json TEXT NOT NULL,              -- Full config snapshot

    -- Reproducibility
    input_hash TEXT NOT NULL,               -- SHA256 of inputs
    run_id TEXT NOT NULL,                   -- Unique run identifier

    -- Metrics
    score REAL,
    metrics_json TEXT NOT NULL,             -- Full metrics object

    -- Status
    status TEXT NOT NULL DEFAULT 'candidate', -- candidate | committed | superseded | rejected

    -- Workspace association
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE INDEX idx_plans_workspace ON plans(workspace_id);
CREATE INDEX idx_plans_status ON plans(status);
```

#### plan_items

```sql
CREATE TABLE plan_items (
    id TEXT PRIMARY KEY,                    -- UUID: "planitem_jkl012"
    plan_id TEXT NOT NULL REFERENCES plans(id) ON DELETE CASCADE,

    -- Acquisition-like fields
    opportunity_id TEXT NOT NULL,
    satellite_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,

    -- Geometry
    roll_angle_deg REAL NOT NULL,
    pitch_angle_deg REAL DEFAULT 0.0,

    -- Metrics
    value REAL,
    quality_score REAL,
    maneuver_time_s REAL,
    slack_time_s REAL,

    -- Reference to order being fulfilled
    order_id TEXT REFERENCES orders(id)
);

CREATE INDEX idx_planitems_plan ON plan_items(plan_id);
CREATE INDEX idx_planitems_opportunity ON plan_items(opportunity_id);
```

#### conflicts

```sql
CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,                    -- UUID: "conflict_mno345"
    detected_at TEXT NOT NULL,

    -- Conflict details
    type TEXT NOT NULL,                     -- temporal_overlap | slew_infeasible | resource_contention
    severity TEXT NOT NULL DEFAULT 'error', -- error | warning | info
    description TEXT,

    -- Affected entities
    acquisition_ids_json TEXT NOT NULL,     -- JSON array of acquisition IDs

    -- Resolution
    resolved_at TEXT,
    resolution_action TEXT,
    resolution_notes TEXT,

    -- Workspace association
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE INDEX idx_conflicts_workspace ON conflicts(workspace_id);
CREATE INDEX idx_conflicts_type ON conflicts(type);
```

### 7.2 Indexing Requirements

| Query Pattern | Index | Table |
|--------------|-------|-------|
| Time range queries | `(start_time, end_time)` | acquisitions |
| Per-satellite timeline | `(satellite_id, start_time)` | acquisitions |
| Order fulfillment lookup | `(order_id)` | acquisitions |
| State filtering | `(state)` | acquisitions, orders |
| Workspace scoping | `(workspace_id)` | all tables |
| Conflict detection | `(satellite_id, start_time)` | acquisitions |

### 7.3 Versioning and Migration Strategy

**Schema Versioning:**
```sql
CREATE TABLE schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);

-- Current version
INSERT INTO schema_migrations VALUES ('2.0', datetime('now'), 'Persistent scheduling');
```

**Migration Path:**
1. **v1.0 → v2.0**: Add orders, acquisitions, plans, conflicts tables
2. Migrate existing `orders_state_json` blobs to normalized tables
3. Keep workspace blobs for backward compatibility (deprecated)

**Backward Compatibility:**
- Existing workspaces remain loadable
- New workspaces use normalized tables
- API response format unchanged for existing clients

---

## Audit Checklist Answers

### Q1: What is the smallest persistent unit we should store so the planner can "know the past"?

**Answer: Both Orders AND Acquisitions**

- **Orders** represent user intent and allow tracking fulfillment status
- **Acquisitions** represent actual schedule slots and are needed for conflict detection
- Storing only orders would require re-planning to know current schedule
- Storing only acquisitions loses the "why" (order priority, constraints)

**Minimum viable:**
```
orders (intent) → acquisitions (schedule) → linked by order_id
```

### Q2: How do we represent locked items vs flexible ones?

**Answer: Two-field model**

```python
state: "tentative" | "locked" | "committed" | "executing" | "completed"
lock_level: "none" | "soft" | "hard"
```

**State machine:**
```
tentative (lock=none) → locked (lock=soft/hard) → committed → executing → completed
                                    ↓
                              unlock → tentative
```

**Enforcement:**
- `hard` lock: No modification allowed except by admin override
- `soft` lock: Can move within original order window
- `none`: Full flexibility

### Q3: How do we detect conflicts efficiently?

**Answer: Interval tree + satellite partitioning**

```python
# Per-satellite conflict detection
def detect_conflicts(acquisitions: List[Acquisition], satellite_id: str):
    # 1. Filter to satellite
    sat_acqs = [a for a in acquisitions if a.satellite_id == satellite_id]

    # 2. Sort by start time
    sat_acqs.sort(key=lambda a: a.start_time)

    # 3. Check adjacent pairs for overlap
    conflicts = []
    for i in range(len(sat_acqs) - 1):
        current = sat_acqs[i]
        next_acq = sat_acqs[i + 1]

        # Include slew time in end calculation
        effective_end = current.end_time + timedelta(seconds=current.slew_to_next)

        if effective_end > next_acq.start_time:
            conflicts.append(TemporalConflict(current, next_acq))

    return conflicts
```

**SQL-based detection:**
```sql
-- Find overlapping acquisitions on same satellite
SELECT a1.id, a2.id, 'temporal_overlap' as type
FROM acquisitions a1
JOIN acquisitions a2 ON a1.satellite_id = a2.satellite_id
WHERE a1.id < a2.id
  AND a1.end_time > a2.start_time
  AND a1.start_time < a2.end_time;
```

### Q4: What's your current schedule horizon concept in UI?

**Answer: Per-run, not global**

Currently, the UI has no persistent schedule horizon. Each planning run operates on:
- Time window from mission analysis (start_time → end_time from form input)
- No concept of "frozen" vs "active" planning zones
- No timeline persistence across sessions

**Proposed change:** Global timeline with configurable horizon stored in workspace.

### Q5: How to keep this compatible with multi-satellite groups and SAR metadata?

**Answer: Satellite groups + mode-specific columns**

```sql
-- Satellite groups table
CREATE TABLE satellite_groups (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    satellite_ids_json TEXT NOT NULL  -- ["ICEYE-X44", "ICEYE-X45"]
);

-- Acquisitions table already has SAR columns:
-- mode, look_side, pass_direction, sar_mode, swath_width_km, scene_length_km

-- Query by group:
SELECT a.* FROM acquisitions a
JOIN satellite_groups g ON json_each.value = a.satellite_id
WHERE g.id = 'iceye_constellation';
```

**Compatibility:**
- Optical missions: SAR columns are NULL
- SAR missions: All columns populated
- Mixed constellations: Mode-aware conflict detection

---

## Instrumentation Added

### A) Planning Response Metadata

**File:** `backend/main.py`

Added to `PlanningResponse`:
```python
{
  "success": true,
  "message": "...",
  "results": { ... },

  # NEW: Audit metadata
  "_audit": {
    "plan_input_hash": "sha256:abc123...",  # Hash of inputs for reproducibility
    "run_id": "run_20250122_120000_xyz",     # Unique run identifier
    "candidate_plan_id": "plan_temp_001",    # In-memory plan ID
    "opportunities_considered": [            # List of opportunity IDs
      "ICEYE-X44_Athens_0_max",
      "ICEYE-X44_Athens_0_early_30",
      ...
    ]
  }
}
```

### B) Schedule State Endpoint

**File:** `backend/routers/schedule.py` (NEW)

```http
GET /api/v1/schedule/state
```

**Response:**
```json
{
  "success": true,
  "message": "Schedule state (currently empty - persistence not implemented)",
  "state": {
    "acquisitions": [],
    "orders": [],
    "conflicts": [],
    "horizon": null
  },
  "_meta": {
    "persistence_enabled": false,
    "schema_version": "2.0-preview"
  }
}
```

This endpoint returns empty data today but establishes the contract for the next PR.

---

## Next Steps (Implementation PRs)

1. **PR: Schema Migration** — Add orders, acquisitions, plans, conflicts tables
2. **PR: Order CRUD** — Endpoints for creating/managing orders
3. **PR: Acquisition Persistence** — Save committed schedules to DB
4. **PR: Conflict Detection Service** — Real-time conflict monitoring
5. **PR: Reshuffle Engine** — Implement repair/reoptimization
6. **PR: UX Implementation** — New left panel, timeline, inspector

---

*Document generated as part of audit/persistent-scheduling-history-reshuffle branch*
