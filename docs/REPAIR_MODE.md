# Repair Mode - Schedule Optimization

## Overview

Repair Mode is an advanced planning mode that allows modifying an existing schedule to improve it while respecting hard constraints. Unlike incremental mode which only adds new acquisitions around existing ones, repair mode can intelligently **drop**, **move**, or **replace** soft-locked items to achieve better schedule quality.

## Key Concepts

### Planning Mode Comparison

| Mode | Existing Schedule | Behavior |
|------|------------------|----------|
| `from_scratch` | Ignored | Plans as if timeline is empty |
| `incremental` | Respected | Adds new acquisitions around existing |
| `repair` | Optimized | Keeps hard locks, modifies soft items, fills gaps |

### Soft Lock Policy

Controls how soft-locked acquisitions are treated during repair:

| Policy | Description | Use Case |
|--------|-------------|----------|
| `allow_replace` | Soft items can be dropped and replaced with better alternatives | Maximum optimization |
| `allow_shift` | Soft items can be moved in time but not removed | Preserve targets, optimize timing |
| `freeze_soft` | Soft items treated as hard locks (no modifications) | Minimal disruption |

### Repair Objective

Determines the optimization goal:

| Objective | Description |
|-----------|-------------|
| `maximize_score` | Optimize for highest total schedule value |
| `maximize_priority` | Prioritize high-priority targets |
| `minimize_changes` | Make the fewest possible changes |

### Repair Scope

Defines what portion of the schedule to repair:

| Scope | Description |
|-------|-------------|
| `workspace_horizon` | All acquisitions in workspace within horizon |
| `satellite_subset` | Only specified satellites |
| `target_subset` | Only specified targets |

## Two-Stage Repair Logic

Repair mode uses a "Repair then Fill" approach:

```
┌─────────────────────────────────────────────────────────────┐
│  Stage A: Load & Partition                                  │
│  ┌─────────────┐    ┌─────────────┐                        │
│  │ Hard Locks  │    │ Soft Locks  │                        │
│  │ (Fixed Set) │    │ (Flex Set)  │                        │
│  └─────────────┘    └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage B: Decide Flex Items                                 │
│  - Evaluate each flex item against objective                │
│  - Mark as: keep | drop | shift | replace                   │
│  - Respect max_changes constraint                           │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Stage C: Fill Gaps                                         │
│  - Run planning algorithm on remaining gaps                 │
│  - Add new opportunities where beneficial                   │
│  - Generate repair diff                                     │
└─────────────────────────────────────────────────────────────┘
```

## API Reference

### Endpoint

```
POST /api/v1/schedule/repair
```

### Request

```json
{
  "workspace_id": "default",
  "soft_lock_policy": "allow_replace",
  "max_changes": 100,
  "objective": "maximize_score",
  "repair_scope": "workspace_horizon",
  "satellite_subset": [],
  "target_subset": [],
  "include_tentative": false,
  "horizon_from": "2024-01-15T00:00:00Z",
  "horizon_to": "2024-01-22T00:00:00Z",
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0,
  "max_pitch_rate_dps": 1.0
}
```

### Response

```json
{
  "success": true,
  "message": "Repair plan: 5 kept, 2 dropped, 3 added. Changes: 5/100",
  "planning_mode": "repair",
  "existing_acquisitions": {
    "count": 7,
    "by_state": { "fixed": 3, "flex": 4 },
    "by_satellite": { "SAT-1": 4, "SAT-2": 3 }
  },
  "fixed_count": 3,
  "flex_count": 4,
  "new_plan_items": [...],
  "repair_diff": {
    "kept": ["acq-1", "acq-2", "acq-3", "acq-4", "acq-5"],
    "dropped": ["acq-6", "acq-7"],
    "added": ["acq-8", "acq-9", "acq-10"],
    "moved": [],
    "reason_summary": {
      "dropped": [
        {"id": "acq-6", "reason": "Better alternative found"},
        {"id": "acq-7", "reason": "Conflict with higher priority"}
      ],
      "moved": []
    },
    "change_score": {
      "num_changes": 5,
      "percent_changed": 71.4
    }
  },
  "metrics_comparison": {
    "score_before": 100.0,
    "score_after": 135.0,
    "score_delta": 35.0,
    "conflicts_before": 2,
    "conflicts_after": 0,
    "acquisition_count_before": 7,
    "acquisition_count_after": 8
  },
  "conflicts_if_committed": [],
  "plan_id": "plan_abc123"
}
```

## Frontend Usage

### 1. Switch to Repair Mode

In the Mission Planning panel, click the **Repair** button in the Planning Mode section.

### 2. Configure Repair Settings

- **Soft Lock Policy**: Choose how to handle soft-locked items
- **Max Changes**: Use the slider to limit disruption (0-100)
- **Objective**: Select optimization goal

### 3. Run Repair Planning

Click **Run Mission Planning** to execute the repair.

### 4. Review Repair Diff

The `RepairDiffPanel` component shows:
- Before/after metrics comparison
- Change breakdown (kept, dropped, added, moved)
- Detailed reasons for each change
- Conflict warnings if any

### 5. Commit Changes

Click **Accept Plan → Orders** to commit the repaired schedule.

## Backend Implementation

### Key Classes

```python
# Enums
class PlanningMode(Enum):
    FROM_SCRATCH = "from_scratch"
    INCREMENTAL = "incremental"
    REPAIR = "repair"

class SoftLockPolicy(Enum):
    ALLOW_SHIFT = "allow_shift"
    ALLOW_REPLACE = "allow_replace"
    FREEZE_SOFT = "freeze_soft"

class RepairObjective(Enum):
    MAXIMIZE_SCORE = "maximize_score"
    MAXIMIZE_PRIORITY = "maximize_priority"
    MINIMIZE_CHANGES = "minimize_changes"

# Dataclasses
@dataclass
class FlexibleAcquisition:
    acquisition_id: str
    satellite_id: str
    target_id: str
    original_start: datetime
    original_end: datetime
    roll_angle_deg: float
    lock_level: str = "soft"
    action: str = "keep"  # keep | drop | shift | replace

@dataclass
class RepairPlanningContext:
    soft_lock_policy: SoftLockPolicy
    objective: RepairObjective
    max_changes: int
    fixed_set: List[BlockedInterval]  # Hard locks
    flex_set: List[FlexibleAcquisition]  # Modifiable items

# Pydantic Models
class RepairDiff(BaseModel):
    kept: List[str]
    dropped: List[str]
    added: List[str]
    moved: List[Dict[str, Any]]
    reason_summary: Dict[str, List[Dict[str, str]]]
    change_score: ChangeScore
```

### Key Functions

| Function | Description |
|----------|-------------|
| `load_repair_context()` | Loads and partitions acquisitions into fixed/flex sets |
| `execute_repair_planning()` | Runs the two-stage repair logic |
| `filter_opportunities_incremental()` | Filters candidates against blocked intervals |

## Testing

Run repair mode tests:

```bash
pytest tests/unit/test_incremental_planning.py::TestRepairPlanningMode -v
```

## Best Practices

1. **Start with `freeze_soft`** to preview impact without changes
2. **Use `max_changes` conservatively** to limit disruption
3. **Review the repair diff** before committing
4. **Hard-lock critical acquisitions** before running repair
5. **Use `minimize_changes` objective** when stability is important

## Troubleshooting

### No Changes Made

- Check if all acquisitions are hard-locked
- Verify `max_changes` > 0
- Ensure `soft_lock_policy` allows modifications

### Too Many Changes

- Reduce `max_changes` slider
- Use `freeze_soft` policy
- Switch to `minimize_changes` objective

### Conflicts Remain

- Some conflicts may require manual resolution
- Hard locks cannot be moved even if conflicting
- Consider adjusting satellite agility parameters
