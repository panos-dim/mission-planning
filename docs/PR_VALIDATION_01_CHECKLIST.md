# PR-VALIDATION-01 Verification Checklist

Deterministic Validation Harness for Mission Planning Workflows

## Pre-Merge Verification

### Backend Implementation

- [ ] **Workflow Models** (`backend/validation/workflow_models.py`)
  - [ ] `WorkflowScenario` dataclass with config, satellites, targets
  - [ ] `WorkflowScenarioConfig` with all required fields
  - [ ] `WorkflowValidationReport` with stage metrics and invariants
  - [ ] `compute_config_hash()` for determinism verification
  - [ ] `compute_report_hash()` excludes timing, includes results only

- [ ] **Invariant Assertions** (`backend/validation/workflow_assertions.py`)
  - [ ] `check_no_temporal_overlap()` - detects overlapping acquisitions per satellite
  - [ ] `check_slew_feasibility()` - validates maneuver time + settling
  - [ ] `check_hard_locks_unchanged()` - repair mode preserves hard locks
  - [ ] `check_repair_diff_consistent()` - diff matches DB changes
  - [ ] `check_conflict_preview_match()` - preview == post-commit detection
  - [ ] `check_deterministic()` - hash comparison

- [ ] **Workflow Runner** (`backend/validation/workflow_runner.py`)
  - [ ] `_run_analysis_stage()` - SAR and optical paths
  - [ ] `_run_planning_stage()` - scheduler integration
  - [ ] `_run_repair_stage()` - repair mode simulation
  - [ ] `_run_commit_preview_stage()` - conflict preview
  - [ ] `_run_commit_stage()` - DB persistence (when not dry_run)
  - [ ] `_run_conflict_recompute_stage()` - post-commit detection
  - [ ] Stage metrics recorded with runtime_ms

- [ ] **API Endpoints** (`backend/routers/validation.py`)
  - [ ] `POST /api/v1/validate/run` - accepts scenario_id or inline scenario
  - [ ] `GET /api/v1/validate/report/{report_id}` - retrieves stored report
  - [ ] `GET /api/v1/validate/workflow/scenarios` - lists available scenarios
  - [ ] Reports saved to `data/validation/{date}/`

- [ ] **Module Exports** (`backend/validation/__init__.py`)
  - [ ] All new classes exported
  - [ ] No circular imports

### CLI Implementation

- [ ] **CLI Entry Point** (`src/mission_planner/validate.py`)
  - [ ] `--scenario <id>` runs single scenario
  - [ ] `--list` shows available scenarios
  - [ ] `--all` runs all scenarios
  - [ ] `--dry-run` (default) prevents DB mutation
  - [ ] `--check-hash <hash>` verifies determinism
  - [ ] `--verbose` shows stage details
  - [ ] Human-readable summary output
  - [ ] Exit code 0 on pass, 1 on fail

### Frontend Implementation

- [ ] **API Client** (`frontend/src/api/workflowValidation.ts`)
  - [ ] `listWorkflowScenarios()` typed correctly
  - [ ] `runWorkflowValidation()` typed correctly
  - [ ] `getValidationReport()` typed correctly

- [ ] **Admin Panel** (`frontend/src/components/AdminPanel.tsx`)
  - [ ] "Validation" tab added (debug/admin mode only)
  - [ ] Scenario dropdown populated from API
  - [ ] "Run Validation" button with loading state
  - [ ] Pass/fail display with invariant details
  - [ ] Report counts visualization
  - [ ] No new panels in Simple Mode

### Documentation

- [ ] **VALIDATION_HARNESS.md**
  - [ ] Overview of workflow stages
  - [ ] Invariant descriptions
  - [ ] API endpoint documentation
  - [ ] CLI usage examples
  - [ ] Report structure explanation
  - [ ] Adding new scenarios guide
  - [ ] Adding new invariants guide

- [ ] **PR_VALIDATION_01_CHECKLIST.md** (this file)
  - [ ] Complete verification checklist

## Functional Tests

### Run All Scenarios

```bash
python -m mission_planner.validate --all
```

Expected: All scenarios pass with 0 failed invariants.

### Determinism Test

```bash
# Run twice, capture hashes
python -m mission_planner.validate --scenario sar_left_right_basic 2>&1 | grep "Report Hash"
# Note the hash

python -m mission_planner.validate --scenario sar_left_right_basic --check-hash <hash>
```

Expected: Determinism invariant passes.

### API Test

```bash
# List scenarios
curl http://localhost:8000/api/v1/validate/workflow/scenarios | jq

# Run validation
curl -X POST http://localhost:8000/api/v1/validate/run \
  -H "Content-Type: application/json" \
  -d '{"scenario_id": "sar_left_right_basic", "dry_run": true}' | jq

# Get report
curl http://localhost:8000/api/v1/validate/report/<report_id> | jq
```

Expected: All endpoints return valid JSON with expected structure.

### UI Test

1. Start frontend: `cd frontend && npm run dev`
2. Open Admin Panel
3. Click "Validation" tab
4. Select a scenario
5. Click "Run Validation"
6. Verify pass/fail display and counts

Expected: Report displays correctly with invariant results.

## Non-Functional Requirements

- [ ] **Performance**: Single scenario < 5 seconds
- [ ] **Memory**: No memory leaks on repeated runs
- [ ] **No Algorithm Changes**: Existing schedulers unchanged
- [ ] **No New Simple Mode UI**: Only debug/admin trigger
- [ ] **Backward Compatible**: Existing tests still pass

## Constraints Verified

- [ ] Does NOT change `first_fit`, `best_fit`, `roll_pitch_best_fit` algorithms
- [ ] Does NOT add new planner workflows
- [ ] Does NOT add UI panels to mission planner Simple Mode
- [ ] Uses existing data models (workspaces, acquisitions, conflicts)
- [ ] Uses existing CESIUM_ENTITY_ID_CONTRACT patterns

## Files Changed

### New Files

| File | Purpose |
| ---- | ------- |
| `backend/validation/workflow_models.py` | Workflow scenario and report models |
| `backend/validation/workflow_assertions.py` | Invariant checking logic |
| `backend/validation/workflow_runner.py` | Main workflow execution |
| `src/mission_planner/validate.py` | CLI entry point |
| `frontend/src/api/workflowValidation.ts` | Frontend API client |
| `docs/VALIDATION_HARNESS.md` | User documentation |
| `docs/PR_VALIDATION_01_CHECKLIST.md` | This checklist |

### Modified Files

| File | Changes |
| ---- | ------- |
| `backend/validation/__init__.py` | Export new classes |
| `backend/routers/validation.py` | Add workflow endpoints |
| `frontend/src/components/AdminPanel.tsx` | Add Validation tab |

## Sign-off

- [ ] Code reviewed
- [ ] All tests pass
- [ ] Documentation complete
- [ ] No lint errors (critical)
- [ ] Performance acceptable

---

**Reviewer Notes:**

_Add any notes or concerns here before merge._
