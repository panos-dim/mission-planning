# Incremental Planning Mode

## Overview

Incremental Planning Mode allows mission planners to add new acquisitions to an existing schedule without disrupting committed operations. Instead of planning from scratch, the system respects existing commitments and finds opportunities that fit around them.

## Key Concepts

### Planning Modes

| Mode | Description |
|------|-------------|
| `from_scratch` | Ignores existing schedule; plans as if timeline is empty |
| `incremental` | Respects committed acquisitions; plans around existing schedule |
| `repair` | Repairs existing schedule: keeps hard locks, optionally modifies soft items, fills gaps |

### Lock Policies

| Policy | Description |
|--------|-------------|
| `respect_hard_only` | Only hard-locked acquisitions are immovable; soft locks may be considered for rescheduling |
| `respect_hard_and_soft` | Both hard and soft locks are respected as immovable |

### Blocked Intervals

When in incremental mode, the system loads existing acquisitions within the planning horizon and creates "blocked intervals" for each satellite. New candidates must:

1. **Not overlap** with any blocked interval
2. **Have sufficient slew time** from the previous acquisition
3. **Allow sufficient slew time** for the next acquisition

## Backend Components

### Core Module: `backend/incremental_planning.py`

#### Classes

```python
class PlanningMode(Enum):
    FROM_SCRATCH = "from_scratch"
    INCREMENTAL = "incremental"

class LockPolicy(Enum):
    RESPECT_HARD_ONLY = "respect_hard_only"
    RESPECT_HARD_AND_SOFT = "respect_hard_and_soft"

@dataclass
class BlockedInterval:
    acquisition_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    roll_angle_deg: float
    pitch_angle_deg: float = 0.0
    state: str = "committed"
    lock_level: str = "soft"

@dataclass
class IncrementalPlanningContext:
    mode: PlanningMode
    lock_policy: LockPolicy
    blocked_intervals: Dict[str, List[BlockedInterval]]
    # ... methods for checking blocked time and finding neighbors
```

#### Key Functions

- `load_blocked_intervals()` - Loads existing acquisitions from DB into blocked intervals
- `filter_opportunities_incremental()` - Filters candidate opportunities against blocked intervals
- `check_adjacency_feasibility()` - Validates slew feasibility with neighboring acquisitions

### API Endpoints

#### POST `/api/planning/schedule`

Standard planning endpoint with incremental mode support.

**Request:**
```json
{
  "mode": "incremental",
  "workspace_id": "ws_123",
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "algorithms": ["roll_pitch_best_fit"],
  "value_source": "target_priority"
}
```

#### POST `/api/v1/schedule/plan`

Advanced incremental planning endpoint with full delta-aware response.

**Request:**
```json
{
  "planning_mode": "incremental",
  "workspace_id": "ws_123",
  "horizon_from": "2024-01-15T00:00:00Z",
  "horizon_to": "2024-01-22T00:00:00Z",
  "lock_policy": "respect_hard_only",
  "include_tentative": false
}
```

**Response:**
```json
{
  "success": true,
  "plan_id": "plan_abc123",
  "schedule_context": {
    "loaded_acquisitions": 15,
    "by_state": {"committed": 12, "tentative": 3},
    "by_satellite": {"SAT-1": 8, "SAT-2": 7}
  },
  "new_plan_items": [...],
  "conflicts_if_committed": [],
  "commit_preview": {
    "new_items_count": 5,
    "conflicts_count": 0,
    "warnings": []
  }
}
```

## Frontend Components

### Planning Mode Toggle

Located in `MissionPlanning.tsx`, the planning mode toggle allows switching between:

- **From Scratch**: Plans without considering existing schedule
- **Incremental**: Plans around existing committed acquisitions

### Schedule Context Box

When incremental mode is selected, displays:
- Number of loaded acquisitions in horizon
- Breakdown by acquisition state
- Current lock policy

### Conflict Warning Modal

`ConflictWarningModal.tsx` displays before committing a plan:

- **New items count**: Number of acquisitions to be added
- **Conflicts count**: Predicted conflicts with existing schedule
- **Warnings**: Informational messages about planning context
- **Confirm/Cancel actions**: Proceed or abort commit

## Slew Feasibility

The system validates that new acquisitions are physically achievable given satellite agility constraints:

```
Required Time = max(roll_slew_time, pitch_slew_time) + settling_time
                      (parallel slew)
             OR
             = roll_slew_time + pitch_slew_time + settling_time
                      (sequential slew)
```

### Feasibility Checks

1. **From Previous**: Time from previous acquisition's end to candidate's start must accommodate slew
2. **To Next**: Time from candidate's end to next acquisition's start must accommodate slew

## Configuration

### Slew Parameters

```python
@dataclass
class SlewConfig:
    roll_slew_rate_deg_per_sec: float = 1.0
    pitch_slew_rate_deg_per_sec: float = 1.0
    settling_time_s: float = 5.0
    parallel_slew: bool = True  # Roll and pitch happen simultaneously
```

## Testing

### Unit Tests

Run incremental planning tests:

```bash
python -m pytest tests/unit/test_incremental_planning.py -v -o "addopts="
```

### Test Scenarios

| Scenario | Description |
|----------|-------------|
| `test_scenario_horizon_boundary_respected` | Acquisitions outside horizon don't block |
| `test_scenario_lock_policy_hard_only` | Hard locks are respected |
| `test_scenario_multi_satellite_independence` | Satellites have independent constraints |
| `test_scenario_adjacent_slew_chain` | Slew feasibility in acquisition chains |
| `test_scenario_rejection_reasons_detailed` | Rejection reasons are informative |

## Usage Example

### 1. Switch to Incremental Mode

In the Mission Planning panel, click "Incremental" mode button.

### 2. Review Schedule Context

The context box shows loaded acquisitions from the existing schedule.

### 3. Run Planning

Click "Run Mission Planning" - the algorithm will avoid conflicts with existing acquisitions.

### 4. Review Results

Check the schedule table for new opportunities that fit around existing commitments.

### 5. Commit with Preview

Click "Accept Plan → Orders" to see the conflict warning modal with commit preview.

## Troubleshooting

### No Opportunities Available

- Check if the horizon has too many existing acquisitions
- Consider adjusting lock policy to allow more flexibility
- Verify satellite agility parameters are realistic

### Slew Infeasibility Errors

- Increase gap between acquisitions
- Reduce roll/pitch requirements
- Consider using a more agile satellite

### Unexpected Conflicts

- Run conflict detection to identify issues
- Review blocked intervals for each satellite
- Check if tentative acquisitions should be included/excluded

---

## Repair Mode

Repair Mode is an advanced planning mode that allows modifying an existing schedule to improve it while respecting hard constraints. Unlike incremental mode which only adds new acquisitions, repair mode can drop, move, or replace soft-locked items.

### Repair Mode Concepts

#### Repair Scope

| Scope | Description |
|-------|-------------|
| `workspace_horizon` | Repairs all acquisitions in the workspace within horizon |
| `satellite_subset` | Repairs only specified satellites |
| `target_subset` | Repairs only specified targets |

#### Soft Lock Policy

| Policy | Description |
|--------|-------------|
| `allow_replace` | Soft-locked items can be dropped and replaced with better alternatives |
| `allow_shift` | Soft-locked items can be moved in time but not replaced |
| `freeze_soft` | Soft-locked items are treated as hard locks (no modifications) |

#### Repair Objective

| Objective | Description |
|-----------|-------------|
| `maximize_score` | Optimize for highest total schedule value |
| `maximize_priority` | Prioritize high-priority targets |
| `minimize_changes` | Make the fewest possible changes to the existing schedule |

### Two-Stage Repair Logic

Repair mode uses a "Repair then Fill" approach:

1. **Stage A (Load Context)**: Load existing acquisitions, partition into fixed set (hard locks) and flex set (soft locks based on policy)
2. **Stage B (Decide Flex)**: Evaluate flex items - keep, drop, or move based on objective and conflicts
3. **Stage C (Fill Gaps)**: Run existing planning algorithm to fill gaps with new opportunities

### Repair Diff Response

The repair endpoint returns a detailed diff showing what changed:

```json
{
  "repair_diff": {
    "kept": ["acq-1", "acq-2"],
    "dropped": ["acq-3"],
    "added": ["acq-4", "acq-5"],
    "moved": [
      {
        "id": "acq-6",
        "from_start": "2024-01-15T10:00:00Z",
        "to_start": "2024-01-15T10:30:00Z"
      }
    ],
    "reason_summary": {
      "dropped": [{"id": "acq-3", "reason": "Better alternative found"}],
      "moved": [{"id": "acq-6", "reason": "Conflict resolution"}]
    },
    "change_score": {
      "num_changes": 4,
      "percent_changed": 25.0
    }
  },
  "metrics_comparison": {
    "score_before": 100.0,
    "score_after": 120.0,
    "score_delta": 20.0,
    "conflicts_before": 2,
    "conflicts_after": 0
  }
}
```

### API Endpoint

#### POST `/api/v1/schedule/repair`

**Request:**
```json
{
  "planning_mode": "repair",
  "workspace_id": "default",
  "soft_lock_policy": "allow_replace",
  "max_changes": 100,
  "objective": "maximize_score",
  "include_tentative": false,
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Repair planning completed",
  "planning_mode": "repair",
  "fixed_count": 5,
  "flex_count": 3,
  "new_plan_items": [...],
  "repair_diff": {...},
  "metrics_comparison": {...},
  "conflicts_if_committed": []
}
```

### Frontend Usage

1. **Switch to Repair Mode**: Click the "Repair" button in the Planning Mode section
2. **Configure Repair Settings**:
   - Select soft lock policy (Allow Replace, Allow Shift, or Freeze Soft)
   - Adjust max changes slider
   - Choose optimization objective
3. **Run Repair**: Click "Run Mission Planning"
4. **Review Repair Diff**: The RepairDiffPanel shows before/after comparison
5. **Commit Changes**: Accept the repaired schedule

### Backend Classes

```python
class RepairScope(Enum):
    WORKSPACE_HORIZON = "workspace_horizon"
    SATELLITE_SUBSET = "satellite_subset"
    TARGET_SUBSET = "target_subset"

class SoftLockPolicy(Enum):
    ALLOW_SHIFT = "allow_shift"
    ALLOW_REPLACE = "allow_replace"
    FREEZE_SOFT = "freeze_soft"

class RepairObjective(Enum):
    MAXIMIZE_SCORE = "maximize_score"
    MAXIMIZE_PRIORITY = "maximize_priority"
    MINIMIZE_CHANGES = "minimize_changes"

@dataclass
class FlexibleAcquisition:
    acquisition_id: str
    satellite_id: str
    target_id: str
    start_time: datetime
    end_time: datetime
    roll_angle_deg: float
    lock_level: str
    state: str
    can_shift: bool = True
    can_replace: bool = True

@dataclass
class RepairPlanningContext:
    horizon_start: datetime
    horizon_end: datetime
    workspace_id: str
    soft_lock_policy: SoftLockPolicy
    objective: RepairObjective
    max_changes: int
    fixed_set: Dict[str, List[BlockedInterval]]
    flex_set: Dict[str, List[FlexibleAcquisition]]
```

### Key Functions

- `load_repair_context()` - Loads and partitions acquisitions into fixed/flex sets
- `execute_repair_planning()` - Runs the two-stage repair logic
- `/api/v1/schedule/repair` endpoint - API entry point for repair mode
