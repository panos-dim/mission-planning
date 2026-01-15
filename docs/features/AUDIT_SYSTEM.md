# Mission Planning Audit & Debug System

Comprehensive deep-audit harness for mission planning algorithms with debug API endpoints and reporting capabilities.

## Overview

The audit system provides:
- **Deep algorithm analysis**: Metrics, invariant checks, and schedule validation
- **Debug API endpoints**: REST endpoints for controlled scenario testing
- **Scenario library**: Preset and random scenarios for benchmarking
- **Roll vs Pitch comparison**: Automated analysis of 2D slew capabilities
- **CLI tool**: Easy command-line access to audit functionality

## Architecture

```
src/mission_planner/audit/
├── __init__.py              # Public API exports
├── planning_audit.py        # Core audit engine
└── scenarios.py             # Scenario generator

backend/main.py              # Debug API endpoints
scripts/run_planning_audit.py   # CLI tool
tests/
├── test_audit_planning.py   # Audit tests
└── test_audit_scenarios.py  # Scenario tests
```

## Quick Start

### 1. Start the Backend

```bash
./run_dev.sh
```

### 2. Run a Single Scenario

```bash
python scripts/run_planning_audit.py --preset simple_two_targets
```

### 3. Compare Roll-Only vs Roll+Pitch

```bash
python scripts/run_planning_audit.py --preset tight_timing_three_targets --compare-roll-pitch
```

### 4. Run Benchmark

```bash
python scripts/run_planning_audit.py --benchmark --all-presets
```

## Debug API Endpoints

### `POST /api/v1/debug/planning/run_scenario`

Run a single planning scenario with multiple algorithms.

**Request:**
```json
{
  "scenario_id": "custom_test",
  "satellites": [{
    "id": "ICEYE-X44",
    "name": "ICEYE-X44",
    "tle_line1": "1 48915U ...",
    "tle_line2": "2 48915 ..."
  }],
  "targets": [{
    "id": "target_1",
    "name": "Target 1",
    "latitude": 40.0,
    "longitude": 20.0,
    "priority": 1.0
  }],
  "time_window": {
    "start": "2025-10-13T00:00:00Z",
    "end": "2025-10-13T12:00:00Z"
  },
  "mission_mode": "OPTICAL",
  "algorithms": ["first_fit", "best_fit", "optimal", "first_fit_roll_pitch"],
  "planning_params": {
    "imaging_time_s": 1.0,
    "max_spacecraft_roll_deg": 45.0,
    "max_spacecraft_pitch_deg": 10.0,
    "quality_model": "off"
  }
}
```

**Response:**
```json
{
  "scenario_id": "custom_test",
  "algorithms": {
    "first_fit": {
      "status": "ok",
      "metrics": {
        "accepted": 15,
        "rejected": 12,
        "total_value": 23.4,
        "mean_incidence_deg": 28.1,
        "max_roll_deg": 41.2,
        "max_pitch_deg": 0.0,
        "utilization": 0.37,
        "runtime_ms": 42.0
      },
      "invariants": [
        {"name": "no_overlap", "ok": true},
        {"name": "roll_within_limits", "ok": true},
        {"name": "pitch_within_limits", "ok": true},
        {"name": "slack_non_negative", "ok": true}
      ],
      "schedule": [...]
    }
  },
  "comparisons": {
    "first_fit_vs_roll_pitch": {
      "delta_accepted": 3,
      "delta_value": 2.4,
      "improvements": [...],
      "regressions": []
    }
  }
}
```

### `POST /api/v1/debug/planning/benchmark`

Run multiple scenarios and aggregate results.

**Request:**
```json
{
  "presets": ["simple_two_targets", "tight_timing_three_targets"],
  "num_random_scenarios": 10,
  "algorithms": ["first_fit", "optimal", "first_fit_roll_pitch"]
}
```

**Response:**
```json
{
  "summary": {
    "total_scenarios": 12,
    "successful_scenarios": 12,
    "failed_scenarios": 0
  },
  "aggregated_metrics": {
    "first_fit": {
      "mean_accepted": 7.5,
      "median_accepted": 8,
      "mean_utilization": 0.42,
      "mean_runtime_ms": 38.2
    },
    "first_fit_roll_pitch": {
      "mean_accepted": 8.9,
      "median_accepted": 9,
      "mean_utilization": 0.48,
      "total_pitch_used_deg": 156.3
    }
  },
  "scenario_results": [...]
}
```

### `GET /api/v1/debug/planning/presets`

List available preset scenarios.

**Response:**
```json
{
  "presets": [
    "simple_two_targets",
    "tight_timing_three_targets",
    "long_day_many_targets",
    "cross_hemisphere",
    "dense_cluster"
  ],
  "descriptions": {...}
}
```

## Audit Engine

### Algorithms Supported

- `first_fit` - Roll-only chronological greedy
- `best_fit` - Roll-only geometry optimization
- `optimal` - Roll-only optimal scheduling
- `first_fit_roll_pitch` - 2D slew chronological greedy
- `best_fit_roll_pitch` - 2D slew geometry optimization (if implemented)

### Metrics Computed

**Coverage:**
- `accepted` - Number of scheduled opportunities
- `rejected` - Number of rejected opportunities
- `total_opportunities` - Total input opportunities

**Value:**
- `total_value` - Sum of all accepted values
- `mean_value` - Average value per opportunity

**Geometry:**
- `mean_incidence_deg` - Average off-nadir angle
- `min_incidence_deg` - Best geometry
- `max_incidence_deg` - Worst geometry

**Roll:**
- `total_roll_used_deg` - Sum of absolute roll angles
- `max_roll_deg` - Maximum roll angle used
- `mean_roll_deg` - Average roll angle

**Pitch (2D slew):**
- `total_pitch_used_deg` - Sum of absolute pitch angles
- `max_pitch_deg` - Maximum pitch angle used
- `mean_pitch_deg` - Average pitch angle
- `opps_using_pitch` - Count of opportunities using pitch

**Time:**
- `total_maneuver_time_s` - Time spent maneuvering
- `total_imaging_time_s` - Time spent imaging
- `total_slack_time_s` - Total slack between tasks
- `utilization` - (maneuver + imaging) / total_time

**Performance:**
- `runtime_ms` - Algorithm execution time

### Invariants Checked

1. **no_overlap** - No two tasks overlap in time on same satellite
2. **roll_within_limits** - All roll angles ≤ max_spacecraft_roll_deg
3. **pitch_within_limits** - All pitch angles ≤ max_spacecraft_pitch_deg
4. **slack_non_negative** - All slack values ≥ 0
5. **time_monotonic** - Schedule sorted by start_time per satellite
6. **quality_consistency** - Higher-value opportunities not systematically skipped (heuristic)

## Scenario Library

### Preset Scenarios

**simple_two_targets**
- 2 targets, 12 hours
- Easy to verify manually
- Tags: simple, deterministic

**tight_timing_three_targets**
- 3 clustered targets, 12 hours
- Designed to show roll+pitch advantages
- Tags: tight_timing, roll_pitch_advantage

**long_day_many_targets**
- 15 targets, 24 hours
- Stress test for scalability
- Tags: stress_test, many_targets

**cross_hemisphere**
- 5 targets across hemispheres
- Tests global coverage
- Tags: global, cross_hemisphere

**dense_cluster**
- 8 targets in small area
- Tests within-pass scheduling
- Tags: clustered, high_density

### Random Scenarios

```python
from src.mission_planner.audit import generate_random_scenario

scenario = generate_random_scenario(
    num_targets=10,
    time_span_hours=12,
    seed=42,  # Reproducible
    lat_min=-60.0,
    lat_max=60.0,
    mission_mode="OPTICAL"
)
```

## CLI Tool Usage

### Basic Commands

```bash
# Run single preset
python scripts/run_planning_audit.py --preset simple_two_targets

# Run with roll+pitch comparison
python scripts/run_planning_audit.py --preset tight_timing_three_targets --compare-roll-pitch

# Run benchmark on all presets
python scripts/run_planning_audit.py --benchmark --all-presets

# Run benchmark with random scenarios
python scripts/run_planning_audit.py --benchmark --random 20

# Save results to file
python scripts/run_planning_audit.py --preset simple_two_targets --output results.json
```

### Example Output

```
================================================================================
  Running Preset Scenario: simple_two_targets
================================================================================

  📊 Running mission analysis...
  ✅ Found 6 opportunities
  🔬 Auditing first_fit...
  🔬 Auditing first_fit_roll_pitch...

================================================================================
  Results
================================================================================

Scenario: simple_two_targets
Total Opportunities: 6

Algorithm: first_fit
  Coverage: 5/6 (83.3%)
  Total Value: 4.85
  Mean Incidence: 22.4°
  Roll Usage: max=38.2°, total=156.8°
  Utilization: 37.2%
  Runtime: 12.3ms

Invariant Checks:
  ✅ All invariants passed!

Algorithm: first_fit_roll_pitch
  Coverage: 6/6 (100.0%)
  Total Value: 5.80
  Mean Incidence: 24.1°
  Roll Usage: max=35.1°, total=142.5°
  Pitch Usage: max=8.0°, total=16.0°, opps=2
  Utilization: 42.8%
  Runtime: 15.7ms

Invariant Checks:
  ✅ All invariants passed!

================================================================================
  Roll-Only vs Roll+Pitch Comparison
================================================================================

Coverage Delta: +1 opportunities
Value Delta: +0.95
Utilization Delta: +0.056

Improvements:
  ✅ additional_coverage: Roll+pitch accepted 1 additional opportunities
  ✅ pitch_utilization: 2 opportunities used pitch capability
```

## Python API Usage

### Direct Audit Call

```python
from src.mission_planner.audit import run_algorithm_audit
from src.mission_planner.mission_config import PlanningConstraints

# Create opportunities (from mission analysis)
opportunities = [...]

# Define constraints
constraints = PlanningConstraints(
    max_spacecraft_roll_deg=45.0,
    max_spacecraft_pitch_deg=10.0,
)

# Run audit
report = run_algorithm_audit(
    algorithm_name="first_fit_roll_pitch",
    opportunities=opportunities,
    constraints=constraints,
    satellite_ids=["ICEYE-X44"],
    quality_model="off",
)

# Check results
print(f"Accepted: {report.metrics.accepted}")
print(f"Max pitch: {report.metrics.max_pitch_deg}°")

for inv in report.invariants:
    if not inv.ok:
        print(f"Failed: {inv.name} - {inv.details}")
```

### Roll vs Pitch Comparison

```python
from src.mission_planner.audit import compare_roll_vs_pitch

# Run both algorithms
roll_only_report = run_algorithm_audit("first_fit", ...)
roll_pitch_report = run_algorithm_audit("first_fit_roll_pitch", ...)

# Compare
comparison = compare_roll_vs_pitch(roll_only_report, roll_pitch_report)

if comparison["delta_accepted"] > 0:
    print(f"Pitch enabled {comparison['delta_accepted']} additional shots!")

# Check for unexplained regressions
for reg in comparison["regressions"]:
    if not reg["ok"]:
        print(f"UNEXPLAINED REGRESSION: {reg['details']}")
```

## Use Cases

### 1. Algorithm Development

Test new algorithms against established baselines:

```bash
python scripts/run_planning_audit.py --preset tight_timing_three_targets
```

### 2. Bug Investigation

Reproduce issues with controlled scenarios:

```bash
# Create custom scenario
curl -X POST http://localhost:8000/api/v1/debug/planning/run_scenario \
  -H "Content-Type: application/json" \
  -d @bug_scenario.json
```

### 3. Performance Benchmarking

Compare algorithm performance across diverse conditions:

```bash
python scripts/run_planning_audit.py --benchmark --all-presets --random 50
```

### 4. Regression Testing

Detect when code changes break invariants:

```python
# In CI/CD pipeline
report = run_algorithm_audit(...)
assert all(inv.ok for inv in report.invariants), "Invariants failed!"
```

### 5. Parameter Tuning

Find optimal parameter configurations:

```python
for max_roll in [30, 45, 60]:
    for max_pitch in [0, 5, 10]:
        constraints = PlanningConstraints(
            max_spacecraft_roll_deg=max_roll,
            max_spacecraft_pitch_deg=max_pitch,
        )
        report = run_algorithm_audit(...)
        print(f"Roll={max_roll}, Pitch={max_pitch}: {report.metrics.accepted} accepted")
```

## Testing

Run audit system tests:

```bash
# All audit tests
pytest tests/test_audit_*.py -v

# Just planning audit
pytest tests/test_audit_planning.py -v

# Just scenarios
pytest tests/test_audit_scenarios.py -v
```

## Performance

**Typical Performance (on laptop):**
- Single scenario: < 1s
- Benchmark (20 scenarios): < 5s
- Invariant checks: < 10ms per schedule

**Scalability:**
- Handles 100+ opportunities efficiently
- Parallel scenario execution possible
- Memory-efficient (streaming results)

## Future Enhancements

1. **Parameter Sweeps**: Automated grid search over parameter space
2. **Visualization**: Charts and graphs of benchmark results
3. **Markdown Reports**: Auto-generated PR comments
4. **Regression Database**: Historical tracking of algorithm performance
5. **Multi-Satellite**: Scenarios with multiple satellites
6. **Best-Fit + Pitch**: Implement 2D slew geometry optimization

## Troubleshooting

### Server Not Running

```
❌ Cannot connect to backend server
Please start the server with: ./run_dev.sh
```

**Solution:** Start the backend server first.

### Import Errors

```
ImportError: cannot import name 'run_algorithm_audit'
```

**Solution:** Ensure you're running from project root or have installed the package.

### Invariant Failures

If invariants fail unexpectedly:

1. Check algorithm implementation
2. Verify constraint values are reasonable
3. Review schedule for overlaps/violations
4. Use `--output results.json` to save full details

## Contributing

When adding new algorithms:

1. Add algorithm name to `run_algorithm_audit()` switch
2. Create a preset scenario showcasing advantages
3. Add tests in `test_audit_planning.py`
4. Update this documentation

## References

- Main scheduler: `src/mission_planner/scheduler.py`
- Opportunity generation: `backend/main.py`
- Quality models: `src/mission_planner/quality_scoring.py`
