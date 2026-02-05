# Workflow Validation Harness

**PR-VALIDATION-01** - Deterministic Validation for Mission Planning Workflows

## Overview

The Workflow Validation Harness provides automated, deterministic testing of the complete mission planning workflow:

1. **Mission Analysis** (SAR + optical visibility computation)
2. **Mission Planning** (algorithm-based scheduling)
3. **Optional Repair Mode** (constrained modifications)
4. **Commit Preview** (conflict detection without mutation)
5. **Commit** (optional DB persistence)
6. **Conflict Recompute** (post-commit verification)

This enables proving correctness of scheduling workflows without manual frontend testing.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Validation Harness                        │
├─────────────────────────────────────────────────────────────┤
│  WorkflowValidationRunner                                    │
│  ├── Stage 1: Mission Analysis (SAR/Optical)                │
│  ├── Stage 2: Mission Planning (first_fit, best_fit, ...)  │
│  ├── Stage 3: Repair Mode (optional)                        │
│  ├── Stage 4: Commit Preview                                │
│  ├── Stage 5: Commit (dry_run or temp workspace)           │
│  └── Stage 6: Conflict Recompute                            │
├─────────────────────────────────────────────────────────────┤
│  WorkflowInvariantChecker                                    │
│  ├── No Temporal Overlap                                     │
│  ├── Slew Feasibility                                        │
│  ├── Hard Locks Unchanged                                    │
│  ├── Repair Diff Consistent                                  │
│  ├── Conflict Preview Match                                  │
│  └── Deterministic Hash                                      │
└─────────────────────────────────────────────────────────────┘
```

## Invariants

The harness checks the following invariants:

### 1. No Temporal Overlap (`no_temporal_overlap`)
After commit, no two acquisitions on the same satellite may have overlapping time windows (unless a force flag is used).

### 2. Slew Feasibility (`slew_feasibility`)
For adjacent scheduled items on the same satellite, the available time between acquisitions must be sufficient for:
- Roll maneuver (delta / roll_rate)
- Pitch maneuver (delta / pitch_rate)
- Settling time

### 3. Hard Locks Unchanged (`hard_locks_unchanged`)
In repair mode, items marked as `hard` lock must never be modified or removed.

### 4. Repair Diff Consistent (`repair_diff_consistent`)
When repair mode commits changes, the reported diff (kept/added/dropped/moved counts) must match actual DB changes.

### 5. Conflict Preview Match (`conflict_preview_match`)
The conflicts detected in preview mode must match conflicts detected after commit within the same horizon.

### 6. Deterministic (`deterministic`)
Same scenario configuration with same seed must produce identical report hash across runs.

## Scenarios

Scenarios are defined in `scenarios/*.json` with the following structure:

```json
{
  "id": "scenario_unique_id",
  "name": "Human Readable Name",
  "description": "What this scenario tests",
  "satellites": [
    {
      "id": "sat_1",
      "name": "ICEYE-X1",
      "tle_line1": "...",
      "tle_line2": "..."
    }
  ],
  "targets": [
    {
      "id": "tgt_1",
      "name": "Target-A",
      "latitude": 60.17,
      "longitude": 24.94,
      "priority": 1,
      "lock_level": "none"
    }
  ],
  "config": {
    "start_time": "2024-01-15T00:00:00Z",
    "end_time": "2024-01-16T00:00:00Z",
    "mission_mode": "SAR",
    "imaging_mode": "strip",
    "look_side": "ANY",
    "pass_direction": "ANY",
    "algorithm": "first_fit",
    "run_repair": false,
    "dry_run": true
  },
  "tags": ["sar", "basic"]
}
```

## API Endpoints

### Run Workflow Validation

```
POST /api/v1/validate/run
```

**Request Body:**
```json
{
  "scenario_id": "sar_left_right_basic",
  "dry_run": true,
  "previous_hash": null
}
```

Or with inline scenario:
```json
{
  "scenario": { ... },
  "dry_run": true
}
```

**Response:**
```json
{
  "report_id": "wf_report_abc123",
  "scenario_id": "sar_left_right_basic",
  "scenario_name": "SAR Left/Right Basic",
  "timestamp": "2024-01-15T12:00:00Z",
  "config_hash": "a1b2c3d4",
  "passed": true,
  "total_invariants": 3,
  "passed_invariants": 3,
  "failed_invariants": 0,
  "stages": [...],
  "invariants": [...],
  "counts": {
    "opportunities": 15,
    "planned": 8,
    "committed": 8,
    "conflicts": 0
  },
  "total_runtime_ms": 1234.56,
  "report_hash": "e5f6g7h8",
  "errors": []
}
```

### Get Validation Report

```
GET /api/v1/validate/report/{report_id}
```

### List Workflow Scenarios

```
GET /api/v1/validate/workflow/scenarios
```

## CLI Usage

```bash
# List available scenarios
python -m mission_planner.validate --list

# Run a specific scenario
python -m mission_planner.validate --scenario sar_left_right_basic

# Run all scenarios
python -m mission_planner.validate --all

# Run with determinism check
python -m mission_planner.validate --scenario sar_left_right_basic --check-hash abc123

# Verbose output
python -m mission_planner.validate --scenario sar_left_right_basic --verbose
```

## UI Integration

A minimal "Validation" tab is available in the Admin Panel (debug/admin mode only):

1. Open Admin Panel (gear icon in header)
2. Click "Validation" tab
3. Select a scenario from the dropdown
4. Click "Run Validation"
5. View pass/fail status, counts, and invariant results

This UI is intentionally minimal to avoid cluttering the main mission planner interface.

## Report Structure

```
WorkflowValidationReport
├── report_id          # Unique identifier
├── scenario_id        # Source scenario
├── scenario_name      # Human readable name
├── timestamp          # ISO timestamp
├── config_hash        # Hash of scenario config
├── passed             # Overall pass/fail
├── total_invariants   # Number of invariants checked
├── passed_invariants  # Count passed
├── failed_invariants  # Count failed
├── stages[]           # Per-stage metrics
│   ├── stage          # analysis, planning, repair, ...
│   ├── runtime_ms     # Stage duration
│   ├── success        # Stage completed
│   ├── input_count    # Items in
│   ├── output_count   # Items out
│   └── details        # Stage-specific data
├── invariants[]       # Invariant results
│   ├── invariant      # Invariant type
│   ├── passed         # Check result
│   ├── message        # Human readable result
│   └── violations[]   # Details of failures
├── counts             # Workflow counts
│   ├── opportunities
│   ├── planned
│   ├── committed
│   └── conflicts
├── metrics            # Workflow metrics
├── repair_diff        # Repair summary (if applicable)
├── total_runtime_ms   # Total execution time
├── report_hash        # Determinism verification hash
└── errors[]           # Any errors encountered
```

## Determinism Guarantee

The validation harness ensures deterministic behavior:

1. **Config Hash**: Each scenario config produces a unique hash
2. **Report Hash**: Computed from results (excluding timing), not random IDs
3. **Verification**: Pass `previous_hash` to verify current run matches expected

```bash
# First run - capture hash
python -m mission_planner.validate --scenario test_scenario
# Output: Report Hash: abc123

# Second run - verify determinism
python -m mission_planner.validate --scenario test_scenario --check-hash abc123
# Should pass determinism invariant
```

## Files

| File | Purpose |
|------|---------|
| `backend/validation/workflow_models.py` | Data models for workflow scenarios and reports |
| `backend/validation/workflow_assertions.py` | Invariant checking logic |
| `backend/validation/workflow_runner.py` | Main workflow execution engine |
| `backend/routers/validation.py` | API endpoints |
| `src/mission_planner/validate.py` | CLI entry point |
| `frontend/src/api/workflowValidation.ts` | Frontend API client |
| `frontend/src/components/AdminPanel.tsx` | UI integration |
| `scenarios/*.json` | Scenario definitions |

## Adding New Scenarios

1. Create a new JSON file in `scenarios/`
2. Follow the schema defined above
3. Include appropriate tags for categorization
4. Run validation to verify scenario works:
   ```bash
   python -m mission_planner.validate --scenario your_new_scenario
   ```

## Adding New Invariants

1. Add invariant type to `InvariantType` enum in `workflow_models.py`
2. Implement check method in `WorkflowInvariantChecker` class
3. Add to `check_all_invariants()` method
4. Update documentation

## Performance

Target performance for local development:
- Single scenario: < 5 seconds
- All scenarios: < 30 seconds

Reports are saved to `data/validation/{date}/{report_id}.json` for later analysis.
