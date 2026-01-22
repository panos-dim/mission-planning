# Conflict Detection + Horizon Truth View

## Overview

The Conflict Detection system analyzes scheduled acquisitions to identify validity issues:
- **Temporal overlaps**: Two acquisitions for the same satellite overlap in time
- **Slew infeasibility**: Insufficient time to maneuver between consecutive acquisitions

Conflicts are detected, persisted, and made visible in the UI without automatic reshuffling.

## Incremental Planning Mode

The system supports **incremental planning** which plans around existing committed acquisitions:

### Planning Modes
- **From Scratch**: Ignores existing schedule, plans fresh (useful for exploring alternatives)
- **Incremental**: Plans around committed/locked acquisitions, avoiding conflicts

### Lock Policy
- **respect_hard_only**: Only hard-locked acquisitions block planning
- **respect_hard_and_soft**: Both hard and soft locks block planning

### How It Works
1. Loads existing acquisitions from the schedule horizon
2. Builds blocked intervals per satellite
3. Filters candidate opportunities to avoid overlaps
4. Checks slew feasibility with neighboring blocked items
5. Returns plan with conflict prediction

### API Endpoint

**POST /api/v1/schedule/plan**

```json
{
  "planning_mode": "incremental",
  "horizon_from": "2024-01-15T00:00:00Z",
  "horizon_to": "2024-01-22T00:00:00Z",
  "workspace_id": "ws_abc123",
  "include_tentative": false,
  "lock_policy": "respect_hard_only",
  "imaging_time_s": 1.0,
  "max_roll_rate_dps": 1.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Created plan with 15 items (incremental: avoided 23 existing acquisitions)",
  "planning_mode": "incremental",
  "existing_acquisitions": {
    "count": 23,
    "by_state": {"committed": 20, "locked": 3},
    "by_satellite": {"SAT-1": 15, "SAT-2": 8},
    "acquisition_ids": ["acq_001", "acq_002", ...]
  },
  "new_plan_items": [...],
  "conflicts_if_committed": [],
  "commit_preview": {
    "will_create": 15,
    "will_conflict_with": 0,
    "warnings": []
  },
  "plan_id": "plan_xyz789"
}
```

## API Endpoints

### GET /api/v1/schedule/conflicts

Query conflicts with optional filters.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `workspace_id` | string | Filter by workspace ID |
| `from` | ISO datetime | Horizon start |
| `to` | ISO datetime | Horizon end |
| `satellite_id` | string | Filter by satellite |
| `conflict_type` | string | `temporal_overlap` or `slew_infeasible` |
| `severity` | string | `error`, `warning`, or `info` |
| `include_resolved` | boolean | Include resolved conflicts (default: false) |

**Response:**
```json
{
  "success": true,
  "conflicts": [
    {
      "id": "conflict_abc123",
      "detected_at": "2024-01-15T10:00:00Z",
      "type": "temporal_overlap",
      "severity": "error",
      "description": "Satellite SAT-1: acquisitions overlap by 300.0s...",
      "acquisition_ids": ["acq_123", "acq_456"],
      "resolved_at": null,
      "resolution_action": null
    }
  ],
  "summary": {
    "total": 1,
    "by_type": {"temporal_overlap": 1},
    "by_severity": {"error": 1}
  }
}
```

### POST /api/v1/schedule/conflicts/recompute

Recompute conflicts for a workspace. Clears existing unresolved conflicts and detects new ones.

**Request Body:**
```json
{
  "workspace_id": "ws_abc123",
  "from_time": "2024-01-15T00:00:00Z",
  "to_time": "2024-01-22T00:00:00Z",
  "satellite_id": null
}
```

**Response:**
```json
{
  "success": true,
  "message": "Detected 3 conflicts, persisted 3",
  "detected": 3,
  "persisted": 3,
  "conflict_ids": ["conflict_1", "conflict_2", "conflict_3"],
  "summary": {
    "total": 3,
    "by_type": {"temporal_overlap": 2, "slew_infeasible": 1},
    "by_severity": {"error": 2, "warning": 1}
  }
}
```

### GET /api/v1/schedule/horizon

Extended with optional `include_conflicts` parameter.

**Query Parameters:**
| Parameter | Type | Description |
|-----------|------|-------------|
| `from` | ISO datetime | Horizon start (default: now) |
| `to` | ISO datetime | Horizon end (default: +7 days) |
| `workspace_id` | string | Filter by workspace |
| `include_tentative` | boolean | Include tentative acquisitions |
| `include_conflicts` | boolean | Include conflicts summary (default: false) |

**Response with conflicts:**
```json
{
  "success": true,
  "horizon": {
    "start": "2024-01-15T00:00:00Z",
    "end": "2024-01-22T00:00:00Z",
    "freeze_cutoff": "2024-01-15T02:00:00Z"
  },
  "acquisitions": [...],
  "statistics": {...},
  "conflicts_summary": {
    "total": 3,
    "by_type": {"temporal_overlap": 2, "slew_infeasible": 1},
    "by_severity": {"error": 2, "warning": 1},
    "error_count": 2,
    "warning_count": 1,
    "conflict_ids": ["conflict_1", "conflict_2", "conflict_3"]
  }
}
```

## Conflict Types

### Temporal Overlap (`temporal_overlap`)

Occurs when two acquisitions for the same satellite have overlapping time windows.

**Detection Logic:**
```
For consecutive acquisitions A1 and A2 (sorted by start_time):
  overlap = A1.end_time - A2.start_time
  if overlap > 0:
    conflict detected
```

**Severity:** Always `error`

### Slew Infeasible (`slew_infeasible`)

Occurs when there isn't enough time between acquisitions to perform the required roll and/or pitch maneuver.

**Detection Logic:**
```
For consecutive acquisitions A1 and A2:
  available_time = A2.start_time - A1.end_time

  roll_delta = abs(A2.roll_angle - A1.roll_angle)
  roll_slew_time = roll_delta / roll_slew_rate

  pitch_delta = abs(A2.pitch_angle - A1.pitch_angle)
  pitch_slew_time = pitch_delta / pitch_slew_rate

  # By default, roll and pitch slew in parallel (max of both)
  if parallel_slew:
    total_slew_time = max(roll_slew_time, pitch_slew_time)
  else:
    total_slew_time = roll_slew_time + pitch_slew_time

  required_time = total_slew_time + settling_time

  if available_time < required_time:
    deficit = required_time - available_time
    if deficit > 10s: severity = "error"
    elif deficit > 5s: severity = "warning"
    else: severity = "info"
```

**Default Configuration:**
- Roll slew rate: 1.0 deg/s
- Pitch slew rate: 1.0 deg/s
- Settling time: 5.0 s
- Parallel slew: true (roll and pitch happen simultaneously)

## Commit Guardrail

The `/api/v1/schedule/commit` endpoint now includes:

**Request Fields:**
- `force`: boolean - Force commit even with error-severity conflicts
- `recompute_conflicts`: boolean - Recompute conflicts after commit (default: true)

**Response Fields:**
- `conflicts_detected`: number - Count of conflicts detected after commit
- `conflict_ids`: string[] - IDs of detected conflicts

## Quick Reproduction Guide

### Create Overlapping Acquisitions

```bash
# Create workspace
curl -X POST http://localhost:8000/api/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Conflicts"}'

# Create overlapping acquisitions via direct commit
curl -X POST http://localhost:8000/api/v1/schedule/commit/direct \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "opportunity_id": "opp_1",
        "satellite_id": "SAT-1",
        "target_id": "T1",
        "start_time": "2024-01-15T10:00:00Z",
        "end_time": "2024-01-15T10:10:00Z",
        "roll_angle_deg": 0
      },
      {
        "opportunity_id": "opp_2",
        "satellite_id": "SAT-1",
        "target_id": "T2",
        "start_time": "2024-01-15T10:05:00Z",
        "end_time": "2024-01-15T10:15:00Z",
        "roll_angle_deg": 0
      }
    ],
    "algorithm": "test",
    "workspace_id": "<workspace_id>"
  }'

# Recompute conflicts
curl -X POST http://localhost:8000/api/v1/schedule/conflicts/recompute \
  -H "Content-Type: application/json" \
  -d '{"workspace_id": "<workspace_id>"}'
```

### Create Slew Infeasible Conflict

```bash
# Create acquisitions with large roll change and small gap
curl -X POST http://localhost:8000/api/v1/schedule/commit/direct \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {
        "opportunity_id": "opp_3",
        "satellite_id": "SAT-1",
        "target_id": "T3",
        "start_time": "2024-01-15T11:00:00Z",
        "end_time": "2024-01-15T11:05:00Z",
        "roll_angle_deg": 0
      },
      {
        "opportunity_id": "opp_4",
        "satellite_id": "SAT-1",
        "target_id": "T4",
        "start_time": "2024-01-15T11:05:10Z",
        "end_time": "2024-01-15T11:10:00Z",
        "roll_angle_deg": 45
      }
    ],
    "algorithm": "test",
    "workspace_id": "<workspace_id>"
  }'
```

## UI Features

### Sidebar Badge
- Red badge: Number of error-severity conflicts
- Yellow badge: Number of warning-severity conflicts (if no errors)

### Conflicts Panel
- Summary badges showing error/warning counts
- Conflict list with type, severity, and description
- Click to select and highlight affected acquisitions
- Recompute button to refresh conflict detection

### Timeline Highlighting (Planned)
- Conflicted acquisitions highlighted in red/yellow
- Click conflict to scroll/focus to affected items

### Inspector (Planned)
- Show conflicts affecting selected acquisition
- Links to paired acquisitions in conflict

## Database Schema

```sql
CREATE TABLE conflicts (
    id TEXT PRIMARY KEY,
    detected_at TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'error',
    description TEXT,
    acquisition_ids_json TEXT NOT NULL,
    resolved_at TEXT,
    resolution_action TEXT,
    resolution_notes TEXT,
    workspace_id TEXT REFERENCES workspaces(id)
);

CREATE INDEX idx_conflicts_workspace ON conflicts(workspace_id);
CREATE INDEX idx_conflicts_type ON conflicts(type);
```

## Future Enhancements (Not in this PR)

- Pitch angle consideration for slew calculation
- Resource contention conflicts (memory, power)
- Automatic conflict resolution suggestions
- Reshuffling engine to resolve conflicts
